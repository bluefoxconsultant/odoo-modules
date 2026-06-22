import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

NTFY_RELAY_PARAM = "bf_helpdesk.ntfy_webhook_url"
NTFY_TIMEOUT_PARAM = "bf_helpdesk.ntfy_webhook_timeout"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    waiting_state = fields.Selection(
        selection=[
            ("client", "Attente — Client.e"),
            ("external", "Attente — Externe"),
        ],
        string="État d'attente",
        copy=False,
        tracking=True,
        help="Marque ce ticket comme en attente d'une partie tierce. Indépendant du stage : "
             "on peut être en stage 'En cours' ET en attente client.",
    )

    hour_bank_id = fields.Many2one(
        comodel_name="hour.bank.client",
        string="Banque d'heures",
        compute="_compute_hour_bank_id",
        store=True,
        readonly=True,
    )
    hour_bank_balance = fields.Float(
        string="Solde banque (h)",
        compute="_compute_hour_bank_balance",
    )
    hour_bank_low = fields.Boolean(
        string="Solde bas",
        compute="_compute_hour_bank_balance",
    )

    # ------------------------------------------------------------------
    # Persona panel — read-only mirror of contact.persona for quick
    # composer hints when answering the ticket
    # ------------------------------------------------------------------
    persona_id = fields.Many2one(
        comodel_name="contact.persona",
        string="Persona",
        compute="_compute_persona_id",
        search="_search_persona_id",
        store=False,
    )

    @api.model
    def _search_persona_id(self, operator, value):
        Persona = self.env["contact.persona"].sudo()
        domain = [("id", operator, value)] if operator in ("=", "!=", "in", "not in") else [("id", operator, value)]
        partners = Persona.search(domain).mapped("partner_id")
        return [("partner_id", "in", partners.ids)]
    persona_addressing_style = fields.Selection(
        related="persona_id.addressing_style",
        string="Style d'adresse",
        readonly=True,
    )
    persona_preferred_salutation = fields.Char(
        related="persona_id.preferred_salutation",
        string="Salutation préférée",
        readonly=True,
    )
    persona_closing_formula = fields.Char(
        related="persona_id.closing_formula",
        string="Formule de clôture",
        readonly=True,
    )
    persona_tone_summary = fields.Selection(
        related="persona_id.tone_summary",
        string="Ton du contact",
        readonly=True,
    )
    persona_our_tone_summary = fields.Selection(
        related="persona_id.our_tone_summary",
        string="Notre ton",
        readonly=True,
    )
    persona_payer_quality = fields.Selection(
        related="persona_id.payer_quality",
        string="Qualité de paiement",
        readonly=True,
    )

    # ------------------------------------------------------------------
    # SLA — first response + resolution deadlines
    # ------------------------------------------------------------------
    sla_response_deadline = fields.Datetime(
        string="Échéance première réponse",
        compute="_compute_sla_deadlines",
        store=True,
    )
    sla_resolve_deadline = fields.Datetime(
        string="Échéance résolution",
        compute="_compute_sla_deadlines",
        store=True,
    )
    sla_response_breach = fields.Boolean(
        string="SLA réponse dépassée",
        compute="_compute_sla_breach",
    )
    sla_resolve_breach = fields.Boolean(
        string="SLA résolution dépassée",
        compute="_compute_sla_breach",
    )

    @api.depends("create_date", "team_id.sla_response_hours", "team_id.sla_resolve_hours")
    def _compute_sla_deadlines(self):
        for ticket in self:
            base = ticket.create_date
            if not base:
                ticket.sla_response_deadline = False
                ticket.sla_resolve_deadline = False
                continue
            response_hours = ticket.team_id.sla_response_hours or 0.0
            resolve_hours = ticket.team_id.sla_resolve_hours or 0.0
            ticket.sla_response_deadline = (
                base + timedelta(hours=response_hours)
            ) if response_hours else False
            ticket.sla_resolve_deadline = (
                base + timedelta(hours=resolve_hours)
            ) if resolve_hours else False

    @api.depends("sla_response_deadline", "sla_resolve_deadline",
                 "stage_id.closed", "message_ids", "closed_date")
    def _compute_sla_breach(self):
        now = fields.Datetime.now()
        for ticket in self:
            # Response breach: deadline passed, ticket still open, no outbound message from staff
            response_breach = False
            if (
                ticket.sla_response_deadline
                and ticket.sla_response_deadline < now
                and not ticket.stage_id.closed
            ):
                outbound = ticket.message_ids.filtered(
                    lambda m: m.message_type == "comment"
                    and m.author_id
                    and m.author_id != ticket.partner_id
                )
                response_breach = not outbound
            ticket.sla_response_breach = response_breach
            # Resolve breach: deadline passed and ticket still open
            resolve_breach = False
            if ticket.sla_resolve_deadline and ticket.sla_resolve_deadline < now:
                resolve_breach = not ticket.stage_id.closed
            ticket.sla_resolve_breach = resolve_breach

    @api.model
    def _cron_sla_breach_activity(self):
        """Daily cron — drop a follow-up activity on tickets newly in breach."""
        breached = self.search([
            ("active", "=", True),
            ("stage_id.closed", "=", False),
            "|",
            ("sla_response_breach", "=", True),
            ("sla_resolve_breach", "=", True),
        ])
        for ticket in breached:
            existing = self.env["mail.activity"].search([
                ("res_model", "=", self._name),
                ("res_id", "=", ticket.id),
                ("summary", "=", "SLA dépassé"),
            ], limit=1)
            if existing:
                continue
            ticket.activity_schedule(
                act_type_xmlid="mail.mail_activity_data_todo",
                summary="SLA dépassé",
                note=(
                    "<p>Ce ticket a dépassé un SLA configuré sur l'équipe. "
                    "Vérifier et réagir.</p>"
                ),
                user_id=ticket.user_id.id or self.env.uid,
            )

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------
    def action_apply_macro(self):
        """Open the macro picker wizard (single-select)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Appliquer une macro",
            "res_model": "helpdesk.macro.apply.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_ticket_id": self.id},
        }

    # ------------------------------------------------------------------
    # Auto-tag — apply matching rules at creation
    # ------------------------------------------------------------------
    def _apply_auto_tag_rules(self):
        """Scan team rules against subject + description and add matching tags."""
        for ticket in self:
            if not ticket.team_id:
                continue
            rules = ticket.team_id.auto_tag_rule_ids.filtered(lambda r: r.active)
            if not rules:
                continue
            text = (ticket.name or "") + " " + (ticket.description or "")
            tag_ids = []
            for rule in rules:
                if rule._matches(text):
                    tag_ids.append(rule.tag_id.id)
            if tag_ids:
                ticket.write({"tag_ids": [(4, tid) for tid in tag_ids]})

    # ------------------------------------------------------------------
    # CSAT — auto-send survey on close
    # ------------------------------------------------------------------
    csat_user_input_id = fields.Many2one(
        comodel_name="survey.user_input",
        string="Réponse CSAT",
        copy=False,
        readonly=True,
    )
    csat_state = fields.Selection(
        related="csat_user_input_id.state",
        string="État CSAT",
        readonly=True,
    )

    def _send_csat_invite(self):
        self.ensure_one()
        team = self.team_id
        if not team or not team.csat_survey_id:
            return False
        if self.csat_user_input_id:
            return False  # already sent
        partner = self.partner_id
        email = self.partner_email or (partner.email if partner else None)
        if not email:
            return False
        survey = team.csat_survey_id.sudo()
        try:
            user_input = survey._create_answer(
                partner=partner if partner else False,
                email=email,
            )
        except Exception:
            _logger.exception(
                "bf_helpdesk: CSAT _create_answer failed for ticket %s", self.number,
            )
            return False
        self.write({"csat_user_input_id": user_input.id})
        template = self.env.ref(
            "survey.mail_template_user_input_invite", raise_if_not_found=False,
        )
        if template:
            template.sudo().send_mail(
                user_input.id, force_send=False,
                email_layout_xmlid="bluefox_branding.bf_mail_layout",
            )
        return user_input

    # ------------------------------------------------------------------
    # Knowledge matrix link — quick scope validation
    # ------------------------------------------------------------------
    knowledge_item_id = fields.Many2one(
        comodel_name="project.knowledge.item",
        string="Élément matrice",
        help="Lie ce ticket à un élément de la matrice de connaissances du projet "
             "pour valider l'alignement avec le scope du mandat.",
    )
    knowledge_matrix_id = fields.Many2one(
        comodel_name="project.knowledge.matrix",
        string="Matrice",
        related="knowledge_item_id.matrix_id",
        readonly=True,
        store=False,
    )
    knowledge_item_state = fields.Selection(
        related="knowledge_item_id.state",
        string="État de l'élément",
        readonly=True,
    )
    scope_aligned = fields.Selection(
        selection=[
            ("aligned", "Dans le scope"),
            ("pending", "Élément en attente"),
            ("out_of_scope", "Hors scope"),
            ("unset", "Non vérifié"),
        ],
        string="Validation scope",
        compute="_compute_scope_aligned",
        store=False,
    )

    # ------------------------------------------------------------------
    # Convert ticket → meeting.record
    # ------------------------------------------------------------------
    meeting_record_ids = fields.One2many(
        comodel_name="meeting.record",
        inverse_name="helpdesk_ticket_id",
        string="Rencontres liées",
    )
    meeting_record_count = fields.Integer(
        string="Nb. rencontres",
        compute="_compute_meeting_record_count",
    )

    @api.depends("meeting_record_ids")
    def _compute_meeting_record_count(self):
        for ticket in self:
            ticket.meeting_record_count = len(ticket.meeting_record_ids)

    def action_create_meeting_record(self):
        """Create a draft meeting.record from this ticket and open it.

        Pre-fills the meeting with the ticket title, links it back to the
        ticket and to the team's hour bank project (if any).
        """
        self.ensure_one()
        Meeting = self.env["meeting.record"]
        project = (
            self.knowledge_item_id.matrix_id.project_id
            or self.team_id.hour_bank_id.project_ids[:1]
            or self.env["project.project"].browse()
        )
        meeting = Meeting.create({
            "name": f"[{self.number}] {self.name}",
            "date": fields.Datetime.now(),
            "project_id": project.id if project else False,
            "helpdesk_ticket_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "meeting.record",
            "res_id": meeting.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Triage IA via Claude — one-shot Anthropic API call
    # ------------------------------------------------------------------
    triage_state = fields.Selection(
        selection=[
            ("none", "Pas de triage"),
            ("pending", "En cours"),
            ("done", "Triage prêt"),
            ("error", "Erreur"),
        ],
        default="none",
        copy=False,
    )
    triage_suggestion_html = fields.Html(
        string="Suggestion IA",
        readonly=True,
        copy=False,
        sanitize=True,
    )
    triage_last_run = fields.Datetime(
        string="Dernier triage",
        readonly=True,
        copy=False,
    )

    def _triage_prompt(self):
        self.ensure_one()
        team_stages = self.team_id._get_applicable_stages().mapped("name") or ["Nouveau", "En cours", "Terminé"]
        team_users = self.team_id.user_ids.mapped("name") or ["—"]
        partner = self.partner_name or (self.partner_id.name if self.partner_id else "Inconnu")
        # Strip HTML from description to keep prompt small
        desc = self.description or ""
        desc_text = self.env["mail.render.mixin"]._replace_local_links(desc)
        return (
            "Tu es un.e adjoint.e helpdesk Blue Fox. Voici un nouveau ticket :\n\n"
            f"# Ticket {self.number}\n"
            f"**Sujet** : {self.name}\n"
            f"**Client** : {partner}\n"
            f"**Équipe** : {self.team_id.name}\n"
            f"**Stages disponibles** : {', '.join(team_stages)}\n"
            f"**Membres de l'équipe** : {', '.join(team_users)}\n\n"
            f"**Description (HTML)** :\n{desc_text}\n\n"
            "Réponds en français, en HTML simple (p, ul, li, strong), avec ces 3 sections :\n"
            "1. **Catégorisation** — 1 phrase qui résume le type de demande.\n"
            "2. **Stage suggéré** — 1 stage parmi la liste, avec justification.\n"
            "3. **Assignation suggérée** — 1 membre de l'équipe (ou « non-assigné si X »), avec justification.\n"
            "4. **Brouillon de première réponse** — 2-3 phrases qui acknowledge la demande "
            "et indiquent les prochaines étapes. Ton chaleureux mais concis.\n"
            "Pas de bla-bla. Pas d'introduction. Pas de conclusion."
        )

    def _call_anthropic_network(self, prompt):
        """Call Anthropic Messages API directly. Returns assistant text.

        Raises UserError for configuration issues (missing key) or HTTP errors.
        Lets network exceptions propagate (caller catches and persists 'error').
        """
        IConf = self.env["ir.config_parameter"].sudo()
        api_key = self._bf_helpdesk_get_anthropic_api_key()
        if not api_key:
            raise UserError(
                "Triage IA non configuré : aucune clé API Anthropic disponible. "
                "Renseignez le paramètre système 'bf_helpdesk.anthropic_api_key', "
                "ou installez le module optionnel GenFox (bf_claude_chat) qui fournit "
                "une clé chiffrée."
            )
        model = IConf.get_param("bf_claude_chat.model", "claude-sonnet-4-6")
        timeout = float(IConf.get_param("bf_helpdesk.triage_timeout", "30"))
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                data = json.loads(body)
        except urllib.error.HTTPError as e:
            raise UserError(f"Anthropic API a retourné HTTP {e.code} : {e.read()[:200].decode('utf-8', errors='replace')}")
        # Extract text from content blocks
        content = data.get("content") or []
        parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(parts).strip()

    def _bf_helpdesk_get_anthropic_api_key(self):
        """Resolve the Anthropic API key.

        Priority:
        1. ir.config_parameter 'bf_helpdesk.anthropic_api_key' (plain — for tests)
        2. bf_claude_chat encrypted key, decrypted via the same Fernet pattern.
        """
        IConf = self.env["ir.config_parameter"].sudo()
        plain = (IConf.get_param("bf_helpdesk.anthropic_api_key", "") or "").strip()
        if plain:
            return plain
        encrypted = IConf.get_param("bf_claude_chat.api_key_encrypted", "")
        if not encrypted:
            return ""
        try:
            ResConfig = self.env["res.config.settings"]
            return ResConfig._decrypt_api_key(self.env, encrypted)
        except Exception:
            _logger.exception("bf_helpdesk: cannot decrypt bf_claude_chat API key")
            return ""

    def action_triage_with_claude(self):
        """Run Claude triage on this ticket.

        - Configuration errors (missing API key, etc.) raise UserError and
          surface as a popup; the form state is unchanged.
        - Network/transient errors are caught, the suggestion field shows
          the error, and the state goes to 'error' so the user can retry.
        """
        self.ensure_one()
        prompt = self._triage_prompt()
        try:
            response_text = self._call_anthropic_network(prompt)
        except (ConnectionError, urllib.error.URLError, TimeoutError, OSError) as e:
            _logger.warning(
                "bf_helpdesk: triage network failure on ticket %s: %s",
                self.number, e,
            )
            self.write({
                "triage_state": "error",
                "triage_suggestion_html": f"<p><strong>Erreur réseau :</strong> {e}</p>",
                "triage_last_run": fields.Datetime.now(),
            })
            return True
        self.write({
            "triage_state": "done",
            "triage_suggestion_html": response_text,
            "triage_last_run": fields.Datetime.now(),
        })
        return True

    def action_view_meeting_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "meeting.record",
            "view_mode": "list,form",
            "domain": [("helpdesk_ticket_id", "=", self.id)],
            "context": {"default_helpdesk_ticket_id": self.id},
        }

    @api.depends("knowledge_item_id", "knowledge_item_id.state")
    def _compute_scope_aligned(self):
        for ticket in self:
            if not ticket.knowledge_item_id:
                ticket.scope_aligned = "unset"
                continue
            state = ticket.knowledge_item_id.state
            if state in ("done", "accepted"):
                ticket.scope_aligned = "aligned"
            elif state in ("pending", "in_progress", "proposed"):
                ticket.scope_aligned = "pending"
            elif state in ("rejected", "na", "superseded"):
                ticket.scope_aligned = "out_of_scope"
            else:
                ticket.scope_aligned = "unset"

    @api.depends("partner_id")
    def _compute_persona_id(self):
        Persona = self.env["contact.persona"].sudo()
        partners = self.mapped("partner_id")
        if not partners:
            for ticket in self:
                ticket.persona_id = False
            return
        personas = Persona.search([("partner_id", "in", partners.ids)])
        by_partner = {p.partner_id.id: p.id for p in personas}
        for ticket in self:
            ticket.persona_id = by_partner.get(ticket.partner_id.id, False)

    def action_open_persona(self):
        self.ensure_one()
        if self.persona_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "contact.persona",
                "res_id": self.persona_id.id,
                "view_mode": "form",
                "target": "current",
            }
        # No persona yet — open create wizard pre-filled with the partner
        return {
            "type": "ir.actions.act_window",
            "res_model": "contact.persona",
            "view_mode": "form",
            "target": "current",
            "context": {"default_partner_id": self.partner_id.id},
        }

    @api.depends("team_id", "team_id.hour_bank_id")
    def _compute_hour_bank_id(self):
        for ticket in self:
            ticket.hour_bank_id = ticket.team_id.hour_bank_id or False

    def _track_template(self, tracking):
        """Force helpdesk tracking emails to use the Blue Fox branded layout
        instead of mail.mail_notification_light (generic Odoo).

        The bluefox_branding module overrides the 3 helpdesk_mgmt mail.template
        records to strip the legacy purple shell, then bf_mail_layout wraps them
        in the BF header/accent/footer canon.
        """
        res = super()._track_template(tracking)
        for key, (_template, ctx) in list(res.items()):
            if isinstance(ctx, dict) and ctx.get("email_layout_xmlid") == "mail.mail_notification_light":
                ctx["email_layout_xmlid"] = "bluefox_branding.bf_mail_layout"
        return res

    @api.depends("hour_bank_id", "hour_bank_id.current_balance",
                 "team_id.hour_bank_alert_threshold_hours")
    def _compute_hour_bank_balance(self):
        for ticket in self:
            if ticket.hour_bank_id:
                ticket.hour_bank_balance = ticket.hour_bank_id.current_balance
                threshold = ticket.team_id.hour_bank_alert_threshold_hours or 0.0
                ticket.hour_bank_low = ticket.hour_bank_balance <= threshold
            else:
                ticket.hour_bank_balance = 0.0
                ticket.hour_bank_low = False

    # ------------------------------------------------------------------
    # ntfy critical hook
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket._apply_auto_tag_rules()
            ticket._maybe_notify_ntfy_critical(reason="created")
        return tickets

    def write(self, vals):
        old_priority = {t.id: t.priority for t in self}
        before_closed = {t.id: bool(t.stage_id.closed) for t in self}
        res = super().write(vals)
        if "priority" in vals:
            for ticket in self:
                if old_priority.get(ticket.id) != ticket.priority:
                    ticket._maybe_notify_ntfy_critical(reason="escalated")
        if "stage_id" in vals:
            for ticket in self:
                if ticket.stage_id.closed and not before_closed.get(ticket.id):
                    ticket._send_csat_invite()
        return res

    # ------------------------------------------------------------------
    # IMAP gateway hardening
    # ------------------------------------------------------------------
    @api.model
    def message_new(self, msg, custom_values=None):
        """Defensive overrides on top of OCA's mail.thread message_new:

        - Drop autoresponder loops (Auto-Submitted, X-AutoReply, Precedence: bulk)
          — these create noise tickets when a customer's mail server bounces
          back our notification.
        - Strip the most obvious quoted-tail noise from the body so the ticket
          opens with the actual question, not the quoted previous reply.
        - Skip empty subjects with body length < 10 chars (likely cron blow-back).
        """
        if self._is_autoresponder(msg):
            _logger.info(
                "bf_helpdesk: dropping autoresponder mail-gateway message "
                "(subject=%r, from=%r)",
                msg.get("subject"), msg.get("from"),
            )
            # Return an empty record so mail.thread treats this as handled
            return self.browse()
        return super().message_new(msg, custom_values=custom_values)

    @api.model
    def _is_autoresponder(self, msg):
        """Detect common autoresponder/loop signals across SMTP and X- headers."""
        headers = msg.get("custom_headers") or {}
        # mail.thread normalizes some headers into msg dict; others are in raw headers
        auto_submitted = (
            (msg.get("auto-submitted") or headers.get("Auto-Submitted") or "")
            .strip().lower()
        )
        if auto_submitted and auto_submitted != "no":
            return True
        x_auto = headers.get("X-Auto-Response-Suppress") or headers.get("X-AutoReply")
        if x_auto:
            return True
        precedence = (headers.get("Precedence") or "").strip().lower()
        if precedence in ("bulk", "auto_reply", "list", "junk"):
            return True
        # Subject prefixes that almost always mean automation
        subject = (msg.get("subject") or "").lower()
        if subject.startswith(("auto:", "automatic reply", "out of office",
                               "absent du bureau", "réponse automatique",
                               "delivery status notification",
                               "undeliverable:", "mail delivery failed",
                               "mailer-daemon")):
            return True
        return False

    def _maybe_notify_ntfy_critical(self, reason="created"):
        self.ensure_one()
        team = self.team_id
        if not team or not team.ntfy_critical_enabled:
            return
        threshold = team.ntfy_priority_threshold or "3"
        # Selection lex order (str) is fine for "0".."3"
        if (self.priority or "0") < threshold:
            return
        url = self.env["ir.config_parameter"].sudo().get_param(NTFY_RELAY_PARAM)
        if not url:
            _logger.info(
                "bf_helpdesk: ntfy enabled on team %s but %s not set, skipping",
                team.name, NTFY_RELAY_PARAM,
            )
            return
        try:
            timeout = float(
                self.env["ir.config_parameter"].sudo().get_param(NTFY_TIMEOUT_PARAM, "5")
            )
        except (TypeError, ValueError):
            timeout = 5.0

        payload = {
            "_id": self.id,
            "_model": self._name,
            "_action": reason,
            "number": self.number,
            "name": self.name,
            "priority": self.priority,
            "team_id": team.id,
            "team_name": team.name,
            "partner_name": self.partner_name or (self.partner_id.name if self.partner_id else ""),
            "partner_email": self.partner_email or (self.partner_id.email if self.partner_id else ""),
            "url": self.get_base_url() + "/odoo/helpdesk-tickets/" + str(self.id),
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 400:
                    _logger.warning(
                        "bf_helpdesk: ntfy relay returned %s for ticket %s",
                        resp.status, self.number,
                    )
        except Exception:
            _logger.exception(
                "bf_helpdesk: ntfy relay POST failed for ticket %s", self.number,
            )
