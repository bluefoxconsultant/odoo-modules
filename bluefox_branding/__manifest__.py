{
    "name": "Configurable Branding Pack",
    "version": "18.0.2.0.0",
    "category": "Tools",
    "summary": "Per-company brand color + email layout overrides for Odoo Community",
    "description": """
        Configurable branding overrides for Odoo Community.

        All colors are sourced at runtime from `res.company.report_brand_primary`
        and `res.company.report_brand_dark` (fields provided by `bf_lexend`).
        Tenants set their own colors via Settings > Brand colors; no SCSS
        recompile, no per-tenant build.

        What this module overrides:
        - Backend navbar, app menu, burger menu, main-menu module — re-skinned
          via CSS variables fed from the company brand color fields.
        - Buttons, links, badges, progress bars, kanban accents, selection,
          focus rings — all use the configured brand primary.
        - Email layouts (`bluefox_branding.bf_mail_layout` and the
          `_with_signature` variant) used by the composer wizard for
          invoices, quotes, contracts, etc. — header, accent bar, signature
          and footer all draw on the company logo, name, contact info, and
          brand colors.
        - Standard Odoo mail templates from `om_account_followup`, `contract`,
          `helpdesk_mgmt`, `survey`, and `calendar` are rewritten with the
          branded layout via `post_init_hook` (the originals have noupdate=1
          and can't be patched declaratively).
        - Late-invoice template (no XML ID, manually created in UI) gets a
          branded body via the same hook.
        - Legacy Odoo purple (#875A7B variants) found in email bodies is
          replaced with the configured brand primary at render time.

        Fallback hex values match Odoo's stock theme (#714B67 plum,
        #212529 dark) so this module is a visual no-op until brand colors
        are configured.
    """,
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    "license": "LGPL-3",
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
        "portal",
        "bf_lexend",
    ],
    "data": [
        "data/mail_layout_override.xml",
        "views/brand_css_variables.xml",
        "views/website_brand_css_variables.xml",
        # mail_template_overrides.xml is NOT loaded by the Odoo data loader
        # (originals have noupdate=True). post_init_hook reads it and applies
        # updates via ORM write().
    ],
    "assets": {
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
