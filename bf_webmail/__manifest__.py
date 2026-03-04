{
    "name": "Courriel Blue Fox",
    "summary": "Accès au courriel SnappyMail depuis la barre Odoo",
    "version": "18.0.1.1.0",
    "category": "Tools",
    "website": "https://bluefox.ca",
    "author": "Blue Fox Inc.",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": ["base"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_webmail/static/src/scss/bf_webmail.scss",
            "bf_webmail/static/src/js/bf_webmail_dialog.js",
            "bf_webmail/static/src/js/bf_webmail_systray.js",
            "bf_webmail/static/src/xml/bf_webmail.xml",
        ],
    },
}
