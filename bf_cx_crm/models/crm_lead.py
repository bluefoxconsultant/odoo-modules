"""Win/loss feedback: survey the contact when an opportunity is lost.

No BF precedent existed on the loss path — the anchor is the core
crm.lead.action_set_lost(). One survey per lead (bf_cx_loss_survey_sent),
cooldown applied, and everything wrapped so a survey hiccup can never
block marking a deal lost.
"""
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = "crm.lead"

    bf_cx_loss_survey_sent = fields.Boolean(
        string="Sondage post-perte envoyé", copy=False
    )

    def action_set_lost(self, **additional_values):
        res = super().action_set_lost(**additional_values)
        try:
            self._bf_cx_send_loss_survey()
        except Exception:  # noqa: BLE001 - never block the lost flow
            _logger.exception(
                "bf_cx_crm: loss survey failed for leads %s", self.ids
            )
        return res

    def _bf_cx_send_loss_survey(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("bf_cx.loss_program_id")
        )
        try:
            program_id = int(raw or 0)
        except (TypeError, ValueError):
            program_id = 0
        if not program_id:
            return
        program = (
            self.env["bf.cx.program"].sudo().browse(program_id).exists()
        )
        if not program or not program.survey_id or not program.invite_template_id:
            return
        for lead in self:
            if lead.bf_cx_loss_survey_sent:
                continue
            partner = lead.partner_id
            if not partner or not partner.email:
                continue
            allowed, blocked = partner._bf_cx_split_solicitable()
            if blocked:
                lead.message_post(
                    body=_(
                        "Sondage post-perte non envoyé : %s a été sollicité "
                        "récemment (garde-fou anti-sursollicitation)."
                    )
                    % partner.display_name
                )
                continue
            answer = program.survey_id.sudo()._create_answer(
                partner=partner, check_attempts=False
            )
            program.invite_template_id.sudo().send_mail(
                answer.id, force_send=False
            )
            partner._bf_cx_mark_solicited()
            lead.bf_cx_loss_survey_sent = True
            lead.message_post(
                body=_(
                    "Sondage post-perte « %(program)s » envoyé à %(partner)s "
                    "(motif de perte : %(reason)s).",
                    program=program.name,
                    partner=partner.display_name,
                    reason=lead.lost_reason_id.name or _("non précisé"),
                )
            )
