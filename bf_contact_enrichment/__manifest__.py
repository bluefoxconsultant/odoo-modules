{
    "name": "Enrichissement de contacts",
    "summary": "Cartes d'affaires (OCR), signatures courriel, import vCard, "
               "détection de doublons et score de complétude — via Claude",
    "version": "18.0.1.0.0",
    "category": "Contacts",
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "mail",
        "bf_email_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/bf_contact_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/bf_email_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
