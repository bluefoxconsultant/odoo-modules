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
        """Open wizard to post this SMS to a project task."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Poster sur une tâche",
            "res_model": "sms.archive.post.to.task.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_message_id": self.id,
            },
        }
