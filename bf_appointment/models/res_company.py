from odoo import fields, models


# Defaults match Blue Fox Inc - keep them so a fresh install (no data file
# loaded yet, or a new company created post-install) ships with usable
# branding even before an admin touches Settings. Per-tenant deployments
# override these via res.config.settings or directly on res.company.
_BF_DEFAULT_BRAND_NAME = "Blue Fox"
_BF_DEFAULT_LOGO_URL = (
    "https://www.bluefoxconsultant.com/web/image/website/1/logo/"
    "Blue%20Fox?unique=803cc14"
)
_BF_DEFAULT_WEBSITE_URL = "https://www.bluefoxconsultant.com"
_BF_DEFAULT_PRIMARY = "#29ABE2"
_BF_DEFAULT_DARK = "#2E3132"
_BF_DEFAULT_SUPPORT_EMAIL = "service@bluefoxconsultant.com"
_BF_DEFAULT_SUPPORT_PHONE = "+15145132535"
_BF_DEFAULT_SUPPORT_PHONE_DISPLAY = "514-513-2535"
_BF_DEFAULT_PRIVACY_URL = (
    "https://www.bluefoxconsultant.com/r/politique-de-confidentialite"
)
_BF_DEFAULT_TERMS_URL = (
    "https://www.bluefoxconsultant.com/r/termes-et-conditions"
)


class ResCompany(models.Model):
    _inherit = "res.company"

    appointment_brand_name = fields.Char(
        string="Appointment Brand Name",
        default=_BF_DEFAULT_BRAND_NAME,
        help="Display name used in appointment emails (subject lines, sign-offs).",
    )
    appointment_brand_logo_url = fields.Char(
        string="Appointment Brand Logo URL",
        default=_BF_DEFAULT_LOGO_URL,
        help="Public URL of the logo embedded in appointment emails. "
             "Must be reachable without authentication.",
    )
    appointment_brand_website_url = fields.Char(
        string="Appointment Brand Website",
        default=_BF_DEFAULT_WEBSITE_URL,
        help="Where the email logo links to.",
    )
    appointment_brand_primary = fields.Char(
        string="Appointment Brand Primary Color",
        default=_BF_DEFAULT_PRIMARY,
        help="Hex color used for accents (buttons, links) on appointment "
             "pages and emails.",
    )
    appointment_brand_dark = fields.Char(
        string="Appointment Brand Dark Color",
        default=_BF_DEFAULT_DARK,
        help="Hex color for dark headers/footers in appointment emails.",
    )
    appointment_brand_support_email = fields.Char(
        string="Appointment Support Email",
        default=_BF_DEFAULT_SUPPORT_EMAIL,
        help="Contact email shown in appointment emails for booker questions.",
    )
    appointment_brand_support_phone = fields.Char(
        string="Appointment Support Phone (E.164)",
        default=_BF_DEFAULT_SUPPORT_PHONE,
        help="Phone in E.164 format (e.g. +15145551212), used in tel: links.",
    )
    appointment_brand_support_phone_display = fields.Char(
        string="Appointment Support Phone (display)",
        default=_BF_DEFAULT_SUPPORT_PHONE_DISPLAY,
        help="Phone in human format (e.g. 514-555-1212) shown to readers.",
    )
    appointment_brand_privacy_url = fields.Char(
        string="Appointment Privacy Policy URL",
        default=_BF_DEFAULT_PRIVACY_URL,
        help="Privacy-policy URL shown in email footers and the public form.",
    )
    appointment_brand_terms_url = fields.Char(
        string="Appointment Terms & Conditions URL",
        default=_BF_DEFAULT_TERMS_URL,
        help="Terms & conditions URL shown in email footers.",
    )
