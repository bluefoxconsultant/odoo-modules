import json
import logging
import socket
import threading

import pytz
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_DEFAULT_BRIDGE_SOCKET = "/run/claude-bridge/bridge.sock"

_TZ_CITY_LABEL = {
    'America/Toronto': 'Montréal',
    'America/Montreal': 'Montréal',
    'Pacific/Auckland': 'Auckland',
}


def _tz_city(tz_name):
    if not tz_name:
        return ''
    if tz_name in _TZ_CITY_LABEL:
        return _TZ_CITY_LABEL[tz_name]
    return tz_name.split('/')[-1].replace('_', ' ')


def _format_meeting_date_display(record):
    """Format record.date in the client's tz, with the originator's tz in
    parentheses when it differs. record must expose date, partner_id,
    organizer_id, create_uid."""
    if not record.date:
        return ''
    client_tz_name = (record.partner_id.tz if record.partner_id else None) \
        or 'America/Toronto'
    organizer = record.organizer_id or record.create_uid
    originator_tz_name = (organizer.tz if organizer else None) \
        or 'America/Toronto'

    utc_dt = pytz.utc.localize(record.date)
    client_dt = utc_dt.astimezone(pytz.timezone(client_tz_name))
    primary = client_dt.strftime('%Y-%m-%d %H:%M %Z')

    if client_tz_name == originator_tz_name:
        return primary

    originator_dt = utc_dt.astimezone(pytz.timezone(originator_tz_name))
    secondary = originator_dt.strftime('%Y-%m-%d %H:%M %Z')
    return f"{primary} ({_tz_city(originator_tz_name)}: {secondary})"


def _post_to_bridge(socket_path, endpoint, payload, timeout):
    """Minimal HTTP-over-Unix-socket POST, returns parsed JSON response.

    Mirrors the helper in bf_claude_chat to keep this module standalone.
    """
    body = json.dumps(payload).encode()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(socket_path)
        req = (
            f"POST {endpoint} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + body
        sock.sendall(req)
        chunks = []
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks).decode()
        header_end = raw.find("\r\n\r\n")
        if header_end == -1:
            raise ValueError("Malformed HTTP response from bridge")
        status_line = raw[:raw.find("\r\n")]
        status_code = int(status_line.split(" ", 2)[1])
        resp_body = raw[header_end + 4:]
        headers_block = raw[:header_end].lower()
        if "transfer-encoding: chunked" in headers_block:
            decoded = []
            pos = 0
            while pos < len(resp_body):
                nl = resp_body.find("\r\n", pos)
                if nl == -1:
                    break
                chunk_size = int(resp_body[pos:nl], 16)
                if chunk_size == 0:
                    break
                decoded.append(resp_body[nl + 2:nl + 2 + chunk_size])
                pos = nl + 2 + chunk_size + 2
            resp_body = "".join(decoded)
        if status_code >= 400:
            raise ValueError(f"Bridge HTTP {status_code}: {resp_body[:200]}")
        return json.loads(resp_body)
    finally:
        sock.close()


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
    meeting_type = fields.Selection(
        [
            ('in_person', 'Présentiel'),
            ('video', 'Visio'),
            ('phone', 'Téléphonique'),
            ('hybrid', 'Hybride'),
            ('async', 'Asynchrone'),
        ],
        string='Mode',
        default='video',
        required=True,
        index=True,
        tracking=True,
        help='Mode de la rencontre. Visio par défaut (cas dominant via Noota). '
             'Téléphonique permet de lier un appel archivé via le module pont.',
    )
    meeting_type_icon = fields.Char(
        string='Icône mode',
        compute='_compute_meeting_type_icon',
        store=True,
        help='Glyphe unicode représentant le mode — utilisé en list/kanban.',
    )
    lang = fields.Selection(
        lambda self: self.env['res.lang'].get_installed(),
        string='Langue',
        compute='_compute_lang',
        store=True,
        readonly=False,
        help="Langue du compte rendu : pilote la langue du rapport PDF et du "
             "courriel d'envoi. Initialisée depuis la langue du client.",
    )

    @api.depends('meeting_type')
    def _compute_meeting_type_icon(self):
        glyphs = {
            'in_person': '👥',
            'video': '🎥',
            'phone': '📞',
            'hybrid': '🔀',
            'async': '💬',
        }
        for rec in self:
            rec.meeting_type_icon = glyphs.get(rec.meeting_type, '')

    @api.depends('partner_id')
    def _compute_lang(self):
        default_lang = self.env.lang or 'fr_CA'
        for rec in self:
            if rec.lang:
                continue
            rec.lang = (rec.partner_id and rec.partner_id.lang) or default_lang
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

    meeting_attachment_ids = fields.One2many(
        'ir.attachment',
        compute='_compute_meeting_attachment_ids',
        inverse='_inverse_meeting_attachment_ids',
        string='Documents',
    )

    def _compute_meeting_attachment_ids(self):
        for rec in self:
            rec.meeting_attachment_ids = self.env['ir.attachment'].search([
                ('res_model', '=', 'meeting.record'),
                ('res_id', '=', rec.id),
            ])

    def _inverse_meeting_attachment_ids(self):
        # Make sure inline edits to bf_visibility_window/from/until persist.
        # The One2many is computed (no real FK to inverse) — Odoo writes back
        # to ir.attachment directly via the inline list.
        pass

    @api.onchange('calendar_event_id')
    def _onchange_calendar_event_id_fill_participants(self):
        for rec in self:
            if rec.calendar_event_id and not rec.participant_ids:
                attendees = rec.calendar_event_id.partner_ids
                if attendees:
                    rec.participant_ids = [(6, 0, attendees.ids)]

    def write(self, vals):
        """Cascade `project_id` change to linked action-item tasks.

        When the user moves a meeting record to a different project, the
        action items that came out of that meeting should follow. Users can
        still re-route individual tasks afterwards if needed.
        """
        cascade = 'project_id' in vals
        if cascade:
            old_by_record = {rec.id: rec.project_id.id for rec in self}
        res = super().write(vals)
        if cascade:
            new_pid = vals.get('project_id')
            for rec in self:
                if new_pid == old_by_record.get(rec.id):
                    continue
                # Only move tasks that were on the OLD project (don't drag
                # tasks already manually re-routed elsewhere).
                old_pid = old_by_record.get(rec.id)
                to_move = rec.task_ids.filtered(
                    lambda t, old=old_pid: t.project_id.id == old
                ) if old_pid else rec.task_ids
                if to_move and new_pid:
                    to_move.write({'project_id': new_pid})
        return res

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

        # Multi-company guard: the QWeb report reads project_id.name etc., which
        # is blocked by ir.rule when the project lives in a company that is not
        # in allowed_company_ids on the current request. Resolve the project's
        # company via sudo (the project ref itself is otherwise unreadable in a
        # mismatched company context) and force it into context before rendering.
        target_company = (
            self.sudo().project_id.company_id
            or self.sudo().company_id
            or self.env.company
        )
        allowed_ids = set(self.env.context.get('allowed_company_ids') or [self.env.company.id])
        allowed_ids.add(target_company.id)
        template.with_company(target_company).with_context(
            allowed_company_ids=list(allowed_ids),
        ).send_mail(self.id, force_send=True)
        self.write({
            'report_state': 'sent',
            'report_sent_date': fields.Datetime.now(),
        })
        return True

    def action_refine_meeting(self):
        """Lancer le skill /refine-meeting via le bridge Claude.

        Le bridge est appelé en arrière-plan (thread) parce que /refine-meeting
        peut prendre plusieurs minutes ; le résultat est posté au chatter.

        Réservé aux gestionnaires (`bf_meeting.group_meeting_manager`) car le
        bridge spawn `claude -p --dangerously-skip-permissions`, qui contourne
        toute vérification de permissions côté Claude.
        """
        self.ensure_one()
        if not self.env.user.has_group("bf_meeting.group_meeting_manager"):
            raise UserError(
                "Le raffinement automatique est réservé aux gestionnaires "
                "(groupe « Rencontres / Gestionnaire »)."
            )

        import os as _os
        ICP = self.env["ir.config_parameter"].sudo()
        socket_path = ICP.get_param("bf_meeting.bridge_socket", _DEFAULT_BRIDGE_SOCKET)
        timeout = int(ICP.get_param("bf_meeting.bridge_timeout", "480"))

        if not _os.path.exists(socket_path):
            raise UserError(
                f"Bridge Claude non disponible (socket introuvable : {socket_path}).\n"
                f"Configurer le paramètre système `bf_meeting.bridge_socket` "
                f"vers le socket du service `claude-chatbot-bridge`."
            )

        record_id = self.id
        db_name = self.env.cr.dbname
        uid = self.env.user.id
        triggered_by = self.env.user.login

        def _run():
            from odoo import api as _api, registry as _registry
            try:
                resp = _post_to_bridge(
                    socket_path, "/refine-meeting",
                    {
                        "meeting_id": record_id,
                        "tenant": "bf",
                        "triggered_by": triggered_by,
                    },
                    timeout,
                )
                status = resp.get("status", "?")
                msg = resp.get("message", "")
            except Exception as exc:
                status, msg = "error", f"{type(exc).__name__}: {exc}"

            with _registry(db_name).cursor() as new_cr:
                new_env = _api.Environment(new_cr, uid, {})
                rec = new_env["meeting.record"].browse(record_id).exists()
                if rec:
                    body = (
                        f"<p><b>Raffinement /refine-meeting</b> — statut : "
                        f"<code>{escape(status)}</code></p>"
                    )
                    if msg:
                        body += f"<p>{escape(msg)}</p>"
                    rec.message_post(body=Markup(body), message_type="comment")

        threading.Thread(target=_run, daemon=True).start()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "info",
                "title": "Raffinement lancé",
                "message": (
                    "Le skill /refine-meeting est en cours d'exécution. "
                    "Le résultat apparaîtra au chatter dans quelques minutes."
                ),
                "sticky": False,
            },
        }

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
            'date_display': _format_meeting_date_display(self),
            'topics': data.get('topics', []),
            'deliverables': data.get('deliverables', []),
            'open_questions': data.get('open_questions', []),
            'decision_count': len(self.decision_ids),
            'task_count': len(self.task_ids),
            'participant_count': len(self.participant_ids),
        }
