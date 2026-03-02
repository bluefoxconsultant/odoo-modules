from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    nc_sync_cron_enabled = fields.Boolean(
        string="Enable Nextcloud Calendar Catch-up Sync",
        config_parameter="calendar_nextcloud_sync.cron_enabled",
    )
    nc_sync_cron_interval = fields.Integer(
        string="Sync Interval (minutes)",
        config_parameter="calendar_nextcloud_sync.cron_interval",
        default=15,
    )
    nc_sync_webhook_url = fields.Char(
        string="n8n Webhook URL",
        config_parameter="calendar_nextcloud_sync.webhook_url",
        help="Default webhook URL applied to new calendar configurations",
    )
    nc_sync_webhook_secret = fields.Char(
        string="Webhook Secret",
        config_parameter="calendar_nextcloud_sync.webhook_secret",
        help="Default webhook secret applied to new calendar configurations",
    )
    nc_sync_default_calendar_id = fields.Many2one(
        "nextcloud.calendar.sync.config",
        string="Default Nextcloud Calendar",
        help="New events created in Odoo will automatically sync to this calendar",
    )

    def set_values(self):
        res = super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            "calendar_nextcloud_sync.default_calendar_id",
            self.nc_sync_default_calendar_id.id or 0,
        )
        cron = self.env.ref(
            "calendar_nextcloud_sync.cron_nextcloud_calendar_sync",
            raise_if_not_found=False,
        )
        if cron:
            cron.sudo().write({
                "active": self.nc_sync_cron_enabled,
                "interval_number": self.nc_sync_cron_interval or 15,
            })
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        cal_id = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("calendar_nextcloud_sync.default_calendar_id", "0")
        )
        if cal_id:
            cal = self.env["nextcloud.calendar.sync.config"].browse(cal_id)
            if cal.exists():
                res["nc_sync_default_calendar_id"] = cal_id
        cron = self.env.ref(
            "calendar_nextcloud_sync.cron_nextcloud_calendar_sync",
            raise_if_not_found=False,
        )
        if cron:
            res["nc_sync_cron_enabled"] = cron.active
            res["nc_sync_cron_interval"] = cron.interval_number
        return res
