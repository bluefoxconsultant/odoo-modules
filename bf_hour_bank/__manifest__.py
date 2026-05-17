{
    'name': 'Banque d\'heures',
    'version': '18.0.1.11.0',
    'category': 'Services/Project',
    'summary': 'Suivi automatis\u00e9 des banques d\'heures client',
    'description': """
Banque d'heures
===============

Suivi automatis\u00e9 des banques d'heures pour les clients en mode forfaitaire.

Fonctionnalit\u00e9s:
-----------------
* Configuration par client (projets, produits de facturation)
* Calcul automatique du solde (d\u00e9bits feuilles de temps, cr\u00e9dits factures)
* G\u00e9n\u00e9ration de rapports PDF et Excel
* Envoi par courriel avec pi\u00e8ces jointes
* Sommaire par projet et synth\u00e8se mensuelle
    """,
    'author': 'Blue Fox Inc.',
    'website': 'https://bluefoxconsultant.com',
    'license': 'LGPL-3',
    'depends': ['project', 'account', 'hr_timesheet', 'mail', 'portal', 'bluefox_branding', 'bf_onboarding_base'],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'data': [
        # Security first
        'security/hour_bank_security.xml',
        'security/ir.model.access.csv',
        # Reports
        'report/hour_bank_paperformat.xml',
        'report/hour_bank_report_templates.xml',
        # Data
        'data/hour_bank_mail_template.xml',
        'data/hour_bank_cron.xml',
        'data/bf_onboarding.xml',
        # Wizards
        'wizard/hour_bank_send_wizard_views.xml',
        # Views
        'views/hour_bank_client_views.xml',
        'views/hour_bank_threshold_views.xml',
        'views/hour_bank_portal_templates.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
