{
    "name": "Blue Fox — Helpdesk",
    "summary": "Fork OCA helpdesk_mgmt with BF integrations: hour bank, waiting states, branded public form, ntfy critical hook",
    "version": "18.0.2.1.0",
    "category": "After-Sales",
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    "license": "LGPL-3",
    "depends": [
        "website",
        "helpdesk_mgmt",
        "bf_hour_bank",
        "bluefox_branding",
        "bf_persona",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/helpdesk_data.xml",
        "views/helpdesk_menu_views.xml",
        "views/helpdesk_ticket_team_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/public_form_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "bf_helpdesk/static/src/scss/public_form.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}
