"""Post-report feedback request.

Hooks the real send method (action_send_report_direct — the wizard path
ends there too once composed). Opt-in via bf_cx.meeting_feedback, and the
bf_cx anti-oversolicitation cooldown applies per contact.
"""
import logging

from odoo import _, models

from odoo.addons.bf_cx.models.bf_cx_feedback import param_is_true

_logger = logging.getLogger(__name__)


class MeetingRecord(models.Model):
    _inherit = "meeting.record"

    def action_send_report_direct(self):
        res = super().action_send_report_direct()
        try:
            self._bf_cx_maybe_request_feedback()
        except Exception:  # noqa: BLE001 - never break the report send
            _logger.exception(
                "bf_cx_meeting: feedback request failed for meeting %s",
                self.ids,
            )
        return res

    def _bf_cx_maybe_request_feedback(self):
        if not param_is_true(self.env, "bf_cx.meeting_feedback", default=False):
            return
        template = self.env.ref(
            "bf_cx_meeting.mail_template_meeting_rating",
            raise_if_not_found=False,
        )
        if not template:
            return
        for record in self:
            partner = record.partner_id
            if not partner or not partner.email:
                continue
            allowed, blocked = partner._bf_cx_split_solicitable()
            if blocked:
                record.message_post(
                    body=_(
                        "Demande de feedback non envoyée : %s a été sollicité "
                        "récemment (garde-fou anti-sursollicitation)."
                    )
                    % partner.display_name
                )
                continue
            record.rating_send_request(
                template, lang=partner.lang, force_send=False
            )
            partner._bf_cx_mark_solicited()
