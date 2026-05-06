{
    "name": "Bureau — bureaux multi-panneaux personnalisables",
    "summary": "Crée et gère des « bureaux » nommés (mises en page multi-panneaux d'actions Odoo) modifiables depuis l'UI",
    "version": "18.0.2.1.1",
    "category": "Productivity",
    "website": "https://bluefox.ca",
    "author": "Blue Fox Inc.",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": ["web", "base", "mail", "project", "bf_email_management"],
    "data": [
        "security/ir.model.access.csv",
        "security/bureau_security.xml",
        "views/bureau_desk_views.xml",
        "views/bureau_menu.xml",
        "data/bureau_default_desk.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bureau/static/src/js/bureau_desk.js",
            "bureau/static/src/xml/bureau_desk.xml",
            "bureau/static/src/scss/bureau_desk.scss",
        ],
    },
}
