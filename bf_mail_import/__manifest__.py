{
    "name": "BF Import courriel (.eml)",
    "version": "18.0.1.1.0",
    "category": "Productivity/Email",
    "summary": "Importer des fichiers .eml dans le chatter Odoo",
    "author": "Blue Fox",
    "website": "https://example.com",
    "license": "Other OSI approved licence",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/mail_import_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_mail_import/static/src/js/chatter_import_patch.js",
            "bf_mail_import/static/src/xml/chatter_import_patch.xml",
        ],
    },
    "application": False,
    "installable": True,
}
