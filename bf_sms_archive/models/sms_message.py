import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# SMS Backup & Restore type mapping
_SMS_TYPE_MAP = {
    "1": "in",     # Received
    "2": "out",    # Sent
    "3": "draft",  # Draft
}

_DIRECTION_LABELS = {
    "in": "←",
    "out": "→",
    "draft": "~",
}


class SmsArchiveMessage(models.Model):
    _name = "sms.archive.message"
    _description = "Message SMS archivé"
    _order = "date_sent asc, id asc"

    thread_id = fields.Many2one(
        comodel_name="sms.archive.thread",
        string="Conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    message_hash = fields.Char(
        string="Hash de dédoublonnage",
        size=64,
        required=True,
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("in", "Reçu"),
            ("out", "Envoyé"),
            ("draft", "Brouillon"),
        ],
        string="Direction",
        required=True,
    )
    body = fields.Text(
        string="Contenu",
    )
    date_sent = fields.Datetime(
        string="Date",
        required=True,
        index=True,
    )
    date_sent_ms = fields.Char(
        string="Timestamp (ms)",
        help="Timestamp brut en millisecondes conservé du XML",
    )
    is_mms = fields.Boolean(
        string="MMS",
        default=False,
    )
    contact_name = fields.Char(
        string="Nom du contact",
    )
    owner_id = fields.Many2one(
        related="thread_id.owner_id",
        store=True,
        index=True,
        string="Propriétaire",
    )
    import_batch_id = fields.Char(
        string="Lot d'import",
        help="Identifiant backup_set du fichier XML",
    )
    mms_part_ids = fields.One2many(
        comodel_name="sms.archive.mms.part",
        inverse_name="message_id",
        string="Pièces jointes MMS",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
    )

    _sql_constraints = [
        (
            "hash_uniq",
            "UNIQUE(message_hash)",
            "Ce message existe déjà (hash dupliqué).",
        ),
    ]

    @api.depends("direction", "thread_id.contact_name", "date_sent", "body")
    def _compute_display_name(self):
        for msg in self:
            arrow = _DIRECTION_LABELS.get(msg.direction, "?")
            contact = msg.thread_id.contact_name or msg.thread_id.phone_normalized or "?"
            dt = str(msg.date_sent)[:16] if msg.date_sent else ""
            preview = (msg.body or "")[:40]
            if len(msg.body or "") > 40:
                preview += "…"
            msg.display_name = f"{arrow} {contact} — {dt} — {preview}"

    def action_post_to_task(self):
        """Open wizard to post the selected SMS message(s) to a project task."""
        if not self:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Poster sur une tâche",
            "res_model": "sms.archive.post.to.task.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_message_ids": [(6, 0, self.ids)],
            },
        }

    def action_export_csv(self):
        """Export the selected messages as a single CSV file."""
        if not self:
            return False
        filename = f"sms_selection_{fields.Date.today()}.csv"
        res_id = self.thread_id.id if len(self.thread_id) == 1 else False
        return self.env["sms.archive.thread"]._build_csv_download(
            self, filename=filename, res_id=res_id,
        )

    def action_export_xml(self):
        """Export the selected messages as a single SMS Backup & Restore XML file."""
        if not self:
            return False
        filename = f"sms_selection_{fields.Date.today()}.xml"
        res_id = self.thread_id.id if len(self.thread_id) == 1 else False
        return self.env["sms.archive.thread"]._build_xml_download(
            self, filename=filename, res_id=res_id,
        )

    def action_export_pdf(self):
        """Print the selected messages as a branded PDF."""
        if not self:
            return False
        return self.env.ref(
            "bf_sms_archive.action_report_sms_messages"
        ).report_action(self)

    def _get_messages_report_data(self):
        """Prepare data for the per-message PDF report (binding_model: sms.archive.message)."""
        Thread = self.env["sms.archive.thread"]
        data = Thread._build_shared_report_data()

        # Group selected messages by thread, preserving thread order by last activity
        threads = self.thread_id.sorted(
            lambda t: (t.last_message_date or fields.Datetime.from_string("1970-01-01")),
            reverse=True,
        )
        groups = []
        for thread in threads:
            thread_msgs = self.filtered(lambda m, t=thread: m.thread_id.id == t.id)
            if thread_msgs:
                groups.append(Thread._build_thread_group(thread, thread_msgs))

        data["groups"] = groups
        data["total_count"] = sum(g["count"] for g in groups)
        data["thread_count"] = len(groups)
        return data
