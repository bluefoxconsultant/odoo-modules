from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    report_brand_primary = fields.Char(
        related="company_id.report_brand_primary",
        readonly=False,
    )
    report_brand_dark = fields.Char(
        related="company_id.report_brand_dark",
        readonly=False,
    )
