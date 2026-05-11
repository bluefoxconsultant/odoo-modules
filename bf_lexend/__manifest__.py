{
    "name": "Lexend Typeface",
    "summary": "Use Lexend across Odoo UI and PDF reports, with brand colour settings",
    "version": "18.0.2.0.0",
    "category": "Theme/Backend",
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    "license": "LGPL-3",
    "depends": ["web", "base_setup"],
    "data": [
        "data/company_defaults.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": ["bf_lexend/static/src/scss/lexend.css"],
        "web.assets_frontend": ["bf_lexend/static/src/scss/lexend.css"],
        "web.report_assets_common": ["bf_lexend/static/src/scss/lexend_report.css"],
        "web.report_assets_pdf": ["bf_lexend/static/src/scss/lexend_report.css"],
    },
}
