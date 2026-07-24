"""Central solicitation guard on rating requests.

The core rating module defines rating_send_request() on mail.thread itself:
project task ratings (stage change + periodic cron) and any other module
using the standard mechanism all funnel through here. Hooking it makes the
anti-oversolicitation guard truly global — without it, enabling project
ratings could email the same client on top of an NPS wave the same day —
and stamps bf_cx_last_solicited so every channel sees every other channel.
"""
import logging

from odoo import _, models

from .bf_cx_feedback import param_is_true

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def rating_send_request(self, template, lang=False, force_send=True):
        partner = None
        try:
            partner = self._rating_get_partner()
        except Exception:  # noqa: BLE001 - models without partner semantics
            partner = None
        if partner and param_is_true(
            self.env, "bf_cx.guard_rating_requests", default=True
        ):
            allowed, blocked = partner._bf_cx_split_solicitable()
            if blocked:
                self.message_post(
                    body=_(
                        "Demande d'évaluation non envoyée à %s : garde-fou "
                        "de sollicitation (cooldown, liste à ne pas "
                        "contacter ou dossier en recouvrement)."
                    )
                    % partner.display_name
                )
                return None
            partner._bf_cx_mark_solicited()
        return super().rating_send_request(
            template, lang=lang, force_send=force_send
        )
