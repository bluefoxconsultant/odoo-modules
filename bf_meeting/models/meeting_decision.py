from odoo import fields, models


class MeetingDecision(models.Model):
    """Décision prise lors d'une réunion."""
    _name = 'meeting.decision'
    _description = 'Décision de réunion'
    _order = 'meeting_id, sequence, id'

    meeting_id = fields.Many2one(
        'meeting.record',
        string='Réunion',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Ordre',
        default=10,
    )
    name = fields.Char(
        string='Décision',
        required=True,
    )
    description = fields.Html(
        string='Contexte',
        sanitize_style=True,
    )
    decision_maker_id = fields.Many2one(
        'res.partner',
        string='Décideur',
    )
    knowledge_item_id = fields.Many2one(
        'project.knowledge.item',
        string='Élément de matrice',
    )
