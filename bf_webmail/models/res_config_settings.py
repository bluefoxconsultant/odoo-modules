import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception
    _logger.warning(
        "cryptography package not installed. "
        "IMAP password will be stored unencrypted."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bf_webmail_url = fields.Char(
        string="URL du webmail",
        config_parameter="bf_webmail.webmail_url",
    )
    bf_webmail_imap_host = fields.Char(
        string="Serveur IMAP",
        config_parameter="bf_webmail.imap_host",
    )
    bf_webmail_imap_port = fields.Integer(
        string="Port IMAP",
        config_parameter="bf_webmail.imap_port",
        default=993,
    )
    bf_webmail_imap_user = fields.Char(
        string="Utilisateur IMAP",
        config_parameter="bf_webmail.imap_user",
    )
    bf_webmail_imap_password = fields.Char(
        string="Mot de passe IMAP",
        compute="_compute_imap_password",
        inverse="_inverse_imap_password",
    )

    # --- Encryption helpers ---

    @staticmethod
    def _get_imap_encryption_key(env):
        """Get or generate Fernet key for IMAP password encryption."""
        if not Fernet:
            return None
        ICP = env["ir.config_parameter"].sudo()
        key = ICP.get_param("bf_webmail.encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            ICP.set_param("bf_webmail.encryption_key", key)
        return key.encode()

    @staticmethod
    def _encrypt_imap_password(env, value):
        if not value:
            return ""
        key = ResConfigSettings._get_imap_encryption_key(env)
        if not key:
            return value
        try:
            return Fernet(key).encrypt(value.encode()).decode()
        except Exception:
            _logger.exception("IMAP password encryption failed")
            return value

    @staticmethod
    def _decrypt_imap_password(env, encrypted):
        if not encrypted:
            return ""
        key = ResConfigSettings._get_imap_encryption_key(env)
        if not key:
            return encrypted
        try:
            return Fernet(key).decrypt(encrypted.encode()).decode()
        except InvalidToken:
            # Legacy unencrypted value — migrate it on next save
            return encrypted
        except Exception:
            _logger.exception("IMAP password decryption failed")
            return encrypted

    # --- Computed field ---

    def _compute_imap_password(self):
        encrypted = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("bf_webmail.imap_password_encrypted", "")
        )
        plaintext = self._decrypt_imap_password(self.env, encrypted)
        for rec in self:
            rec.bf_webmail_imap_password = plaintext

    def _inverse_imap_password(self):
        for rec in self:
            encrypted = self._encrypt_imap_password(
                self.env, rec.bf_webmail_imap_password or ""
            )
            self.env["ir.config_parameter"].sudo().set_param(
                "bf_webmail.imap_password_encrypted", encrypted
            )
