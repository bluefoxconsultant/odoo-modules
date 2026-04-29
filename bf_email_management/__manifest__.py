{
    "name": "Gestion des courriels",
    "summary": "Inbox unifiée IMAP + chatters Odoo, avec re-routage UI",
    "version": "18.0.1.5.1",
    "category": "Productivity",
    "website": "https://bluefox.ca",
    "author": "Blue Fox Inc.",
    "license": "LGPL-3",  # MIT — see README.md for full license text
    "application": True,
    "installable": True,
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/email_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/email_sync_cron.xml",
        "data/email_sync_imap_cron.xml",
        "wizard/bf_email_initial_sync_views.xml",
        "wizard/bf_email_reroute_views.xml",
        "wizard/bf_email_imap_backfill_views.xml",
        "views/bf_email_views.xml",
        "views/bf_email_dashboard_views.xml",
        "views/mail_scheduled_message_views.xml",
        "views/bf_email_menu.xml",
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_email_management/static/src/js/bf_email_dashboard.js",
            "bf_email_management/static/src/xml/bf_email_dashboard.xml",
        ],
    },
}
