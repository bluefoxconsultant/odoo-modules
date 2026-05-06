"""mail.notification override — propagate read state to bf.email.

When a mail.notification's ``is_read`` flips to True for the configured
IMAP user (i.e. the user reads the message in the chatter UI of any
record), find any bf.email row whose ``mail_message_id`` matches and
flip its ``status`` from ``new`` to ``read``.

This fixes the user-visible ambiguity: "read" used to mean only "opened
in the bf.email module" — now it means "the user (or chatter) saw it."
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MailNotification(models.Model):
    _inherit = "mail.notification"

    def write(self, vals):
        result = super().write(vals)
        if vals.get("is_read") is True and self:
            try:
                self._propagate_read_to_bf_email()
            except Exception:
                _logger.warning(
                    "bf.email read propagation failed", exc_info=True,
                )
        return result

    def _propagate_read_to_bf_email(self):
        """Flip matching bf.email rows from status='new' to 'read'."""
        ICP = self.env["ir.config_parameter"].sudo()
        imap_user = ICP.get_param("bf_email.imap_user", "").strip().lower()
        if not imap_user:
            return
        partner = self.env["res.partner"].sudo().search(
            [("email_normalized", "=", imap_user)], limit=1,
        )
        if not partner:
            return
        relevant = self.filtered(
            lambda n: n.res_partner_id.id == partner.id and n.mail_message_id
        )
        if not relevant:
            return
        message_ids = relevant.mapped("mail_message_id").ids
        rows = self.env["bf.email"].sudo().search([
            ("mail_message_id", "in", message_ids),
            ("status", "=", "new"),
        ])
        if rows:
            rows.write({"status": "read"})
            _logger.info(
                "bf.email: propagated chatter-read to %s rows", len(rows),
            )
