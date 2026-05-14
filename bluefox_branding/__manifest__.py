{
    "name": "Blue Fox Branding",
    "version": "18.0.1.17.0",
    "category": "Tools",
    "summary": "Custom branding colors and email templates for Blue Fox",
    "description": """
        Custom branding module for Blue Fox Inc.

        Features:
        - Custom navbar color (#2E3132)
        - Custom button/accent color (#29ABE2)
        - Main Menu / Home Menu / App Switcher branding
        - Email button colors automatically replaced
        - All Odoo purple (#875A7B) replaced with brand blue (#29ABE2)
        - Blue Fox branded mail notification layout (header, footer, accent bars)
        - Branded payment followup templates (4 levels, French)
        - Branded contract email templates (French)
        - Branded helpdesk notification templates (French)
        - Late invoice notice template branding (post_init_hook)
        - Branded survey invitation template (French)
        - Branded calendar event templates: invitation, date update, reminder, event update (French)
    """,
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    'license': 'LGPL-3',
    "depends": [
        "web",
        "mail",
        "account",
        "sale",
        "calendar",
        "om_account_followup",
        "contract",
        "helpdesk_mgmt",
        "survey",
        "bf_lexend",  # provides company.report_brand_primary / report_brand_dark + Lexend font
        "bf_onboarding_base",
    ],
    "data": [
        "data/mail_layout_override.xml",
        "data/bf_onboarding.xml",
        # mail_template_overrides.xml is NOT loaded by Odoo data loader
        # (original templates have noupdate=True). Instead, post_init_hook
        # reads this file and applies updates via ORM write().
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "bluefox_branding/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "bluefox_branding/static/src/scss/branding.scss",
        ],
        "web.assets_frontend": [
            "bluefox_branding/static/src/scss/branding.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
