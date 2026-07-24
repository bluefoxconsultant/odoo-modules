"""Complaint registry.

Thin, self-sufficient complaint log: severity, acknowledgement deadline,
root cause and corrective action (closed loop). When helpdesk_mgmt is
installed the bf_cx_helpdesk bridge adds the ticket link — the core
deliberately has no reference to helpdesk models so it loads on any tenant.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BfCxComplaint(models.Model):
    _name = "bf.cx.complaint"
    _description = "Plainte client"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_received desc, id desc"
    _rec_name = "number"

    number = fields.Char(
        string="Numéro",
        readonly=True,
        copy=False,
        default="/",
    )
    name = fields.Char(string="Objet", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Plaignant", index=True, tracking=True
    )
    contact_name = fields.Char(
        string="Nom du contact",
        help="Si le plaignant n'a pas de fiche contact.",
    )
    contact_email = fields.Char(string="Courriel du contact")
    severity = fields.Selection(
        [
            ("low", "Faible"),
            ("medium", "Moyenne"),
            ("high", "Élevée"),
            ("critical", "Critique"),
        ],
        string="Gravité",
        default="medium",
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        [
            ("received", "Reçue"),
            ("ack", "Accusé de réception"),
            ("analysis", "En analyse"),
            ("resolved", "Résolue"),
            ("closed", "Fermée"),
        ],
        string="État",
        default="received",
        required=True,
        tracking=True,
    )
    date_received = fields.Datetime(
        string="Reçue le",
        required=True,
        default=fields.Datetime.now,
    )
    ack_deadline = fields.Datetime(
        string="Échéance d'accusé de réception",
        compute="_compute_ack_deadline",
        store=True,
        help="Date limite pour accuser réception (délai configurable dans "
             "les paramètres). Le cron alerte le responsable à l'approche "
             "du dépassement.",
    )
    date_acknowledged = fields.Datetime(
        string="AR envoyé le", readonly=True, copy=False
    )
    ack_delay_hours = fields.Float(
        string="Délai d'AR (h)",
        compute="_compute_delays",
        store=True,
        help="Heures entre la réception et l'accusé de réception — "
             "indicateur ISO 10002.",
    )
    resolution_delay_days = fields.Float(
        string="Délai de résolution (j)",
        compute="_compute_delays",
        store=True,
    )
    date_resolved = fields.Datetime(string="Résolue le", readonly=True, copy=False)
    complainant_satisfied = fields.Boolean(
        string="Plaignant satisfait du traitement",
        tracking=True,
        help="ISO 10002 : vérifier la satisfaction du plaignant vis-à-vis "
             "du TRAITEMENT de la plainte après résolution (pas du produit).",
    )
    description = fields.Html(string="Description", required=True)
    resolution = fields.Html(string="Résolution")
    root_cause = fields.Text(string="Cause fondamentale")
    corrective_action = fields.Text(
        string="Action corrective",
        help="Ce qui est mis en place pour que la situation ne se "
             "reproduise pas.",
    )
    project_id = fields.Many2one("project.project", string="Projet / mandat")
    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )
    feedback_id = fields.Many2one(
        "bf.cx.feedback",
        string="Feedback d'origine",
        ondelete="set null",
    )

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends("date_received")
    def _compute_ack_deadline(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("bf_cx.complaint_ack_days", "2")
        )
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = 2
        for rec in self:
            rec.ack_deadline = (
                rec.date_received + timedelta(days=days)
                if rec.date_received
                else False
            )

    @api.depends("date_received", "date_acknowledged", "date_resolved")
    def _compute_delays(self):
        for rec in self:
            rec.ack_delay_hours = (
                (rec.date_acknowledged - rec.date_received).total_seconds()
                / 3600.0
                if rec.date_acknowledged and rec.date_received
                else 0.0
            )
            rec.resolution_delay_days = (
                (rec.date_resolved - rec.date_received).total_seconds()
                / 86400.0
                if rec.date_resolved and rec.date_received
                else 0.0
            )

    # ── ORM ──────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("number") or vals["number"] == "/":
                vals["number"] = (
                    self.env["ir.sequence"].next_by_code("bf.cx.complaint")
                    or "/"
                )
        return super().create(vals_list)

    @api.depends("number", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                "%s — %s" % (rec.number, rec.name)
                if rec.number and rec.number != "/"
                else (rec.name or "")
            )

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_acknowledge(self):
        """Real acknowledgement: email the complainant when reachable."""
        template = self.env.ref(
            "bf_cx.mail_template_complaint_ack", raise_if_not_found=False
        )
        for rec in self:
            email = rec.partner_id.email or rec.contact_email
            if template and email:
                template.send_mail(rec.id, force_send=False)
                body = _("Accusé de réception envoyé à %s.") % email
            else:
                body = _(
                    "Accusé de réception consigné par %s (aucune adresse "
                    "courriel — transmis hors système)."
                ) % self.env.user.display_name
            rec.write(
                {
                    "state": "ack",
                    "date_acknowledged": fields.Datetime.now(),
                }
            )
            rec.message_post(body=body)
        return True

    def action_start_analysis(self):
        self.write({"state": "analysis"})
        return True

    def action_resolve(self):
        for rec in self:
            if not rec.resolution:
                raise UserError(
                    _("Consigner la résolution avant de fermer l'analyse "
                      "(champ « Résolution »).")
                )
            rec.write(
                {"state": "resolved", "date_resolved": fields.Datetime.now()}
            )
        return True

    def action_close(self):
        """Close, then verify the complainant's satisfaction (ISO 10002)."""
        self.write({"state": "closed"})
        for rec in self:
            if rec.complainant_satisfied:
                continue
            if not (rec.partner_id or rec.contact_email or rec.contact_name):
                continue
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=fields.Date.context_today(rec)
                + timedelta(days=7),
                user_id=(rec.user_id or self.env.user).id,
                summary=_("Valider la satisfaction du plaignant (%s)")
                % (rec.partner_id.display_name or rec.contact_name or ""),
                note=_(
                    "ISO 10002 : vérifier que le plaignant est satisfait du "
                    "TRAITEMENT de sa plainte, puis cocher « Plaignant "
                    "satisfait du traitement » sur la fiche."
                ),
            )
        return True

    def action_reopen(self):
        self.write({"state": "analysis", "date_resolved": False})
        return True

    # ── Cron ─────────────────────────────────────────────────────────────────

    @api.model
    def _cron_ack_overdue(self):
        """Alert the owner when an acknowledgement deadline is (nearly) blown."""
        soon = fields.Datetime.now() + timedelta(hours=24)
        overdue = self.search(
            [("state", "=", "received"), ("ack_deadline", "<", soon)]
        )
        for rec in overdue:
            summary = _("Accusé de réception en retard — %s") % rec.number
            existing = self.env["mail.activity"].search_count(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", rec.id),
                    ("summary", "=", summary),
                ]
            )
            if existing:
                continue
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=(rec.user_id or self.env.user).id,
                summary=summary,
                note=_(
                    "L'échéance d'accusé de réception de cette plainte est "
                    "atteinte ou dépassée. Utiliser « Accuser réception » "
                    "(courriel automatique si le plaignant a une adresse)."
                ),
            )
        return True
