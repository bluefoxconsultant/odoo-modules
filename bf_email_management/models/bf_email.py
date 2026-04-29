import base64
import logging
import re
from datetime import timedelta
from email.utils import parseaddr

from odoo import api, fields, models, tools

from . import bf_email_imap

_logger = logging.getLogger(__name__)

_DIRECTION_LABELS = {
    "in": "\u2190",
    "out": "\u2192",
}


class BfEmail(models.Model):
    _name = "bf.email"
    _inherit = ["mail.activity.mixin"]
    _description = "Courriel"
    _order = "date desc, id desc"
    _rec_name = "subject"

    # ------------------------------------------------------------------
    # Core fields
    # ------------------------------------------------------------------
    date = fields.Datetime(
        string="Date",
        required=True,
        index=True,
    )
    email_from = fields.Char(
        string="De",
        index=True,
    )
    email_to = fields.Char(
        string="\u00c0",
    )
    email_cc = fields.Char(
        string="CC",
    )
    subject = fields.Char(
        string="Objet",
        index=True,
    )
    body_preview = fields.Char(
        string="Aper\u00e7u",
        size=300,
        compute="_compute_body_preview",
        store=True,
    )
    body_html = fields.Html(
        string="Corps",
        compute="_compute_body_html",
        store=True,
        readonly=True,
        sanitize=False,
        help="Corps HTML du courriel. Pour une rangée chatter/gateway, "
             "synchronisé depuis mail.message.body. Pour une rangée IMAP "
             "orpheline, parsé depuis raw_rfc822.",
    )
    direction = fields.Selection(
        selection=[
            ("in", "Re\u00e7u"),
            ("out", "Envoy\u00e9"),
        ],
        string="Direction",
        required=True,
        index=True,
    )
    source = fields.Selection(
        selection=[
            ("gateway", "Passerelle courriel"),
            ("chatter", "Chatter"),
            ("imap", "IMAP direct"),
        ],
        string="Source",
        index=True,
        help="Origine du message\u00a0: passerelle courriel entrante/sortante, "
             "commentaire post\u00e9 via le chatter et notifi\u00e9 par courriel, "
             "ou ingestion IMAP directe (orphelin sans chatter Odoo).",
    )
    message_id_header = fields.Char(
        string="Message-ID",
        index=True,
        help="RFC 2822 Message-ID pour la d\u00e9duplication",
    )
    in_reply_to = fields.Char(
        string="In-Reply-To",
        index=True,
    )
    thread_root_id = fields.Char(
        string="Racine du fil",
        index=True,
        help="Message-ID racine du fil RFC 2822 (premier message). "
             "Permet de regrouper la conversation enti\u00e8re.",
    )
    thread_count = fields.Integer(
        string="Nb dans le fil",
        compute="_compute_thread_count",
    )

    # ------------------------------------------------------------------
    # IMAP-direct ingestion (orphan rows without mail.message)
    # ------------------------------------------------------------------
    imap_uid = fields.Char(
        string="IMAP UID",
        index=True,
        help="UID IMAP du message dans son dossier d'origine.",
    )
    imap_folder = fields.Char(
        string="Dossier IMAP",
        help="Dossier IMAP de provenance (INBOX, Sent, Archives/2026, etc.).",
    )
    raw_rfc822 = fields.Binary(
        string="RFC 2822 brut",
        attachment=True,
        help="Message RFC 2822 complet (brut). Conserv\u00e9 pour permettre "
             "le re-routage vers un chatter Odoo.",
    )

    # ------------------------------------------------------------------
    # Links to source
    # ------------------------------------------------------------------
    mail_message_id = fields.Many2one(
        comodel_name="mail.message",
        string="Message source",
        ondelete="set null",
        index=True,
    )
    res_model = fields.Char(
        string="Mod\u00e8le li\u00e9",
        index=True,
    )
    res_id = fields.Many2oneReference(
        string="Enregistrement li\u00e9",
        model_field="res_model",
    )
    record_name = fields.Char(
        string="Enregistrement",
        help="Nom de l'enregistrement li\u00e9 (d\u00e9normalis\u00e9 pour la performance)",
    )

    # ------------------------------------------------------------------
    # Partners
    # ------------------------------------------------------------------
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        index=True,
        help="Contact principal (exp\u00e9diteur pour entrant, destinataire pour sortant)",
    )
    author_id = fields.Many2one(
        comodel_name="res.partner",
        string="Auteur",
    )

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------
    category = fields.Selection(
        selection=[
            ("client", "Client"),
            ("internal", "Interne"),
            ("vendor", "Fournisseur"),
            ("notification", "Notification"),
            ("marketing", "Marketing"),
        ],
        string="Cat\u00e9gorie",
        compute="_compute_category",
        store=True,
        readonly=False,
    )
    priority = fields.Selection(
        selection=[
            ("0", "Normal"),
            ("1", "Faible"),
            ("2", "\u00c9lev\u00e9e"),
            ("3", "Urgente"),
        ],
        string="Priorit\u00e9",
        default="0",
    )
    status = fields.Selection(
        selection=[
            ("new", "Nouveau"),
            ("read", "Lu"),
            ("replied", "R\u00e9pondu"),
            ("archived", "Archiv\u00e9"),
        ],
        string="Statut",
        default="new",
        required=True,
        index=True,
    )
    response_time_hours = fields.Float(
        string="Temps de r\u00e9ponse (h)",
        compute="_compute_response_time",
        store=True,
        help="Heures entre la r\u00e9ception et la premi\u00e8re r\u00e9ponse",
    )
    has_attachments = fields.Boolean(
        string="Pi\u00e8ces jointes",
        default=False,
    )
    attachment_count = fields.Integer(
        string="Nb pi\u00e8ces jointes",
        default=0,
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Fichiers joints",
        related="mail_message_id.attachment_ids",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Operational
    # ------------------------------------------------------------------
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Soci\u00e9t\u00e9",
        default=lambda self: self.env.company,
        index=True,
    )
    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    _sql_constraints = [
        (
            "message_id_header_uniq",
            "UNIQUE(message_id_header, company_id)",
            "Ce courriel existe d\u00e9j\u00e0 (Message-ID dupliqu\u00e9).",
        ),
    ]

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------
    @api.depends("direction", "email_from", "email_to", "subject", "date")
    def _compute_display_name(self):
        for rec in self:
            arrow = _DIRECTION_LABELS.get(rec.direction, "?")
            contact = rec.email_from if rec.direction == "in" else rec.email_to
            contact = (contact or "")[:40]
            subj = (rec.subject or "")[:50]
            rec.display_name = f"{arrow} {contact} \u2014 {subj}"

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------
    @staticmethod
    def _scrub_body(text):
        """Strip NUL bytes (PG TEXT refuses 0x00) and normalize."""
        if not text:
            return ""
        # PostgreSQL TEXT columns reject 0x00. Some clients embed them in
        # inline images or quoted-printable artifacts.
        return text.replace("\x00", "")

    @api.depends("mail_message_id.body", "raw_rfc822", "source")
    def _compute_body_html(self):
        for rec in self:
            if rec.mail_message_id and rec.mail_message_id.body:
                rec.body_html = self._scrub_body(rec.mail_message_id.body)
                continue
            if rec.source == "imap" and rec.raw_rfc822:
                try:
                    raw = base64.b64decode(rec.raw_rfc822)
                    parsed = bf_email_imap.parse_rfc822(raw)
                    body_html, body_plain = bf_email_imap.extract_body(parsed)
                    if body_html:
                        rec.body_html = self._scrub_body(body_html)
                    elif body_plain:
                        # Wrap plain text in <pre> for chatter-like rendering.
                        escaped = (body_plain
                                   .replace("&", "&amp;")
                                   .replace("<", "&lt;")
                                   .replace(">", "&gt;"))
                        rec.body_html = self._scrub_body(
                            f"<pre style=\"white-space:pre-wrap\">{escaped}</pre>"
                        )
                    else:
                        rec.body_html = ""
                except Exception:
                    _logger.warning(
                        "bf.email #%s: failed to parse raw_rfc822 for body",
                        rec.id, exc_info=True,
                    )
                    rec.body_html = ""
            else:
                rec.body_html = ""

    @api.depends("body_html")
    def _compute_body_preview(self):
        for rec in self:
            body = rec.body_html or ""
            text = re.sub(r"<[^>]+>", " ", body)
            text = re.sub(r"\s+", " ", text).strip()
            rec.body_preview = text[:300]

    _NOTIFICATION_PATTERNS = re.compile(
        r"^(noreply|no-reply|notification|mailer-daemon|postmaster|bounce)"
        r"@",
        re.IGNORECASE,
    )

    @api.depends("partner_id", "author_id", "email_from")
    def _compute_category(self):
        for rec in self:
            # Detect notification senders by email pattern
            if rec.email_from and self._NOTIFICATION_PATTERNS.search(
                rec.email_from.strip()
            ):
                rec.category = "notification"
                continue

            partner = rec.partner_id or rec.author_id
            if not partner:
                rec.category = False
                continue
            # customer_rank / supplier_rank live on res.partner only when the
            # sale_team / purchase modules are installed. Tenants without them
            # (PMEC) would AttributeError otherwise.
            customer_rank = getattr(partner, "customer_rank", 0) or 0
            supplier_rank = getattr(partner, "supplier_rank", 0) or 0
            if partner.user_ids:
                rec.category = "internal"
            elif customer_rank > 0:
                rec.category = "client"
            elif supplier_rank > 0:
                rec.category = "vendor"
            else:
                rec.category = False

    @api.depends("date", "direction", "mail_message_id")
    def _compute_response_time(self):
        # Pre-load originals in one query to avoid N+1
        reply_to_ids = [
            r.in_reply_to for r in self
            if r.direction == "out" and r.in_reply_to
        ]
        originals = {}
        if reply_to_ids:
            candidates = self.search([
                ("message_id_header", "in", reply_to_ids),
                ("company_id", "=", self.env.company.id),
            ])
            for c in candidates:
                originals[c.message_id_header] = c.date

        for rec in self:
            rec.response_time_hours = 0.0
            if rec.direction != "out" or not rec.in_reply_to:
                continue
            orig_date = originals.get(rec.in_reply_to)
            if orig_date and rec.date:
                delta = rec.date - orig_date
                rec.response_time_hours = round(
                    delta.total_seconds() / 3600, 2
                )

    @api.depends("thread_root_id", "company_id")
    def _compute_thread_count(self):
        for rec in self:
            if not rec.thread_root_id:
                rec.thread_count = 1
                continue
            rec.thread_count = self.with_context(active_test=False).search_count([
                ("thread_root_id", "=", rec.thread_root_id),
                ("company_id", "=", rec.company_id.id),
            ])

    # ------------------------------------------------------------------
    # Needaction (menu badge for unread count)
    # ------------------------------------------------------------------
    @api.model
    def _needaction_domain_get(self):
        return [("status", "=", "new")]

    # ------------------------------------------------------------------
    # Auto mark-as-read on form open
    # ------------------------------------------------------------------
    def web_read(self, specification):
        result = super().web_read(specification)
        new_recs = self.filtered(lambda r: r.status == "new")
        if new_recs:
            new_recs.write({"status": "read"})
        return result

    # ------------------------------------------------------------------
    # Auto-replied: when an outbound row is created with in_reply_to set,
    # flip the matching inbound row's status to 'replied'.
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.direction != "out" or not rec.in_reply_to:
                continue
            parent = self.search([
                ("message_id_header", "=", rec.in_reply_to),
                ("direction", "=", "in"),
                ("status", "in", ("new", "read")),
                ("company_id", "=", rec.company_id.id),
            ], limit=1)
            if parent:
                parent.write({"status": "replied"})
        return records

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_mark_read(self):
        self.filtered(lambda r: r.status == "new").write({"status": "read"})

    def action_mark_replied(self):
        self.write({"status": "replied"})

    def action_archive(self):
        self.write({"status": "archived", "active": False})

    def action_open_source_record(self):
        self.ensure_one()
        if self.res_model and self.res_id:
            self.env[self.res_model].check_access_rights("read")
            self.env[self.res_model].browse(self.res_id).check_access_rule("read")
            return {
                "type": "ir.actions.act_window",
                "res_model": self.res_model,
                "res_id": self.res_id,
                "views": [[False, "form"]],
                "target": "current",
            }

    def action_reply(self):
        """Open mail composer pre-filled to reply on the source record."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return self.action_reply_standalone()

        # Auto mark as replied
        if self.status in ("new", "read"):
            self.write({"status": "replied"})

        # Build recipient list from original sender
        partner_ids = []
        if self.direction == "in" and self.email_from:
            partner = self.env["res.partner"].search(
                [("email", "=ilike", self.email_from.strip())], limit=1
            )
            if not partner:
                partner = self.env["res.partner"].search(
                    [("email_normalized", "=", self.email_from.strip().lower())],
                    limit=1,
                )
            if partner:
                partner_ids = partner.ids
        elif self.partner_id:
            partner_ids = [self.partner_id.id]

        subject = self.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Build quoted reply body via mail_quoted_reply pattern
        quote_body = ""
        if self.mail_message_id:
            quote_body = self.mail_message_id._prep_quoted_reply_body()

        ctx = {
            "default_model": self.res_model,
            "default_res_ids": [self.res_id],
            "default_composition_mode": "comment",
            "default_partner_ids": partner_ids,
            "default_subject": subject,
            "default_notify": True,
            "force_email": True,
            "is_quoted_reply": True,
            "quote_body": quote_body,
        }

        action = self.env["ir.actions.actions"]._for_xml_id(
            "mail.action_email_compose_message_wizard"
        )
        action["context"] = ctx
        return action

    def action_reply_standalone(self):
        """Fallback reply when no source record: open source record search."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Aucun enregistrement li\u00e9",
                "message": "Ce courriel n'est pas li\u00e9 \u00e0 un enregistrement. "
                           "Utilisez le bouton \u00ab\u00a0Enregistrement\u00a0\u00bb pour le lier d'abord.",
                "type": "warning",
                "sticky": False,
            },
        }

    def action_open_in_chatter(self):
        """Navigate to the source record form (chatter visible)."""
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        self.env[self.res_model].check_access_rights("read")
        self.env[self.res_model].browse(self.res_id).check_access_rule("read")
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "views": [[False, "form"]],
            "target": "current",
        }

    def action_open_conversation(self):
        """Open the list view filtered by RFC 2822 thread root.

        When the row has no thread_root_id, fall back to subject-prefix
        matching (Re:/Fwd:-stripped) for the same partner.
        """
        self.ensure_one()
        domain = []
        if self.thread_root_id:
            domain = [("thread_root_id", "=", self.thread_root_id)]
        else:
            cleaned = re.sub(r"^(re|fwd|tr|fw)\s*:\s*", "", (self.subject or ""), flags=re.IGNORECASE).strip()
            if cleaned and self.partner_id:
                domain = [
                    ("subject", "ilike", cleaned),
                    ("partner_id", "=", self.partner_id.id),
                ]
        return {
            "type": "ir.actions.act_window",
            "name": f"Fil : {(self.subject or '')[:60]}",
            "res_model": "bf.email",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"search_default_group_date": 0},
        }

    def action_reroute(self):
        """Open the reroute wizard pre-filled with selected bf.email rows."""
        if not self:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Importer dans un chatter",
            "res_model": "bf.email.reroute",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_bf_email_ids": [(6, 0, self.ids)],
            },
        }

    # ------------------------------------------------------------------
    # Cron: incremental sync from mail.message
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_emails(self):
        """Sync new mail.message records of type 'email' into bf.email.

        Watermark uses ``create_date`` (insertion time), not ``date``
        (sender's send time). Backdated imports (manual IMAP imports,
        forwarded emails with original send dates) would otherwise fall
        below the watermark and never get picked up.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        last_sync = ICP.get_param("bf_email.last_sync_date", "2000-01-01 00:00:00")
        batch_size = int(ICP.get_param("bf_email.sync_batch_size", "200"))

        messages = self.env["mail.message"].sudo().search(
            [
                ("create_date", ">", last_sync),
                "|",
                    ("message_type", "=", "email"),
                    "&",
                        ("message_type", "=", "comment"),
                        ("notification_ids.notification_type", "=", "email"),
            ],
            limit=batch_size,
            order="create_date asc",
        )

        if not messages:
            return

        created = 0
        skipped = 0
        latest_date = last_sync

        for msg in messages:
            msg_date_str = fields.Datetime.to_string(msg.create_date)
            if msg_date_str > latest_date:
                latest_date = msg_date_str

            if not self._should_sync(msg):
                skipped += 1
                continue

            vals = self._prepare_email_vals(msg)
            if not vals:
                skipped += 1
                continue

            try:
                with self.env.cr.savepoint():
                    self.with_context(
                        mail_create_nosubscribe=True,
                        tracking_disable=True,
                    ).create(vals)
                created += 1
            except Exception:
                _logger.warning(
                    "Failed to sync mail.message %s", msg.id, exc_info=True
                )
                skipped += 1

        ICP.set_param("bf_email.last_sync_date", latest_date)
        _logger.info(
            "bf.email sync: %d created, %d skipped (from %d messages)",
            created,
            skipped,
            len(messages),
        )

    @api.model
    def _should_sync(self, msg):
        """Check if a mail.message should be synced (dedup).

        Three outcomes:
        - Returns ``False`` if a non-orphan row already represents this
          Message-ID (true duplicate, skip).
        - Returns ``False`` after PROMOTING an IMAP-orphan row (source='imap',
          ``mail_message_id=False``) to a chatter row by linking the new
          ``mail.message``. Preserves the original UNIQUE row.
        - Returns ``True`` if no row exists yet — caller should ``create``.

        Includes archived records via active_test=False — the UNIQUE
        constraint on (message_id_header, company_id) spans all rows
        regardless of active, so we must match that scope to avoid
        IntegrityError when a partner later archives and we re-sync.
        """
        if not msg.message_id:
            return True

        existing = self.with_context(active_test=False).search([
            ("message_id_header", "=", msg.message_id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if not existing:
            return True

        # Promote IMAP-orphan to chatter row if a real mail.message just landed.
        if existing.source == "imap" and not existing.mail_message_id:
            try:
                vals = self._prepare_email_vals(msg)
                if vals:
                    promote = {
                        "mail_message_id": msg.id,
                        "res_model": vals.get("res_model") or False,
                        "res_id": vals.get("res_id") or False,
                        "record_name": vals.get("record_name") or "",
                        "source": vals.get("source") or "gateway",
                        "partner_id": vals.get("partner_id") or existing.partner_id.id or False,
                        "author_id": vals.get("author_id") or existing.author_id.id or False,
                        "email_to": vals.get("email_to") or existing.email_to or "",
                        "email_cc": vals.get("email_cc") or existing.email_cc or "",
                        "has_attachments": vals.get("has_attachments") or existing.has_attachments,
                        "attachment_count": vals.get("attachment_count") or existing.attachment_count,
                        "in_reply_to": vals.get("in_reply_to") or existing.in_reply_to or False,
                        "thread_root_id": vals.get("thread_root_id") or existing.thread_root_id or False,
                    }
                    existing.write(promote)
                    _logger.info(
                        "bf.email: promoted IMAP-orphan #%s to chatter (mail.message #%s)",
                        existing.id, msg.id,
                    )
            except Exception:
                _logger.warning(
                    "bf.email: failed to promote orphan #%s for mail.message #%s",
                    existing.id, msg.id, exc_info=True,
                )
        return False

    @api.model
    def _prepare_email_vals(self, msg):
        """Build bf.email values dict from a mail.message record."""
        direction = self._detect_direction(msg)

        record_name = ""
        if msg.res_id and msg.model:
            try:
                record = self.env[msg.model].sudo().browse(msg.res_id)
                if record.exists():
                    record_name = record.display_name or ""
            except Exception:
                pass

        attachment_ids = msg.attachment_ids

        # email_to: use mail.message.email_to if available, else build from partners
        email_to_str = ""
        if hasattr(msg, "email_to") and msg.email_to:
            email_to_str = msg.email_to
        elif msg.partner_ids:
            email_to_str = ", ".join(
                p.email for p in msg.partner_ids if p.email
            )

        # email_cc: use mail.message.email_cc if available
        email_cc_str = ""
        if hasattr(msg, "email_cc") and msg.email_cc:
            email_cc_str = msg.email_cc

        # partner_id: main external contact
        if direction == "in":
            partner = msg.author_id or False
        else:
            # For outbound: first non-internal recipient
            partner = False
            for p in msg.partner_ids:
                if not p.user_ids:
                    partner = p
                    break
            if not partner and msg.partner_ids:
                partner = msg.partner_ids[0]

        # Drop partner / author refs whose row no longer exists. mail.message
        # holds raw int FKs and Odoo doesn't auto-null them when a partner is
        # deleted, so blindly forwarding the id would trip the bf_email FK.
        partner_id = partner.id if partner and partner.exists() else False
        author_id = msg.author_id.id if msg.author_id and msg.author_id.exists() else False

        in_reply_to = msg.parent_id.message_id if msg.parent_id else False
        # Walk parent chain for thread root; fall back to in_reply_to or self.
        thread_root = msg.message_id or False
        cursor = msg.parent_id
        seen = set()
        while cursor and cursor.id not in seen and cursor.message_id:
            seen.add(cursor.id)
            thread_root = cursor.message_id
            cursor = cursor.parent_id

        return {
            "date": msg.date,
            "email_from": msg.email_from or "",
            "email_to": email_to_str,
            "email_cc": email_cc_str,
            "subject": msg.subject or "",
            "direction": direction,
            "source": "gateway" if msg.message_type == "email" else "chatter",
            "message_id_header": msg.message_id or False,
            "in_reply_to": in_reply_to,
            "thread_root_id": thread_root,
            "mail_message_id": msg.id,
            "res_model": msg.model or False,
            "res_id": msg.res_id or False,
            "record_name": record_name[:200],
            "partner_id": partner_id,
            "author_id": author_id,
            "has_attachments": bool(attachment_ids),
            "attachment_count": len(attachment_ids),
            "company_id": self.env.company.id,
        }

    @api.model
    def _detect_direction(self, msg):
        """Detect if a message is inbound or outbound."""
        if msg.author_id and msg.author_id.user_ids:
            return "out"
        return "in"

    # ------------------------------------------------------------------
    # Cron: incremental sync from IMAP (Inbox + Sent live)
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_imap(self):
        """Pull new messages directly from IMAP into bf.email as orphan rows.

        Mirrors ``_cron_sync_emails`` but reads IMAP rather than mail.message.
        Each folder has its own UID watermark advanced after a successful
        commit. Dedup is handled by the UNIQUE(message_id_header) constraint
        plus an explicit search before insert.

        Configured via ir.config_parameter:
        - bf_email.imap_host, bf_email.imap_port, bf_email.imap_user, bf_email.imap_password
        - bf_email.imap_last_uid_inbox, bf_email.imap_last_uid_sent
        - bf_email.imap_batch_size (default 100)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        host = ICP.get_param("bf_email.imap_host")
        user = ICP.get_param("bf_email.imap_user")
        password = ICP.get_param("bf_email.imap_password")
        if not (host and user and password):
            _logger.debug("bf.email: IMAP credentials not configured, skipping cron")
            return
        port = int(ICP.get_param("bf_email.imap_port", "993"))
        batch_size = int(ICP.get_param("bf_email.imap_batch_size", "100"))

        try:
            conn = bf_email_imap.open_connection(host, port, user, password)
        except bf_email_imap.ImapConnectionError as exc:
            _logger.warning("bf.email IMAP cron: %s", exc)
            return

        try:
            for folder in bf_email_imap.DEFAULT_LIVE_FOLDERS:
                self._sync_imap_folder(conn, folder, user, batch_size, ICP)
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    @api.model
    def _sync_imap_folder(self, conn, folder, configured_user, batch_size, ICP):
        """Pull ``batch_size`` new UIDs from one folder, advance watermark."""
        watermark_key = f"bf_email.imap_last_uid_{folder.lower().replace('/', '_')}"
        last_uid = ICP.get_param(watermark_key, "0")

        if not bf_email_imap.select_folder(conn, folder, readonly=True):
            _logger.info("bf.email IMAP: folder %r not selectable, skipping", folder)
            return

        uids = bf_email_imap.search_uids_above(conn, last_uid)
        if not uids:
            return
        uids = uids[:batch_size]

        created = 0
        skipped = 0
        latest_uid = int(last_uid) if last_uid else 0
        for uid in uids:
            raw = bf_email_imap.fetch_rfc822(conn, uid)
            if not raw:
                skipped += 1
                continue
            try:
                with self.env.cr.savepoint():
                    if self._ingest_rfc822(raw, uid, folder, configured_user):
                        created += 1
                    else:
                        skipped += 1
            except Exception:
                _logger.warning(
                    "bf.email IMAP: failed to ingest UID %s in %r",
                    uid, folder, exc_info=True,
                )
                skipped += 1
            if uid > latest_uid:
                latest_uid = uid

        if latest_uid > (int(last_uid) if last_uid else 0):
            ICP.set_param(watermark_key, str(latest_uid))
        _logger.info(
            "bf.email IMAP %s: %d created, %d skipped (UIDs %d-%d)",
            folder, created, skipped, uids[0], uids[-1],
        )

    @api.model
    def _ingest_rfc822(self, raw_bytes, uid, folder, configured_user):
        """Parse one RFC 2822 message and create an orphan bf.email row.

        Returns ``True`` when a row was created, ``False`` when skipped
        (dedup on Message-ID, or unparseable).
        """
        msg = bf_email_imap.parse_rfc822(raw_bytes)
        message_id = str(msg.get("Message-ID", "")).strip() or False
        if not message_id:
            _logger.info(
                "bf.email IMAP: UID %s in %r has no Message-ID, skipping",
                uid, folder,
            )
            return False

        existing = self.with_context(active_test=False).search([
            ("message_id_header", "=", message_id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if existing:
            # Already represented (chatter, gateway, or earlier IMAP poll).
            # Backfill the IMAP UID/folder info on a pure orphan if missing.
            if existing.source == "imap" and not existing.imap_uid:
                existing.write({
                    "imap_uid": str(uid),
                    "imap_folder": folder,
                })
            return False

        # Internal Odoo wins: if a mail.message with the same Message-ID
        # already exists (chatter or gateway projected previously), link
        # to it instead of creating an IMAP orphan.
        existing_msg = self.env["mail.message"].sudo().search([
            ("message_id", "=", message_id),
        ], limit=1)
        if existing_msg:
            chatter_vals = self._prepare_email_vals(existing_msg)
            if chatter_vals:
                # Augment with IMAP traceability — folder/UID kept for audit.
                chatter_vals.update({
                    "imap_uid": str(uid),
                    "imap_folder": folder,
                })
                self.with_context(
                    mail_create_nosubscribe=True,
                    tracking_disable=True,
                ).create(chatter_vals)
                return True

        vals = self._prepare_imap_email_vals(msg, raw_bytes, uid, folder, configured_user)
        if not vals:
            return False
        self.with_context(
            mail_create_nosubscribe=True,
            tracking_disable=True,
        ).create(vals)
        return True

    @api.model
    def _prepare_imap_email_vals(self, msg, raw_bytes, uid, folder, configured_user):
        """Build a bf.email vals dict from a parsed RFC 2822 message."""
        message_id = str(msg.get("Message-ID", "")).strip() or False
        subject = str(msg.get("Subject", ""))
        email_from = str(msg.get("From", ""))
        email_to = str(msg.get("To", ""))
        email_cc = str(msg.get("Cc", ""))
        date_str = bf_email_imap.parse_date(msg.get("Date"))
        in_reply_to, thread_root = bf_email_imap.parse_thread_headers(msg)

        # Direction: Sent folder = out; otherwise inbound unless From is us.
        if folder.lower() == "sent" or bf_email_imap.is_outbound_address(
            email_from, configured_user
        ):
            direction = "out"
        else:
            direction = "in"

        # Resolve partner from the external party's address.
        external_addr = email_to if direction == "out" else email_from
        partner = self._resolve_partner_by_email(external_addr)
        author = self._resolve_partner_by_email(email_from)

        attachments = bf_email_imap.extract_attachments(msg)

        return {
            "date": date_str or fields.Datetime.now(),
            "email_from": email_from,
            "email_to": email_to,
            "email_cc": email_cc,
            "subject": subject,
            "direction": direction,
            "source": "imap",
            "message_id_header": message_id,
            "in_reply_to": in_reply_to or False,
            "thread_root_id": thread_root or message_id,
            "mail_message_id": False,
            "res_model": False,
            "res_id": False,
            "record_name": "",
            "partner_id": partner.id if partner else False,
            "author_id": author.id if author else False,
            "has_attachments": bool(attachments),
            "attachment_count": len(attachments),
            "company_id": self.env.company.id,
            "imap_uid": str(uid),
            "imap_folder": folder,
            "raw_rfc822": bf_email_imap.attachment_to_b64(raw_bytes),
        }

    @api.model
    def _resolve_partner_by_email(self, email_str):
        """Find a res.partner whose ``email`` matches the address, or False."""
        if not email_str:
            return self.env["res.partner"].browse()
        _name, bare = parseaddr(email_str)
        if not bare:
            return self.env["res.partner"].browse()
        bare = bare.strip()
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("email", "=ilike", bare)], limit=1)
        if partner:
            return partner
        return Partner.search(
            [("email_normalized", "=", bare.lower())], limit=1
        )

    # ------------------------------------------------------------------
    # Manual sync trigger
    # ------------------------------------------------------------------
    @api.model
    def action_sync_now(self):
        """Run the sync cron immediately and show a notification with results.

        Iterates until no new messages remain (or a safety cap is reached),
        so a single click covers any backlog that exceeds the batch size.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        before = ICP.get_param("bf_email.last_sync_date", "2000-01-01 00:00:00")
        before_count = self.search_count([])

        max_iterations = 50
        for _ in range(max_iterations):
            last_before = ICP.get_param(
                "bf_email.last_sync_date", "2000-01-01 00:00:00"
            )
            self._cron_sync_emails()
            last_after = ICP.get_param(
                "bf_email.last_sync_date", "2000-01-01 00:00:00"
            )
            if last_after == last_before:
                break

        after_count = self.search_count([])
        created = after_count - before_count
        after = ICP.get_param("bf_email.last_sync_date", before)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Synchronisation termin\u00e9e",
                "message": (
                    f"{created} nouveau(x) courriel(s) import\u00e9(s).\n"
                    f"Dernier message trait\u00e9\u00a0: {after}"
                ),
                "type": "success" if created else "info",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    # ------------------------------------------------------------------
    # Reminder / Activity
    # ------------------------------------------------------------------
    def action_create_reminder(self):
        """Open the activity scheduling wizard on this email record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.activity",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
                "default_summary": self.subject or "",
            },
        }

    # ------------------------------------------------------------------
    # Data repair
    # ------------------------------------------------------------------
    def action_recompute_from_source(self):
        """Re-read email_to, email_cc, partner_id from mail.message source.

        Call on existing records to fix data synced with the old logic.
        Also triggers recompute of category via partner_id change.
        """
        updated = 0
        for rec in self.filtered("mail_message_id"):
            msg = rec.mail_message_id.sudo()
            direction = rec.direction

            # email_to
            email_to_str = ""
            if hasattr(msg, "email_to") and msg.email_to:
                email_to_str = msg.email_to
            elif msg.partner_ids:
                email_to_str = ", ".join(
                    p.email for p in msg.partner_ids if p.email
                )

            # email_cc
            email_cc_str = ""
            if hasattr(msg, "email_cc") and msg.email_cc:
                email_cc_str = msg.email_cc

            # partner_id
            if direction == "in":
                partner = msg.author_id or False
            else:
                partner = False
                for p in msg.partner_ids:
                    if not p.user_ids:
                        partner = p
                        break
                if not partner and msg.partner_ids:
                    partner = msg.partner_ids[0]

            vals = {}
            if email_to_str != (rec.email_to or ""):
                vals["email_to"] = email_to_str
            if email_cc_str != (rec.email_cc or ""):
                vals["email_cc"] = email_cc_str
            new_partner_id = partner.id if partner else False
            if new_partner_id != rec.partner_id.id:
                vals["partner_id"] = new_partner_id

            if vals:
                rec.write(vals)
                updated += 1

        _logger.info(
            "bf.email recompute_from_source: %d/%d records updated",
            updated, len(self),
        )
        return updated
