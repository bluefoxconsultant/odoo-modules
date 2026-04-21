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

    @api.depends('meeting_record_ids')
    def _compute_meeting_record_id(self):
        for event in self:
            event.meeting_record_id = event.meeting_record_ids[:1]
            event.meeting_record_count = len(event.meeting_record_ids)

    def action_create_meeting_record(self):
        """Créer un compte rendu à partir de cet événement calendrier."""
        self.ensure_one()
        # Collect attendee partners
        partner_ids = self.attendee_ids.mapped('partner_id').ids

        # Compute duration in minutes
        duration_minutes = int((self.duration or 0) * 60)

        vals = {
            'date': self.start,
            'room_name': self.name,
            'location': self.location or '',
            'duration_minutes': duration_minutes,
            'calendar_event_id': self.id,
            'participant_ids': [(6, 0, partner_ids)],
            'organizer_id': self.user_id.id if self.user_id else False,
        }
        record = self.env['meeting.record'].create(vals)

        return {
            'type': 'ir.actions.act_window',
            'name': record.name,
            'res_model': 'meeting.record',
            'res_id': record.id,
            'views': [[False, 'form']],
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
