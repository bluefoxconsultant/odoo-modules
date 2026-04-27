import logging
import re
from datetime import timedelta

from odoo import api, fields, models, tools

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
        related="mail_message_id.body",
        readonly=True,
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
        ],
        string="Source",
        index=True,
        help="Origine du message\u00a0: passerelle courriel entrante/sortante "
             "ou commentaire post\u00e9 via le chatter et notifi\u00e9 par courriel.",
    )
    message_id_header = fields.Char(
        string="Message-ID",
        index=True,
        help="RFC 2822 Message-ID pour la d\u00e9duplication",
    )
    in_reply_to = fields.Char(
        string="In-Reply-To",
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
    @api.depends("mail_message_id.body")
    def _compute_body_preview(self):
        for rec in self:
            body = rec.mail_message_id.body or ""
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

        Includes archived records via active_test=False — the UNIQUE
        constraint on (message_id_header, company_id) spans all rows
        regardless of active, so we must match that scope to avoid
        IntegrityError when a partner later archives and we re-sync.
        """
        if msg.message_id:
            existing = self.with_context(active_test=False).search_count([
                ("message_id_header", "=", msg.message_id),
                ("company_id", "=", self.env.company.id),
            ])
            if existing:
                return False
        return True

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

        return {
            "date": msg.date,
            "email_from": msg.email_from or "",
            "email_to": email_to_str,
            "email_cc": email_cc_str,
            "subject": msg.subject or "",
            "direction": direction,
            "source": "gateway" if msg.message_type == "email" else "chatter",
            "message_id_header": msg.message_id or False,
            "in_reply_to": msg.parent_id.message_id if msg.parent_id else False,
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
