import logging
import re
import uuid
from xml.etree import ElementTree

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception
    _logger.warning(
        "cryptography package not installed. "
        "Nextcloud credential encryption will not be available."
    )

# French name particles for N field splitting
_PARTICLES = {"de", "du", "des", "le", "la", "les", "van", "von", "di", "da"}

# Fields on res.partner that trigger a re-sync when changed
SYNC_RELEVANT_FIELDS = {
    "name", "email", "phone", "mobile", "function",
    "parent_id", "company_name", "street", "street2",
    "city", "state_id", "zip", "country_id",
    "website", "comment",
}


def _split_name(full_name):
    """Split a full name into (given, family), handling particles."""
    parts = full_name.strip().split()
    if len(parts) <= 1:
        return "", full_name.strip()
    return parts[0], " ".join(parts[1:])


def _escape_vcard(value):
    """Escape special characters for vCard text values."""
    if not value:
        return ""
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def _unescape_vcard(value):
    """Unescape vCard text values."""
    if not value:
        return ""
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


class NextcloudContactsSyncConfig(models.Model):
    """Configuration for Nextcloud contacts synchronization via CardDAV."""

    _name = "nextcloud.contacts.sync.config"
    _description = "Nextcloud Contacts Sync Configuration"
    _order = "sequence, name"

    name = fields.Char(
        string="Address Book Name",
        required=True,
        help="Display name for this Nextcloud address book",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Nextcloud CardDAV configuration
    nextcloud_base_url = fields.Char(
        string="Nextcloud URL",
        required=True,
        help="Base URL of Nextcloud instance (e.g., https://nextcloud.example.com)",
    )
    carddav_path = fields.Char(
        string="CardDAV Path",
        required=True,
        help="Path to the address book "
        "(e.g., /remote.php/dav/addressbooks/users/olivier/contacts/)",
    )
    nextcloud_user = fields.Char(
        string="Nextcloud User",
        required=True,
        help="Username for CardDAV authentication",
    )
    nextcloud_app_password = fields.Char(
        string="App Password",
        compute="_compute_app_password",
        inverse="_inverse_app_password",
        store=False,
        groups="base.group_system",
        help="Nextcloud app password for CardDAV authentication",
    )
    nextcloud_app_password_encrypted = fields.Char(
        string="App Password (encrypted)",
        groups="base.group_system",
    )

    # Sync configuration
    sync_direction = fields.Selection(
        [
            ("both", "Bidirectional"),
            ("nc_to_odoo", "Nextcloud → Odoo only"),
            ("odoo_to_nc", "Odoo → Nextcloud only"),
        ],
        string="Sync Direction",
        default="odoo_to_nc",
        required=True,
    )
    exclude_tag_id = fields.Many2one(
        "res.partner.category",
        string="Exclusion Tag",
        required=True,
        help="Contacts with this tag will NOT be synchronized",
    )

    # Statistics
    contact_count = fields.Integer(
        string="Synced Contacts",
        compute="_compute_contact_count",
    )
    last_sync = fields.Datetime(
        string="Last Sync",
        readonly=True,
    )
    last_sync_status = fields.Selection(
        [
            ("success", "Success"),
            ("error", "Error"),
            ("partial", "Partial"),
        ],
        string="Last Sync Status",
        readonly=True,
    )
    last_sync_message = fields.Text(
        string="Last Sync Message",
        readonly=True,
    )
    carddav_sync_token = fields.Char(
        string="CardDAV Sync Token",
        help="Opaque token from last sync for incremental pull (RFC 6578)",
        copy=False,
    )

    @api.constrains("nextcloud_base_url")
    def _check_https(self):
        for record in self:
            if record.nextcloud_base_url and not record.nextcloud_base_url.startswith("https://"):
                raise ValidationError(
                    "Nextcloud URL must use HTTPS to protect credentials in transit."
                )

    # === Encryption Methods ===

    def _get_encryption_key(self):
        """Get or generate encryption key from system parameters."""
        if not Fernet:
            return None
        ICP = self.env["ir.config_parameter"].sudo()
        key = ICP.get_param("contacts_nextcloud_sync.encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            ICP.set_param("contacts_nextcloud_sync.encryption_key", key)
        return key.encode()

    def _encrypt_value(self, value):
        """Encrypt a string value using Fernet symmetric encryption."""
        if not value:
            return False
        key = self._get_encryption_key()
        if not key:
            raise ValueError(
                "Cannot store password: cryptography package is not installed. "
                "Install it with: pip install cryptography"
            )
        try:
            f = Fernet(key)
            return f.encrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(f"Cannot encrypt password: {e}") from e

    def _decrypt_value(self, encrypted_value):
        """Decrypt a Fernet-encrypted value. Falls back to returning as-is."""
        if not encrypted_value:
            return False
        key = self._get_encryption_key()
        if not key:
            return encrypted_value
        try:
            f = Fernet(key)
            return f.decrypt(encrypted_value.encode()).decode()
        except InvalidToken:
            _logger.debug("Value appears to be unencrypted, returning as-is")
            return encrypted_value
        except Exception as e:
            _logger.error("Decryption failed: %s", e)
            return encrypted_value

    # === Computed Fields ===

    def _compute_app_password(self):
        """Decrypt app password for display."""
        for record in self:
            record.nextcloud_app_password = record._decrypt_value(
                record.nextcloud_app_password_encrypted
            )

    def _inverse_app_password(self):
        """Encrypt app password on write."""
        for record in self:
            if record.nextcloud_app_password:
                record.nextcloud_app_password_encrypted = record._encrypt_value(
                    record.nextcloud_app_password
                )
            else:
                record.nextcloud_app_password_encrypted = False

    @api.depends("name")
    def _compute_contact_count(self):
        """Count contacts linked to this configuration."""
        for record in self:
            record.contact_count = self.env["res.partner"].search_count(
                [("x_nc_contacts_config_id", "=", record.id)]
            )

    @property
    def carddav_url(self):
        """Return full CardDAV URL for this address book."""
        base = self.nextcloud_base_url.rstrip("/")
        path = self.carddav_path
        if not path.startswith("/"):
            path = "/" + path
        if not path.endswith("/"):
            path += "/"
        return base + path

    # === Actions ===

    def action_view_contacts(self):
        """Open view of contacts synced via this configuration."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Contacts: {self.name}",
            "res_model": "res.partner",
            "views": [[False, "list"], [False, "form"]],
            "domain": [("x_nc_contacts_config_id", "=", self.id)],
        }

    def action_test_connection(self):
        """Test connection to Nextcloud CardDAV endpoint via PROPFIND."""
        self.ensure_one()

        password = self.nextcloud_app_password
        if not password:
            self.update_sync_status("error", "No app password configured.")
            return self._notify(
                "No app password configured. Enter the Nextcloud app password first.",
                "warning",
            )

        url = self.carddav_url
        propfind_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:">'
            "<d:prop>"
            "<d:displayname/>"
            "<d:resourcetype/>"
            "</d:prop>"
            "</d:propfind>"
        )

        try:
            response = requests.request(
                "PROPFIND",
                url,
                data=propfind_body,
                headers={"Content-Type": "application/xml", "Depth": "0"},
                auth=(self.nextcloud_user, password),
                timeout=15,
            )
        except requests.ConnectionError:
            msg = f"Cannot reach {self.nextcloud_base_url} — check URL and network."
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")
        except requests.Timeout:
            msg = f"Connection to {self.nextcloud_base_url} timed out (15s)."
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")
        except requests.RequestException as e:
            msg = f"Request error: {e}"
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")

        if response.status_code in (401, 403):
            msg = (
                f"Authentication failed (HTTP {response.status_code}). "
                "Check username and app password."
            )
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")

        if response.status_code == 404:
            msg = f"Address book not found at {self.carddav_path}. Check the CardDAV path."
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")

        if response.status_code != 207:
            msg = f"Unexpected response: HTTP {response.status_code}"
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")

        display_name = self._parse_propfind_displayname(response.text)
        msg = (
            f"Connected successfully! Address book: {display_name}"
            if display_name
            else "Connected successfully! (could not parse address book name)"
        )
        self.update_sync_status("success", msg)
        return self._notify(msg, "success")

    def action_sync_now(self):
        """Dispatch to push/pull based on sync_direction."""
        self.ensure_one()
        if self.sync_direction == "odoo_to_nc":
            return self.action_push_to_nextcloud()
        elif self.sync_direction == "nc_to_odoo":
            return self.action_pull_from_nextcloud()
        else:
            # Bidirectional: pull first, then push
            self.action_pull_from_nextcloud()
            return self.action_push_to_nextcloud()

    def action_push_to_nextcloud(self):
        """Push all tagged contacts to Nextcloud address book."""
        self.ensure_one()

        if self.sync_direction == "nc_to_odoo":
            return self._notify(
                "Sync direction is Nextcloud → Odoo only. Cannot push.", "warning"
            )

        password = self.nextcloud_app_password
        if not password:
            return self._notify("No app password configured.", "warning")

        # Get all contacts except those with the exclusion tag
        # Includes both companies and individuals (type=contact)
        partners = self.env["res.partner"].search([
            ("category_id", "not in", [self.exclude_tag_id.id]),
            ("type", "=", "contact"),
            "|", ("email", "!=", False), ("name", "!=", False),
        ])

        if not partners:
            return self._notify("No contacts to sync.", "info")

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Get existing vCards in NC for orphan detection + stale UID check
        nc_uids = set()
        try:
            nc_entries = self._carddav_propfind_vcards()
            nc_uids = {e["uid"] for e in nc_entries}
        except Exception as e:
            _logger.warning("Could not list NC vCards for orphan detection: %s", e)

        # Detect stale UIDs: contacts tracked in Odoo whose vCards are
        # missing from NC (e.g. interrupted push). Clear their sync fields
        # so they get recreated below.
        if nc_uids:
            stale = 0
            for partner in partners:
                if (
                    partner.x_nc_contact_uid
                    and partner.x_nc_contact_uid not in nc_uids
                ):
                    partner.with_context(skip_nc_contact_sync=True).write({
                        "x_nc_contact_uid": False,
                        "x_carddav_etag": False,
                    })
                    stale += 1
            if stale:
                _logger.info(
                    "Cleared %d stale UIDs (missing from NC) for %s",
                    stale, self.name,
                )
                # Re-read partners to pick up cleared fields
                partners = partners.exists()

        odoo_uids = set()

        for partner in partners:
            try:
                vcard_text = self._partner_to_vcard(partner)

                if not partner.x_nc_contact_uid:
                    # New contact — create in NC
                    uid = str(uuid.uuid4())
                    new_etag = self._carddav_put_vcard(uid, vcard_text)
                    partner.with_context(skip_nc_contact_sync=True).write({
                        "x_nc_contact_uid": uid,
                        "x_carddav_etag": new_etag or "",
                        "x_nc_contacts_config_id": self.id,
                        "x_contact_sync_source": "odoo",
                        "x_contact_last_sync": fields.Datetime.now(),
                    })
                    odoo_uids.add(uid)
                    created += 1
                elif not partner.x_carddav_etag:
                    # Contact needs update (etag cleared = dirty)
                    new_etag = self._carddav_put_vcard(
                        partner.x_nc_contact_uid, vcard_text,
                        etag=None,  # No If-Match — force overwrite
                    )
                    partner.with_context(skip_nc_contact_sync=True).write({
                        "x_carddav_etag": new_etag or "",
                        "x_nc_contacts_config_id": self.id,
                        "x_contact_last_sync": fields.Datetime.now(),
                    })
                    odoo_uids.add(partner.x_nc_contact_uid)
                    updated += 1
                else:
                    # Unchanged
                    odoo_uids.add(partner.x_nc_contact_uid)
                    skipped += 1

                # Commit after each write to persist progress
                # (protects against interrupted long-running pushes)
                if created + updated > 0 and (created + updated) % 10 == 0:
                    self.env.cr.commit()  # pylint: disable=invalid-commit

            except Exception as e:
                _logger.error(
                    "Error pushing contact %s (id=%s): %s",
                    partner.name, partner.id, e,
                )
                errors += 1

        # Commit any remaining writes before orphan cleanup
        self.env.cr.commit()  # pylint: disable=invalid-commit

        # Orphan detection: vCards in NC not in Odoo → delete from NC
        deleted = 0
        orphan_uids = nc_uids - odoo_uids
        for orphan_uid in orphan_uids:
            try:
                self._carddav_delete_vcard(orphan_uid)
                deleted += 1
            except Exception as e:
                _logger.warning("Failed to delete orphan vCard %s: %s", orphan_uid, e)

        # Summary
        parts = []
        if created:
            parts.append(f"{created} created")
        if updated:
            parts.append(f"{updated} updated")
        if deleted:
            parts.append(f"{deleted} orphans removed")
        if skipped:
            parts.append(f"{skipped} unchanged")
        if errors:
            parts.append(f"{errors} errors")
        summary = ", ".join(parts) if parts else "No contacts to push"
        msg = f"Push complete: {summary}"

        status = "error" if errors and not (created or updated) else (
            "partial" if errors else "success"
        )
        self.update_sync_status(status, msg)
        return self._notify(msg, "success" if not errors else "warning")

    def action_pull_from_nextcloud(self):
        """Pull all vCards from NC address book and upsert into Odoo."""
        self.ensure_one()

        if self.sync_direction == "odoo_to_nc":
            return self._notify(
                "Sync direction is Odoo → Nextcloud only. Cannot pull.", "warning"
            )

        password = self.nextcloud_app_password
        if not password:
            return self._notify("No app password configured.", "warning")

        # PROPFIND Depth:1 to get all UIDs + ETags
        try:
            nc_entries = self._carddav_propfind_vcards()
        except Exception as e:
            msg = f"Failed to list address book: {e}"
            self.update_sync_status("error", msg)
            return self._notify(msg, "danger")

        if not nc_entries:
            self.update_sync_status("success", "Address book is empty")
            return self._notify("Address book is empty.", "info")

        # Pre-fetch existing partners with sync UIDs for this config
        existing_partners = self.env["res.partner"].search([
            ("x_nc_contacts_config_id", "=", self.id),
            ("x_nc_contact_uid", "!=", False),
        ])
        existing_by_uid = {p.x_nc_contact_uid: p for p in existing_partners}
        existing_etags = {p.x_nc_contact_uid: p.x_carddav_etag for p in existing_partners}

        # Determine which vCards need fetching (changed ETags)
        to_fetch = []
        nc_uids_seen = set()
        skipped = 0

        for entry in nc_entries:
            uid = entry["uid"]
            etag = entry["etag"]
            nc_uids_seen.add(uid)

            if uid in existing_etags and existing_etags[uid] == etag:
                skipped += 1
                continue
            to_fetch.append(uid)

        # Fetch changed/new vCards
        created = 0
        updated = 0
        errors = 0
        Partner = self.env["res.partner"]
        ctx = {"skip_nc_contact_sync": True, "tracking_disable": True}

        for uid in to_fetch:
            try:
                vcard_text, etag = self._carddav_get_vcard(uid)
                if not vcard_text:
                    continue

                contact_data = self._parse_vcard(vcard_text)
                if not contact_data:
                    _logger.warning("Could not parse vCard for UID %s", uid)
                    errors += 1
                    continue

                # Build partner vals
                vals = self._vcard_data_to_partner_vals(contact_data)
                vals.update({
                    "x_nc_contact_uid": uid,
                    "x_carddav_etag": etag or "",
                    "x_nc_contacts_config_id": self.id,
                    "x_contact_sync_source": "nextcloud",
                    "x_contact_last_sync": fields.Datetime.now(),
                })

                existing = existing_by_uid.get(uid)
                if existing:
                    existing.with_context(**ctx).write(vals)
                    updated += 1
                else:
                    # Try matching by email before creating
                    match = None
                    if contact_data.get("email"):
                        match = Partner.search([
                            ("email", "=ilike", contact_data["email"]),
                            ("x_nc_contacts_config_id", "=", False),
                        ], limit=1)

                    if match:
                        match.with_context(**ctx).write(vals)
                        existing_by_uid[uid] = match
                        updated += 1
                    else:
                        new_partner = Partner.with_context(**ctx).create(vals)
                        existing_by_uid[uid] = new_partner
                        created += 1

            except Exception as e:
                _logger.error("Error pulling vCard UID %s: %s", uid, e)
                errors += 1

        # Orphan detection: partners with config but UID not in NC → clear sync fields
        deleted = 0
        orphan_partners = Partner.search([
            ("x_nc_contacts_config_id", "=", self.id),
            ("x_nc_contact_uid", "!=", False),
            ("x_nc_contact_uid", "not in", list(nc_uids_seen)),
        ])
        for orphan in orphan_partners:
            orphan.with_context(**ctx).write({
                "x_nc_contact_uid": False,
                "x_carddav_etag": False,
                "x_carddav_href": False,
                "x_nc_contacts_config_id": False,
                "x_contact_sync_source": False,
            })
            deleted += 1

        # Summary
        parts = []
        if created:
            parts.append(f"{created} created")
        if updated:
            parts.append(f"{updated} updated")
        if deleted:
            parts.append(f"{deleted} orphans cleared")
        if skipped:
            parts.append(f"{skipped} unchanged")
        if errors:
            parts.append(f"{errors} errors")
        summary = ", ".join(parts) if parts else "No contacts found"
        msg = f"Pull complete: {summary}"

        status = "error" if errors and not (created or updated) else (
            "partial" if errors else "success"
        )
        self.update_sync_status(status, msg)
        return self._notify(msg, "success" if not errors else "warning")

    def action_force_full_resync(self):
        """Wipe NC address book, clear all Odoo sync fields, and re-push."""
        self.ensure_one()

        # 1. Delete all vCards from NC address book
        try:
            nc_entries = self._carddav_propfind_vcards()
            deleted = 0
            for entry in nc_entries:
                try:
                    self._carddav_delete_vcard(entry["uid"])
                    deleted += 1
                except Exception as e:
                    _logger.warning(
                        "Force resync: failed to delete %s: %s", entry["uid"], e
                    )
            _logger.info(
                "Force resync: deleted %d vCards from NC for %s",
                deleted, self.name,
            )
        except Exception as e:
            _logger.error("Force resync: failed to list NC vCards: %s", e)

        # 2. Clear all sync fields on linked Odoo contacts
        partners = self.env["res.partner"].search([
            ("x_nc_contacts_config_id", "=", self.id),
        ])
        if partners:
            partners.with_context(skip_nc_contact_sync=True).write({
                "x_nc_contact_uid": False,
                "x_carddav_etag": False,
            })

        self.carddav_sync_token = False
        self.env.cr.commit()  # pylint: disable=invalid-commit

        # 3. Fresh push
        return self.action_sync_now()

    # === Cron Methods ===

    @api.model
    def _cron_sync_all(self):
        """Cron job: sync all active configurations."""
        configs = self.search([
            ("active", "=", True),
            ("nextcloud_app_password_encrypted", "!=", False),
        ])
        for config in configs:
            try:
                config.action_sync_now()
            except Exception:
                _logger.exception(
                    "Cron sync failed for config %s (id=%s)",
                    config.name, config.id,
                )
                config.update_sync_status("error", "Cron sync error: see logs")

    @api.model
    def _cron_full_resync(self):
        """Cron job: periodic full resync as a consistency safety net."""
        configs = self.search([
            ("active", "=", True),
            ("nextcloud_app_password_encrypted", "!=", False),
        ])
        for config in configs:
            try:
                config.action_force_full_resync()
            except Exception:
                _logger.exception(
                    "Cron full resync failed for config %s (id=%s)",
                    config.name, config.id,
                )
                config.update_sync_status("error", "Full resync error: see logs")

    # === CardDAV HTTP Operations ===

    def _carddav_auth(self):
        """Return (user, password) tuple for CardDAV requests."""
        self.ensure_one()
        return (self.nextcloud_user, self.nextcloud_app_password)

    def _carddav_propfind_vcards(self):
        """PROPFIND Depth:1 to list all vCard UIDs and ETags.

        Returns list of dicts: [{"uid": "xxx.vcf", "etag": "yyy", "href": "/..."}]
        """
        self.ensure_one()
        propfind_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:">'
            "<d:prop>"
            "<d:getetag/>"
            "<d:getcontenttype/>"
            "</d:prop>"
            "</d:propfind>"
        )

        response = requests.request(
            "PROPFIND",
            self.carddav_url,
            data=propfind_body,
            headers={"Content-Type": "application/xml", "Depth": "1"},
            auth=self._carddav_auth(),
            timeout=30,
        )

        if response.status_code != 207:
            raise RuntimeError(
                f"PROPFIND failed: HTTP {response.status_code}"
            )

        return self._parse_propfind_entries(response.text)

    def _carddav_get_vcard(self, uid):
        """GET a single vCard by UID.

        Returns (vcard_text, etag) tuple.
        """
        self.ensure_one()
        # Ensure .vcf extension
        filename = uid if uid.endswith(".vcf") else f"{uid}.vcf"
        url = self.carddav_url + filename

        response = requests.get(
            url,
            auth=self._carddav_auth(),
            timeout=15,
        )

        if response.status_code == 404:
            return None, None

        response.raise_for_status()

        etag = response.headers.get("ETag", "").strip('"')
        return response.text, etag

    def _carddav_put_vcard(self, uid, vcard_text, etag=None):
        """PUT a vCard to Nextcloud. Returns new ETag.

        If etag is provided, uses If-Match for conditional update.
        """
        self.ensure_one()
        filename = uid if uid.endswith(".vcf") else f"{uid}.vcf"
        url = self.carddav_url + filename

        headers = {"Content-Type": "text/vcard; charset=utf-8"}
        if etag:
            headers["If-Match"] = f'"{etag}"'

        response = requests.put(
            url,
            data=vcard_text.encode("utf-8"),
            headers=headers,
            auth=self._carddav_auth(),
            timeout=15,
        )
        response.raise_for_status()

        return response.headers.get("ETag", "").strip('"')

    def _carddav_delete_vcard(self, uid):
        """DELETE a vCard from Nextcloud."""
        self.ensure_one()
        filename = uid if uid.endswith(".vcf") else f"{uid}.vcf"
        url = self.carddav_url + filename

        response = requests.delete(
            url,
            auth=self._carddav_auth(),
            timeout=15,
        )

        if response.status_code == 404:
            return  # Already gone
        response.raise_for_status()

    # === vCard Parsing (custom, no vobject dependency) ===

    def _parse_propfind_entries(self, xml_text):
        """Parse PROPFIND Depth:1 207 response into vCard entries."""
        ns = {"d": "DAV:"}
        entries = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            _logger.error("Failed to parse PROPFIND response XML")
            return entries

        for resp in root.findall("d:response", ns):
            href_el = resp.find("d:href", ns)
            href = href_el.text if href_el is not None else None
            if not href or not href.endswith(".vcf"):
                continue

            etag_el = resp.find(".//d:getetag", ns)
            etag = (
                etag_el.text.strip('"')
                if etag_el is not None and etag_el.text
                else None
            )

            # Extract UID from href (filename without .vcf)
            uid = href.rstrip("/").rsplit("/", 1)[-1].replace(".vcf", "")
            entries.append({"uid": uid, "etag": etag, "href": href})

        return entries

    def _parse_propfind_displayname(self, xml_text):
        """Extract displayname from PROPFIND 207 Multi-Status response."""
        try:
            root = ElementTree.fromstring(xml_text)
            ns = {"d": "DAV:"}
            dn = root.find(".//d:displayname", ns)
            if dn is not None and dn.text:
                return dn.text
        except ElementTree.ParseError:
            _logger.warning("Failed to parse PROPFIND response XML")
        return None

    def _parse_vcard(self, vcard_text):
        """Parse vCard text into a dict of contact fields.

        Handles line folding (RFC 6350 section 3.2).
        Returns dict with keys: name, first_name, last_name, email, phone,
            mobile, title, organization, website, notes, address.
        """
        if not vcard_text:
            return None

        # Unfold lines: continuation lines start with space or tab
        unfolded = re.sub(r"\r?\n[ \t]", "", vcard_text)
        lines = unfolded.splitlines()

        in_vcard = False
        data = {
            "name": "",
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "mobile": "",
            "title": "",
            "organization": "",
            "website": "",
            "notes": "",
            "street": "",
            "street2": "",
            "city": "",
            "state": "",
            "zip": "",
            "country": "",
        }

        for line in lines:
            stripped = line.strip()
            if stripped.upper() == "BEGIN:VCARD":
                in_vcard = True
                continue
            if stripped.upper() == "END:VCARD":
                break
            if not in_vcard:
                continue

            if ":" not in stripped:
                continue

            prop_part, _, value = stripped.partition(":")
            prop_name = prop_part.split(";")[0].upper()
            params_str = prop_part[len(prop_name):].upper()

            if prop_name == "FN":
                data["name"] = _unescape_vcard(value)
            elif prop_name == "N":
                # N: family;given;additional;prefix;suffix
                parts = value.split(";")
                data["last_name"] = _unescape_vcard(parts[0]) if len(parts) > 0 else ""
                data["first_name"] = _unescape_vcard(parts[1]) if len(parts) > 1 else ""
            elif prop_name == "EMAIL":
                if not data["email"]:
                    data["email"] = value.strip()
            elif prop_name == "TEL":
                if "CELL" in params_str:
                    if not data["mobile"]:
                        data["mobile"] = value.strip()
                else:
                    if not data["phone"]:
                        data["phone"] = value.strip()
            elif prop_name == "TITLE":
                data["title"] = _unescape_vcard(value)
            elif prop_name == "ORG":
                # ORG can have multiple components separated by ;
                org_parts = value.split(";")
                data["organization"] = _unescape_vcard(org_parts[0]) if org_parts else ""
            elif prop_name == "URL":
                data["website"] = value.strip()
            elif prop_name == "NOTE":
                data["notes"] = _unescape_vcard(value)
            elif prop_name == "ADR":
                # ADR: PO Box;Extended;Street;City;State;Zip;Country
                adr_parts = value.split(";")
                data["street"] = _unescape_vcard(adr_parts[2]) if len(adr_parts) > 2 else ""
                data["street2"] = _unescape_vcard(adr_parts[1]) if len(adr_parts) > 1 else ""
                data["city"] = _unescape_vcard(adr_parts[3]) if len(adr_parts) > 3 else ""
                data["state"] = _unescape_vcard(adr_parts[4]) if len(adr_parts) > 4 else ""
                data["zip"] = _unescape_vcard(adr_parts[5]) if len(adr_parts) > 5 else ""
                data["country"] = _unescape_vcard(adr_parts[6]) if len(adr_parts) > 6 else ""

        # Fallback: derive name from N if FN is empty
        if not data["name"] and (data["first_name"] or data["last_name"]):
            data["name"] = f"{data['first_name']} {data['last_name']}".strip()

        # Fallback: derive first/last from FN if N is empty
        if data["name"] and not data["first_name"] and not data["last_name"]:
            data["first_name"], data["last_name"] = _split_name(data["name"])

        return data if data["name"] else None

    def _vcard_data_to_partner_vals(self, contact_data):
        """Convert parsed vCard data dict to res.partner field values."""
        vals = {
            "name": contact_data.get("name", ""),
        }

        if contact_data.get("email"):
            vals["email"] = contact_data["email"]
        if contact_data.get("phone"):
            vals["phone"] = contact_data["phone"]
        if contact_data.get("mobile"):
            vals["mobile"] = contact_data["mobile"]
        if contact_data.get("title"):
            vals["function"] = contact_data["title"]
        if contact_data.get("organization"):
            vals["company_name"] = contact_data["organization"]
        if contact_data.get("website"):
            vals["website"] = contact_data["website"]
        if contact_data.get("notes"):
            vals["comment"] = contact_data["notes"]
        if contact_data.get("street"):
            vals["street"] = contact_data["street"]
        if contact_data.get("street2"):
            vals["street2"] = contact_data["street2"]
        if contact_data.get("city"):
            vals["city"] = contact_data["city"]
        if contact_data.get("zip"):
            vals["zip"] = contact_data["zip"]

        # Resolve state and country by name
        if contact_data.get("state"):
            state = self.env["res.country.state"].search([
                ("name", "=ilike", contact_data["state"]),
            ], limit=1)
            if state:
                vals["state_id"] = state.id

        if contact_data.get("country"):
            country = self.env["res.country"].search([
                ("name", "=ilike", contact_data["country"]),
            ], limit=1)
            if country:
                vals["country_id"] = country.id

        return vals

    def _partner_to_vcard(self, partner):
        """Generate vCard 3.0 text from a res.partner record."""
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
        ]

        # UID
        uid = partner.x_nc_contact_uid or str(uuid.uuid4())
        lines.append(f"UID:{uid}")

        # FN (required)
        fn = partner.name or ""
        lines.append(f"FN:{_escape_vcard(fn)}")

        if partner.is_company:
            # Company: N is empty, ORG = company name
            lines.append("N:;;;;")
            lines.append(f"ORG:{_escape_vcard(fn)}")
        else:
            # Individual: N = family;given
            first, last = _split_name(fn)
            lines.append(f"N:{_escape_vcard(last)};{_escape_vcard(first)};;;")

            # TITLE (function in Odoo = job title)
            if partner.function:
                lines.append(f"TITLE:{_escape_vcard(partner.function)}")

            # ORG
            org_name = ""
            if partner.parent_id:
                org_name = partner.parent_id.name or ""
            elif partner.company_name:
                org_name = partner.company_name
            if org_name:
                lines.append(f"ORG:{_escape_vcard(org_name)}")

        # EMAIL
        if partner.email:
            lines.append(f"EMAIL;TYPE=INTERNET:{partner.email}")

        # TEL
        if partner.phone:
            lines.append(f"TEL;TYPE=WORK:{partner.phone}")
        if partner.mobile:
            lines.append(f"TEL;TYPE=CELL:{partner.mobile}")

        # ADR: PO Box;Extended;Street;City;State;Zip;Country
        street = partner.street or ""
        street2 = partner.street2 or ""
        city = partner.city or ""
        state = partner.state_id.name if partner.state_id else ""
        zip_code = partner.zip or ""
        country = partner.country_id.name if partner.country_id else ""
        if any([street, street2, city, state, zip_code, country]):
            adr_parts = [
                "",  # PO Box
                _escape_vcard(street2),
                _escape_vcard(street),
                _escape_vcard(city),
                _escape_vcard(state),
                _escape_vcard(zip_code),
                _escape_vcard(country),
            ]
            lines.append(f"ADR;TYPE=WORK:{';'.join(adr_parts)}")

        # URL
        if partner.website:
            lines.append(f"URL:{partner.website}")

        # NOTE
        if partner.comment:
            lines.append(f"NOTE:{_escape_vcard(partner.comment)}")

        lines.append("END:VCARD")
        return "\r\n".join(lines) + "\r\n"

    # === Helpers ===

    def update_sync_status(self, status, message=None):
        """Update sync status fields."""
        self.write({
            "last_sync": fields.Datetime.now(),
            "last_sync_status": status,
            "last_sync_message": message or "",
        })

    def _notify(self, message, notif_type):
        """Return a display_notification action."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Contacts Sync",
                "message": message,
                "type": notif_type,
                "sticky": notif_type == "danger",
            },
        }
