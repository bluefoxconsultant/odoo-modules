from odoo import api, fields, models


class CalendarEvent(models.Model):
    """Extension de calendar.event pour le lien avec les comptes rendus."""
    _inherit = 'calendar.event'

    meeting_record_ids = fields.One2many(
        'meeting.record',
        'calendar_event_id',
        string='Comptes rendus (tous)',
    )
    meeting_record_id = fields.Many2one(
        'meeting.record',
        string='Compte rendu',
        compute='_compute_meeting_record_id',
    )
    meeting_record_count = fields.Integer(
        string='Comptes rendus',
        compute='_compute_meeting_record_id',
    )

    meeting_agenda_ids = fields.One2many(
        'meeting.agenda',
        'calendar_event_id',
        string='Ordres du jour (tous)',
    )
    meeting_agenda_id = fields.Many2one(
        'meeting.agenda',
        string='Ordre du jour',
        compute='_compute_meeting_agenda_id',
    )
    meeting_agenda_count = fields.Integer(
        string='Ordres du jour',
        compute='_compute_meeting_agenda_id',
    )

    bf_skip_agenda = fields.Boolean(
        string='Sans ordre du jour formel',
        help="Cocher pour les rencontres internes courtes ou récurrentes qui ne "
             "nécessitent pas d'ordre du jour formel.",
    )
    bf_needs_agenda = fields.Boolean(
        string="Besoin d'un ordre du jour",
        compute='_compute_bf_needs_agenda',
        search='_search_bf_needs_agenda',
        help="Vrai si la rencontre est à venir, n'a pas d'ordre du jour lié et "
             "n'est pas marquée comme dispensée.",
    )

    @api.depends('meeting_record_ids')
    def _compute_meeting_record_id(self):
        for event in self:
            event.meeting_record_id = event.meeting_record_ids[:1]
            event.meeting_record_count = len(event.meeting_record_ids)

    @api.depends('meeting_agenda_ids')
    def _compute_meeting_agenda_id(self):
        for event in self:
            event.meeting_agenda_id = event.meeting_agenda_ids[:1]
            event.meeting_agenda_count = len(event.meeting_agenda_ids)

    @api.depends('meeting_agenda_ids', 'bf_skip_agenda', 'start')
    def _compute_bf_needs_agenda(self):
        now = fields.Datetime.now()
        for event in self:
            event.bf_needs_agenda = bool(
                not event.bf_skip_agenda
                and not event.meeting_agenda_ids
                and event.start
                and event.start >= now
            )

    def _search_bf_needs_agenda(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return [('id', '=', False)]
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        now = fields.Datetime.now()
        domain = [
            ('bf_skip_agenda', '=', False),
            ('meeting_agenda_ids', '=', False),
            ('start', '>=', now),
        ]
        if positive:
            return domain
        return ['!'] + domain

    def action_create_meeting_record(self):
        """Créer un compte rendu à partir de cet événement calendrier.

        Si l'événement a déjà un OdJ lié, le rattacher au compte rendu pour
        unifier la référence à la même rencontre.
        """
        self.ensure_one()
        partner_ids = self.attendee_ids.mapped('partner_id').ids
        duration_minutes = int((self.duration or 0) * 60)
        agenda = self.meeting_agenda_id

        vals = {
            'date': self.start,
            'room_name': self.name,
            'location': self.location or '',
            'duration_minutes': duration_minutes,
            'calendar_event_id': self.id,
            'participant_ids': [(6, 0, partner_ids)],
            'organizer_id': self.user_id.id if self.user_id else False,
        }
        if agenda and agenda.project_id:
            vals['project_id'] = agenda.project_id.id
        record = self.env['meeting.record'].create(vals)

        if agenda and not agenda.meeting_record_id:
            agenda.write({
                'meeting_record_id': record.id,
                'state': 'done' if agenda.state in ('draft', 'confirmed') else agenda.state,
            })

        return {
            'type': 'ir.actions.act_window',
            'name': record.name,
            'res_model': 'meeting.record',
            'res_id': record.id,
            'views': [[False, 'form']],
        }

    def action_create_meeting_agenda(self):
        """Créer un OdJ rattaché à cet événement (le projet reste à choisir)."""
        self.ensure_one()
        partner_ids = self.attendee_ids.mapped('partner_id').ids
        duration_minutes = int((self.duration or 0) * 60)
        ctx = {
            'default_calendar_event_id': self.id,
            'default_date': self.start,
            'default_duration_planned': duration_minutes,
            'default_location': self.location or '',
            'default_participant_ids': [(6, 0, partner_ids)],
        }
        if self.user_id:
            ctx['default_organizer_id'] = self.user_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': "Nouvel ordre du jour",
            'res_model': 'meeting.agenda',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }

    def action_view_meeting_record(self):
        """Ouvrir le compte rendu lié."""
        self.ensure_one()
        if self.meeting_record_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.meeting_record_id.name,
                'res_model': 'meeting.record',
                'res_id': self.meeting_record_id.id,
                'views': [[False, 'form']],
            }

    def action_view_meeting_agenda(self):
        """Ouvrir l'OdJ lié."""
        self.ensure_one()
        if self.meeting_agenda_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.meeting_agenda_id.name,
                'res_model': 'meeting.agenda',
                'res_id': self.meeting_agenda_id.id,
                'views': [[False, 'form']],
            }
