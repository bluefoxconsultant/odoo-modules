import json
import logging

from markupsafe import Markup, escape

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MeetingRecord(models.Model):
    """Compte rendu structuré d'une réunion."""
    _name = 'meeting.record'
    _description = 'Compte rendu de réunion'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Titre',
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Projet',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='project_id.partner_id',
        store=True,
        readonly=True,
    )
    date = fields.Datetime(
        string='Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    duration_minutes = fields.Integer(
        string='Durée (minutes)',
    )
    room_name = fields.Char(
        string='Salon / Titre',
        tracking=True,
    )
    location = fields.Char(
        string='Lieu',
    )
    series_name = fields.Char(
        string='Série',
        help='Nom de la série récurrente (ex. Statutaire BSI)',
        index=True,
    )
    organizer_id = fields.Many2one(
        'res.users',
        string='Organisateur',
    )
    participant_ids = fields.Many2many(
        'res.partner',
        'meeting_record_participant_rel',
        'meeting_id',
        'partner_id',
        string='Participants',
    )
    invited_ids = fields.Many2many(
        'res.partner',
        'meeting_record_invited_rel',
        'meeting_id',
        'partner_id',
        string='Invités',
    )

    # Content
    summary = fields.Text(
        string='Résumé exécutif',
    )
    structured_notes_json = fields.Text(
        string='Notes structurées (JSON)',
    )
    notes_html = fields.Html(
        string='Notes',
        compute='_compute_notes_html',
        store=True,
        sanitize_style=True,
    )
    verbatim = fields.Text(
        string='Transcription brute',
    )
    verbatim_html = fields.Html(
        string='Transcription HTML',
        sanitize_style=True,
    )
    open_questions_html = fields.Html(
        string='Questions ouvertes',
        compute='_compute_notes_html',
        store=True,
        sanitize_style=True,
    )

    # Relations
    decision_ids = fields.One2many(
        'meeting.decision',
        'meeting_id',
        string='Décisions',
    )
    topic_ids = fields.One2many(
        'meeting.topic',
        'meeting_id',
        string='Sujets',
    )
    task_ids = fields.One2many(
        'project.task',
        'meeting_id',
        string="Éléments d'action",
    )
    task_count = fields.Integer(
        string='Nombre de tâches',
        compute='_compute_task_count',
    )
    knowledge_item_ids = fields.Many2many(
        'project.knowledge.item',
        'meeting_record_knowledge_item_rel',
        'meeting_id',
        'knowledge_item_id',
        string='Éléments de matrice',
    )
    knowledge_item_count = fields.Integer(
        string='Éléments de matrice',
        compute='_compute_knowledge_item_count',
    )

    # Report
    report_state = fields.Selection([
        ('draft', 'Brouillon'),
        ('reviewed', 'Révisé'),
        ('sent', 'Envoyé'),
    ], string='État du rapport', default='draft', tracking=True)
    report_sent_date = fields.Datetime(
        string="Date d'envoi",
        readonly=True,
    )
    review_notes = fields.Text(
        string='Notes de révision',
        help='Observations de la révision automatique ou manuelle du compte rendu.',
    )
    report_recipient_ids = fields.Many2many(
        'res.partner',
        'meeting_record_recipient_rel',
        'meeting_id',
        'partner_id',
        string='Destinataires',
    )
    partner_to_ids = fields.Char(
        string='IDs destinataires (technique)',
        compute='_compute_partner_to_ids',
        help="Utilisé par le modèle d'email, contourne la sandbox Jinja d'Odoo 18 qui refuse .mapped/.ids sur les recordsets.",
    )

    @api.depends('report_recipient_ids', 'participant_ids')
    def _compute_partner_to_ids(self):
        for rec in self:
            recipients = rec.report_recipient_ids or rec.participant_ids
            rec.partner_to_ids = ','.join(str(pid) for pid in recipients.ids)

    # Source
    source_filename = fields.Char(
        string='Fichier source',
    )
    source_nc_path = fields.Char(
        string='Chemin Nextcloud',
    )
    source_type = fields.Selection([
        ('audio', 'Audio'),
        ('text', 'Texte'),
        ('talk_recording', 'Enregistrement Talk'),
    ], string='Type de source')

    # Calendar & Agenda
    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Événement calendrier',
    )
    agenda_ids = fields.One2many(
        'meeting.agenda',
        'meeting_record_id',
        string='Ordres du jour liés',
    )
    agenda_id = fields.Many2one(
        'meeting.agenda',
        string='Ordre du jour',
        compute='_compute_agenda_id',
    )

    # Attendance
    attendance_ids = fields.One2many(
        'meeting.attendance',
        'meeting_id',
        string='Présences',
    )
    attendance_count = fields.Integer(
        string='Présences',
        compute='_compute_attendance_count',
    )
    present_count = fields.Integer(
        string='Présents',
        compute='_compute_attendance_count',
    )

    # Calendar view helper
    date_delay = fields.Float(
        string='Durée (heures)',
        compute='_compute_date_delay',
        store=True,
    )

    active = fields.Boolean(default=True)

    @api.depends('room_name', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.name:
                continue
            parts = []
            if rec.room_name:
                parts.append(rec.room_name)
            if rec.date:
                parts.append(rec.date.strftime('%Y-%m-%d'))
            rec.name = ' — '.join(parts) if parts else 'Nouveau compte rendu'

    @api.depends('structured_notes_json')
    def _compute_notes_html(self):
        for rec in self:
            if not rec.structured_notes_json:
                rec.notes_html = False
                rec.open_questions_html = False
                continue
            try:
                data = json.loads(rec.structured_notes_json)
            except (json.JSONDecodeError, TypeError):
                rec.notes_html = False
                rec.open_questions_html = False
                continue

            rec.notes_html = rec._render_notes_html(data)
            rec.open_questions_html = rec._render_open_questions_html(data)

    def _render_notes_html(self, data):
        """Render structured notes JSON to HTML. User-supplied strings are
        escaped to prevent XSS via crafted verbatims / structured notes."""
        parts = []

        topics = data.get('topics', [])
        for topic in topics:
            title = escape(topic.get('title', ''))
            parts.append(f'<h3>{title}</h3>')
            points = topic.get('points', [])
            if points:
                parts.append('<ul>')
                for point in points:
                    parts.append(f'<li>{escape(point)}</li>')
                parts.append('</ul>')

        deliverables = data.get('deliverables', [])
        if deliverables:
            parts.append('<h3>Livrables</h3><ul>')
            for d in deliverables:
                desc = d if isinstance(d, str) else d.get('description', str(d))
                parts.append(f'<li>{escape(desc)}</li>')
            parts.append('</ul>')

        return Markup(''.join(parts)) if parts else False

    def _render_open_questions_html(self, data):
        """Render open questions from JSON (escaped)."""
        questions = data.get('open_questions', [])
        if not questions:
            return False
        parts = ['<ul>']
        for q in questions:
            text = q if isinstance(q, str) else q.get('question', str(q))
            parts.append(f'<li>{escape(text)}</li>')
        parts.append('</ul>')
        return Markup(''.join(parts))

    @api.depends('duration_minutes')
    def _compute_date_delay(self):
        for rec in self:
            rec.date_delay = (rec.duration_minutes or 60) / 60.0

    @api.depends('agenda_ids')
    def _compute_agenda_id(self):
        for rec in self:
            rec.agenda_id = rec.agenda_ids[:1]

    @api.depends('attendance_ids', 'attendance_ids.status')
    def _compute_attendance_count(self):
        for rec in self:
            rec.attendance_count = len(rec.attendance_ids)
            rec.present_count = len(rec.attendance_ids.filtered(
                lambda a: a.status == 'present'
            ))

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('knowledge_item_ids')
    def _compute_knowledge_item_count(self):
        for rec in self:
            rec.knowledge_item_count = len(rec.knowledge_item_ids)

    def action_view_tasks(self):
        """Ouvrir les tâches liées à ce meeting."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Tâches — {self.name}",
            'res_model': 'project.task',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('meeting_id', '=', self.id)],
            'context': {
                'default_meeting_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }

    def action_view_knowledge_items(self):
        """Ouvrir les éléments de matrice liés."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f"Matrice — {self.name}",
            'res_model': 'project.knowledge.item',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('id', 'in', self.knowledge_item_ids.ids)],
        }

    def action_set_reviewed(self):
        """Marquer le rapport comme révisé."""
        self.write({'report_state': 'reviewed'})

    def action_send_report(self):
        """Ouvrir l'assistant d'envoi du rapport par courriel."""
        self.ensure_one()
        template = self.env.ref(
            'bf_meeting.meeting_report_mail_template', raise_if_not_found=False
        )
        ctx = {
            'default_model': 'meeting.record',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_light',
        }
        if template:
            ctx['default_template_id'] = template.id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Envoyer le rapport',
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }

    def action_send_report_direct(self):
        """Envoyer le rapport directement sans assistant de composition."""
        self.ensure_one()
        template = self.env.ref(
            'bf_meeting.meeting_report_mail_template', raise_if_not_found=False
        )
        if not template:
            _logger.warning("Meeting report mail template not found")
            return True

        # Auto-populate recipients from participants if empty
        if not self.report_recipient_ids and self.participant_ids:
            self.report_recipient_ids = self.participant_ids

        if not self.report_recipient_ids:
            _logger.warning("No recipients for meeting report %s", self.name)
            return True

        template.send_mail(self.id, force_send=True)
        self.write({
            'report_state': 'sent',
            'report_sent_date': fields.Datetime.now(),
        })
        return True

    def action_import_attendance(self):
        """Importer les participants comme présences."""
        self.ensure_one()
        existing = self.attendance_ids.mapped('partner_id')
        for partner in self.participant_ids:
            if partner not in existing:
                self.env['meeting.attendance'].create({
                    'meeting_id': self.id,
                    'partner_id': partner.id,
                    'status': 'present',
                })

    def action_view_agenda(self):
        """Ouvrir l'ordre du jour lié."""
        self.ensure_one()
        if self.agenda_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.agenda_id.name,
                'res_model': 'meeting.agenda',
                'res_id': self.agenda_id.id,
                'views': [[False, 'form']],
            }

    def action_view_calendar_event(self):
        """Ouvrir l'événement calendrier lié."""
        self.ensure_one()
        if self.calendar_event_id:
            return {
                'type': 'ir.actions.act_window',
                'name': self.calendar_event_id.name,
                'res_model': 'calendar.event',
                'res_id': self.calendar_event_id.id,
                'views': [[False, 'form']],
            }

    def _get_report_data(self):
        """Prepare data for the PDF report template."""
        self.ensure_one()
        data = {}
        if self.structured_notes_json:
            try:
                data = json.loads(self.structured_notes_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            'today': fields.Date.context_today(self).strftime('%Y-%m-%d'),
            'topics': data.get('topics', []),
            'deliverables': data.get('deliverables', []),
            'open_questions': data.get('open_questions', []),
            'decision_count': len(self.decision_ids),
            'task_count': len(self.task_ids),
            'participant_count': len(self.participant_ids),
        }
