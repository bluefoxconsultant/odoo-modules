import json
import logging
import urllib.request

from odoo import api, fields, models

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
            ticket._maybe_notify_ntfy_critical(reason="created")
        return tickets

    def write(self, vals):
        old_priority = {t.id: t.priority for t in self}
        res = super().write(vals)
        if "priority" in vals:
            for ticket in self:
                if old_priority.get(ticket.id) != ticket.priority:
                    ticket._maybe_notify_ntfy_critical(reason="escalated")
        return res

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
