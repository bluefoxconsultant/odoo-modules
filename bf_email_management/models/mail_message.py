import base64
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    def action_download_eml(self):
        """Stream this chatter message as an .eml download.

        Triggered from the message kebab menu (see static/src/js/
        bf_email_chatter_action.js). Reuses bf.email's RFC 2822 builder so
        rows mirrored from IMAP keep their original raw bytes (DKIM etc.).
        """
        self.ensure_one()
        self.check_access_rule("read")

        BfEmail = self.env["bf.email"].sudo()

        eml_bytes = None
        filename = None

        # Prefer a mirrored bf.email row with raw_rfc822 — that gives us
        # the exact bytes we received over IMAP.
        if self.message_id:
            mirror = BfEmail.search([
                ("message_id_header", "=", self.message_id),
            ], limit=1)
            if mirror and mirror.raw_rfc822:
                try:
                    eml_bytes = base64.b64decode(mirror.raw_rfc822)
                    filename = mirror._eml_filename()
                except Exception:
                    _logger.warning(
                        "mail.message %s: bf.email mirror raw_rfc822 decode failed",
                        self.id,
                    )

        if eml_bytes is None:
            eml_bytes = BfEmail._build_eml_from_mail_message(self)
            filename = self._eml_filename_from_message()

        attachment = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "datas": base64.b64encode(eml_bytes).decode("ascii"),
            "mimetype": "message/rfc822",
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _eml_filename_from_message(self):
        """Filename for direct mail.message downloads (no bf.email mirror)."""
        self.ensure_one()
        BfEmail = self.env["bf.email"].sudo()
        date_part = self.date.strftime("%Y-%m-%d") if self.date else "undated"
        from email.utils import parseaddr
        _, bare = parseaddr(self.email_from or "")
        local = (bare.split("@", 1)[0] if bare else "") or "unknown"
        local = BfEmail._eml_slug(local)
        subject = BfEmail._eml_slug(self.subject or "")
        parts = [p for p in (date_part, local, subject) if p]
        stem = "_".join(parts) or f"message_{self.id}"
        return f"{stem[:120]}.eml"
