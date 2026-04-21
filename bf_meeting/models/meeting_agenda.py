import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ACTIVE_AGENDA_STATES = ('draft', 'confirmed')
CLOSED_TASK_STATES = ('1_done', '1_canceled')


class MeetingAgenda(models.Model):
    """Ordre du jour d'une réunion."""
    _name = 'meeting.agenda'
    _description = 'Ordre du jour'
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
        required=True,
        index=True,
        tracking=True,
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
    duration_planned = fields.Integer(
        string='Durée prévue (minutes)',
    )
    location = fields.Char(
        string='Lieu',
    )
    series_name = fields.Char(
        string='Série',
        index=True,
    )
    organizer_id = fields.Many2one(
        'res.users',
        string='Organisateur',
        default=lambda self: self.env.user,
    )
    participant_ids = fields.Many2many(
        'res.partner',
        'meeting_agenda_participant_rel',
        'agenda_id',
        'partner_id',
        string='Participants',
    )

    # Content
    objectives = fields.Text(
        string='Objectifs',
        help='Ce que nous souhaitons accomplir lors de cette rencontre.',
    )
    context_html = fields.Html(
        string='Contexte',
        sanitize_style=True,
        help='Contexte et état des lieux avant la rencontre.',
    )
    preparation_html = fields.Html(
        string='Préparation',
        sanitize_style=True,
        help='Liste de vérification pour la préparation.',
    )

    # Relations
    topic_ids = fields.One2many(
        'meeting.agenda.topic',
        'agenda_id',
        string='Sujets',
    )
    topic_count = fields.Integer(
        string='Nombre de sujets',
        compute='_compute_topic_count',
    )
    agenda_task_ids = fields.Many2many(
        'project.task',
        string="Éléments d'action à discuter",
        compute='_compute_agenda_task_ids',
        help="Tâches ouvertes rattachées à cet ordre du jour : lien explicite "
             "ou tag « Prochaine rencontre » résolvant à cet agenda.",
    )
    agenda_task_count = fields.Integer(
        compute='_compute_agenda_task_ids',
    )
    meeting_record_id = fields.Many2one(
        'meeting.record',
        string='Compte rendu',
        index=True,
    )
    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Événement calendrier',
    )

    # Email
    auto_send_on_confirm = fields.Boolean(
        string='Envoyer automatiquement à la confirmation',
        default=False,
    )
    sent_date = fields.Datetime(
        string="Date d'envoi",
        readonly=True,
    )
    recipient_ids = fields.Many2many(
        'res.partner',
        'meeting_agenda_recipient_rel',
        'agenda_id',
        'partner_id',
        string='Destinataires',
        help='Si vide, les participants recevront le courriel.',
    )
    partner_to_ids = fields.Char(
        string='IDs destinataires (technique)',
        compute='_compute_partner_to_ids',
    )

    @api.depends('recipient_ids', 'participant_ids')
    def _compute_partner_to_ids(self):
        for rec in self:
            recipients = rec.recipient_ids or rec.participant_ids
            rec.partner_to_ids = ','.join(str(pid) for pid in recipients.ids)

    # State
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', tracking=True)

    # Source
    nc_path = fields.Char(
        string='Chemin Nextcloud',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    @api.depends('project_id', 'date')
    def _compute_name(self):
        for rec in self:
            if rec.name:
                continue
            parts = []
            if rec.project_id:
                parts.append(rec.project_id.name)
            parts.append('OdJ')
            if rec.date:
                parts.append(rec.date.strftime('%Y-%m-%d'))
            rec.name = ' — '.join(parts) if parts else 'Nouvel ordre du jour'

    @api.depends('topic_ids')
    def _compute_topic_count(self):
        for rec in self:
            rec.topic_count = len(rec.topic_ids)

    def _compute_agenda_task_ids(self):
        Task = self.env['project.task']
        Agenda = self.env['meeting.agenda']
        now = fields.Datetime.now()

        # Partition self: only active/future agendas can carry tasks.
        active = self.filtered(
            lambda a: a.state in ACTIVE_AGENDA_STATES and a.date and a.date >= now
        )
        for rec in self - active:
            rec.agenda_task_ids = False
            rec.agenda_task_count = 0

        if not active:
            return

        # Hard-linked tasks: single query, grouped by agenda.
        hard_tasks = Task.search([
            ('bf_meeting_agenda_id', 'in', active.ids),
            ('state', 'not in', CLOSED_TASK_STATES),
        ])
        hard_by_agenda = {}
        for t in hard_tasks:
            hard_by_agenda.setdefault(t.bf_meeting_agenda_id.id, Task)
            hard_by_agenda[t.bf_meeting_agenda_id.id] |= t

        # Resolve winners: earliest upcoming draft/confirmed agenda per
        # partner_id and per project_id across the whole database (not just self).
        partner_ids = active.mapped('partner_id').ids
        project_ids = active.mapped('project_id').ids
        partner_winner = {}
        if partner_ids:
            candidates = Agenda.search([
                ('partner_id', 'in', partner_ids),
                ('state', 'in', ACTIVE_AGENDA_STATES),
                ('date', '>=', now),
            ], order='date asc, id asc')
            for cand in candidates:
                partner_winner.setdefault(cand.partner_id.id, cand.id)
        project_winner = {}
        if project_ids:
            candidates = Agenda.search([
                ('project_id', 'in', project_ids),
                ('state', 'in', ACTIVE_AGENDA_STATES),
                ('date', '>=', now),
            ], order='date asc, id asc')
            for cand in candidates:
                project_winner.setdefault(cand.project_id.id, cand.id)

        # Tagged tasks: 2 batched searches (one per scope) instead of 4.
        # Partition by tag in Python. Per-agenda filtering afterwards.
        client_tagged = Task
        if partner_ids:
            client_tagged = Task.search([
                ('bf_discuss_tag', 'in', ('next_client', 'all_client')),
                ('bf_meeting_agenda_id', '=', False),
                ('state', 'not in', CLOSED_TASK_STATES),
                '|',
                ('partner_id', 'in', partner_ids),
                ('project_id.partner_id', 'in', partner_ids),
            ])
        project_tagged = Task
        if project_ids:
            project_tagged = Task.search([
                ('bf_discuss_tag', 'in', ('next_project', 'all_project')),
                ('bf_meeting_agenda_id', '=', False),
                ('state', 'not in', CLOSED_TASK_STATES),
                ('project_id', 'in', project_ids),
            ])

        def _match_partner(t, pid):
            return t.partner_id.id == pid or (
                not t.partner_id and t.project_id.partner_id.id == pid
            )

        # Constant — avoid recomputing each task during the sort.
        sort_max_date = fields.Date.today().replace(year=9999)

        for rec in active:
            collected = Task
            collected |= hard_by_agenda.get(rec.id, Task)
            if rec.partner_id:
                pid = rec.partner_id.id
                is_partner_winner = partner_winner.get(pid) == rec.id
                collected |= client_tagged.filtered(
                    lambda t, pid=pid, win=is_partner_winner: _match_partner(t, pid) and (
                        t.bf_discuss_tag == 'all_client'
                        or (t.bf_discuss_tag == 'next_client' and win)
                    )
                )
            if rec.project_id:
                prj = rec.project_id.id
                is_project_winner = project_winner.get(prj) == rec.id
                collected |= project_tagged.filtered(
                    lambda t, prj=prj, win=is_project_winner: t.project_id.id == prj and (
                        t.bf_discuss_tag == 'all_project'
                        or (t.bf_discuss_tag == 'next_project' and win)
                    )
                )
            collected = collected.sorted(
                key=lambda t: (-int(t.priority or '0'),
                               t.date_deadline or sort_max_date,
                               t.id)
            )
            rec.agenda_task_ids = collected
            rec.agenda_task_count = len(collected)

    def action_confirm(self):
        """Confirmer l'ordre du jour."""
        self.write({'state': 'confirmed'})
        for rec in self:
            if rec.auto_send_on_confirm:
                rec.action_send_agenda()

    def action_done(self):
        """Marquer l'ordre du jour comme terminé."""
        self.write({'state': 'done'})

    def action_cancel(self):
        """Annuler l'ordre du jour.

        Pour chaque tâche hard-linkée à l'agenda :
        - Efface `bf_meeting_agenda_id`.
        - Si la tâche n'a pas de tag soft (`bf_discuss_tag`), crée une activité
          « À faire » due aujourd'hui sur le premier assigné (fallback
          organisateur) pour réassigner la tâche à un OdJ.
        Les tâches avec tag soft basculent automatiquement vers le prochain
        agenda admissible via la résolution calculée.
        """
        Task = self.env['project.task']
        for agenda in self:
            hard = Task.search([('bf_meeting_agenda_id', '=', agenda.id)])
            if not hard:
                continue
            tz_date = fields.Datetime.context_timestamp(agenda, agenda.date) \
                if agenda.date else None
            date_str = tz_date.strftime('%Y-%m-%d') if tz_date else ''
            for task in hard:
                task.bf_meeting_agenda_id = False
                if task.bf_discuss_tag:
                    continue
                assignee = task.user_ids[:1]
                user_id = assignee.id if assignee else (
                    agenda.organizer_id.id if agenda.organizer_id else self.env.uid
                )
                task.activity_schedule(
                    'mail.mail_activity_data_todo',
                    date_deadline=fields.Date.context_today(agenda),
                    summary="Rencontre annulée — réassigner à un OdJ",
                    note=(f"La rencontre « {agenda.name} » prévue le {date_str} "
                          "a été annulée. Réassigner cette tâche à un ordre "
                          "du jour si applicable."),
                    user_id=user_id,
                )
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        """Remettre en brouillon."""
        self.write({'state': 'draft'})

    def action_send_agenda(self):
        """Envoyer l'ordre du jour par courriel."""
        self.ensure_one()
        template = self.env.ref(
            'bf_meeting.meeting_agenda_mail_template', raise_if_not_found=False
        )
        if not template:
            _logger.warning("Agenda mail template not found")
            return

        recipients = self.recipient_ids or self.participant_ids
        if not recipients:
            _logger.warning("No recipients for agenda %s", self.name)
            return

        template.send_mail(self.id, force_send=True)
        self.write({'sent_date': fields.Datetime.now()})

    def action_send_agenda_wizard(self):
        """Ouvrir l'assistant d'envoi de l'ordre du jour."""
        self.ensure_one()
        template = self.env.ref(
            'bf_meeting.meeting_agenda_mail_template', raise_if_not_found=False
        )
        ctx = {
            'default_model': 'meeting.agenda',
            'default_res_ids': self.ids,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_light',
        }
        if template:
            ctx['default_template_id'] = template.id
        return {
            'type': 'ir.actions.act_window',
            'name': "Envoyer l'ordre du jour",
            'res_model': 'mail.compose.message',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }

    def action_view_agenda_tasks(self):
        """Smart button : ouvrir la liste des tâches à discuter."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Éléments d'action à discuter",
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.agenda_task_ids.ids)],
            'context': {'default_project_id': self.project_id.id},
        }

    def _get_report_data(self):
        """Prepare data dict for the QWeb agenda report."""
        self.ensure_one()
        topics = []
        for idx, t in enumerate(self.topic_ids.sorted('sequence'), 1):
            topics.append({
                'index': idx,
                'name': t.name,
                'duration': t.duration_planned,
                'presenter': t.presenter_id.name if t.presenter_id else '',
                'description': t.description or '',
            })
        tag_labels = dict(self.env['project.task']._fields['bf_discuss_tag'].selection)
        tagged_tasks = []
        for idx, t in enumerate(self.agenda_task_ids, 1):
            if t.bf_discuss_tag:
                source = tag_labels.get(t.bf_discuss_tag, '')
            elif t.bf_meeting_agenda_id:
                source = 'Épinglée'
            else:
                source = ''
            tagged_tasks.append({
                'index': idx,
                'name': t.name,
                'project': t.project_id.name or '',
                'assignees': ', '.join(t.user_ids.mapped('name')),
                'deadline': t.date_deadline,
                'stage': t.stage_id.name or '',
                'source': source,
            })
        return {
            'topic_count': len(topics),
            'topics': topics,
            'participant_count': len(self.participant_ids),
            'tagged_tasks': tagged_tasks,
            'tagged_task_count': len(tagged_tasks),
        }

    def action_create_meeting_record(self):
        """Créer un compte rendu à partir de cet ordre du jour."""
        self.ensure_one()
        if self.meeting_record_id:
            raise UserError(
                "Un compte rendu existe déjà pour cet ordre du jour : "
                f"« {self.meeting_record_id.name} »."
            )
        if self.state == 'cancelled':
            raise UserError(
                "Impossible de créer un compte rendu : l'ordre du jour est annulé."
            )
        vals = {
            'project_id': self.project_id.id,
            'date': self.date,
            'room_name': self.name,
            'location': self.location,
            'series_name': self.series_name,
            'organizer_id': self.organizer_id.id if self.organizer_id else False,
            'participant_ids': [(6, 0, self.participant_ids.ids)],
            'calendar_event_id': self.calendar_event_id.id if self.calendar_event_id else False,
            'duration_minutes': self.duration_planned,
        }
        record = self.env['meeting.record'].create(vals)

        # Create topics from agenda topics
        for topic in self.topic_ids:
            self.env['meeting.topic'].create({
                'meeting_id': record.id,
                'sequence': topic.sequence,
                'name': topic.name,
            })

        # Transfer hard-linked tasks to the new meeting record. Soft-tagged
        # tasks are left alone — they will naturally resolve to the next
        # upcoming agenda.
        hard = self.env['project.task'].search([
            ('bf_meeting_agenda_id', '=', self.id),
        ])
        if hard:
            hard.write({
                'meeting_id': record.id,
                'bf_meeting_agenda_id': False,
                'bf_discuss_tag': False,
            })

        self.write({
            'meeting_record_id': record.id,
            'state': 'done',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': record.name,
            'res_model': 'meeting.record',
            'res_id': record.id,
            'views': [[False, 'form']],
        }
