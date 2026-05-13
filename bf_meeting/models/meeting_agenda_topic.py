from odoo import fields, models


class MeetingAgendaTopic(models.Model):
    """Sujet planifié dans un ordre du jour."""
    _name = 'meeting.agenda.topic'
    _description = "Sujet d'ordre du jour"
    _order = 'agenda_id, sequence, id'

    agenda_id = fields.Many2one(
        'meeting.agenda',
        string='Ordre du jour',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string='Ordre',
        default=10,
    )
    name = fields.Char(
        string='Sujet',
        required=True,
    )
    duration_planned = fields.Integer(
        string='Durée (min)',
        help='Temps alloué pour ce sujet en minutes.',
    )
    presenter_id = fields.Many2one(
        'res.partner',
        string='Intervenant',
    )
    description = fields.Html(
        string='Notes / Contexte',
        sanitize_style=True,
    )
    live_notes_html = fields.Html(
        string='Notes (rencontre)',
        sanitize_style=True,
        help="Prise de notes en direct pendant la rencontre. N'apparaît pas "
             "dans le PDF de l'ordre du jour ; sera transféré dans le compte "
             "rendu à sa création.",
    )
