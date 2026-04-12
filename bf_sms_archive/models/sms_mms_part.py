import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SmsArchiveMmsPart(models.Model):
    _name = "sms.archive.mms.part"
    _description = "Pièce jointe MMS"
    _order = "sequence, id"

    message_id = fields.Many2one(
        comodel_name="sms.archive.message",
        string="Message",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(
        string="Séquence",
        default=0,
    )
    content_type = fields.Char(
        string="Type MIME",
    )
    filename = fields.Char(
        string="Nom de fichier",
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Fichier",
        ondelete="cascade",
    )
    text_content = fields.Text(
        string="Contenu texte",
        help="Pour les parties text/plain",
    )
    owner_id = fields.Many2one(
        related="message_id.owner_id",
        store=True,
        index=True,
        string="Propriétaire",
    )

    is_image = fields.Boolean(
        compute="_compute_is_image",
        store=True,
    )

    @api.depends("content_type")
    def _compute_is_image(self):
        for part in self:
            part.is_image = (part.content_type or "").startswith("image/")
