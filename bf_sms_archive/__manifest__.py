{
    "name": "Archive SMS & Appels",
    "summary": "Archivage et recherche de SMS et journaux d'appels Android (SMS Backup & Restore)",
    "version": "18.0.1.3.1",
    "category": "Tools",
    "author": "Olivier Morneau",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "base",
        "mail",
        "project",
    ],
    "external_dependencies": {
        "python": ["defusedxml", "requests"],
    },
    "data": [
        "security/sms_security.xml",
        "security/ir.model.access.csv",
        "report/sms_paperformat.xml",
        "report/sms_report_templates.xml",
        "wizard/import_wizard_views.xml",
        "wizard/post_to_task_wizard_views.xml",
        "views/sms_thread_views.xml",
        "views/sms_message_views.xml",
        "views/call_views.xml",
        "views/sms_dashboard_views.xml",
        "views/menu_views.xml",
        # Data
        "data/sms_nc_watch_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_sms_archive/static/src/js/sms_dashboard.js",
            "bf_sms_archive/static/src/xml/sms_dashboard.xml",
        ],
    },
}
