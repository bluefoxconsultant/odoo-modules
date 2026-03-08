import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None
    _logger.warning(
        "cryptography package not installed. "
        "Nextcloud Talk credential encryption will not be available."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bf_appointment_jitsi_domain = fields.Char(
        string="Jitsi Domain",
        config_parameter="bf_appointment.jitsi_domain",
        default="meet.jit.si",
        help="Jitsi Meet server domain (e.g. meet.jit.si or your self-hosted instance).",
    )
    bf_appointment_nc_talk_base_url = fields.Char(
        string="Nextcloud Talk Base URL",
        config_parameter="bf_appointment.nc_talk_base_url",
        help="Base URL of the Nextcloud instance (e.g. https://cloud.example.com).",
    )
    bf_appointment_nc_talk_user = fields.Char(
        string="Nextcloud Talk User",
        config_parameter="bf_appointment.nc_talk_user",
        help="Nextcloud user for Talk API authentication.",
    )
    bf_appointment_nc_talk_password = fields.Char(
        string="Nextcloud Talk Password",
        help="Nextcloud app password for Talk API. Stored encrypted.",
    )

    def set_values(self):
        res = super().set_values()
        if self.bf_appointment_nc_talk_password:
            encrypted = self._encrypt_value(self.bf_appointment_nc_talk_password)
            self.env["ir.config_parameter"].sudo().set_param(
                "bf_appointment.nc_talk_password_encrypted", encrypted
            )
        return res

    def get_values(self):
        res = super().get_values()
        encrypted = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("bf_appointment.nc_talk_password_encrypted", "")
        )
        if encrypted:
            res["bf_appointment_nc_talk_password"] = "********"
        return res

    def _encrypt_value(self, value):
        if not value:
            return False
        if not Fernet:
            _logger.warning("Fernet not available, storing value as-is")
            return value
        ICP = self.env["ir.config_parameter"].sudo()
        key = ICP.get_param("bf_appointment.encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            ICP.set_param("bf_appointment.encryption_key", key)
        try:
            f = Fernet(key.encode())
            return f.encrypt(value.encode()).decode()
        except Exception as e:
            _logger.error("Encryption failed: %s", e)
            return value
