# License MIT - see README.md for full license text.
{
    "name": "Gestion d'hébergement",
    "summary": "Gérer les services d'hébergement pour les clients avec suivi de versions et facturation",
    "version": "18.0.2.35.0",
    "category": "Services",
    "website": "https://bluefox.ca",
    "author": "Blue Fox Inc.",
    "license": "LGPL-3",  # Odoo requires LGPL-3 or proprietary for Community modules
    "application": True,
    "installable": True,
    "depends": [
        "base",
        "mail",
        "contacts",
        "contract",
    ],
    "data": [
        # Security
        "security/hosting_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/hosting_sequence.xml",
        "data/mail_activity_type.xml",
        "data/hosting_cron.xml",
        "data/hosting_export.xml",
        "data/hosting_digest_template.xml",
        "data/hosting_cron_update.xml",
        "data/hosting_server_data.xml",
        "data/hosting_software_extended.xml",
        "data/hosting_maintenance_template_data.xml",
        "data/hosting_backup_email_template.xml",
        "data/hosting_client_email_templates.xml",
        "data/hosting_accepted_http_code_data.xml",
        "data/hosting_domain_data.xml",
        "data/hosting_audit_cron.xml",
        # Views
        "views/hosting_software_views.xml",
        "views/hosting_software_version_views.xml",
        "views/hosting_service_tag_views.xml",
        "views/hosting_server_views.xml",
        "views/hosting_update_log_views.xml",
        "views/hosting_health_check_views.xml",
        "views/hosting_health_daily_snapshot_views.xml",
        "views/hosting_maintenance_schedule_views.xml",
        "views/hosting_maintenance_template_views.xml",
        "views/hosting_service_views.xml",  # Must come after maintenance_schedule (references action)
        "views/hosting_dashboard_views.xml",
        "views/hosting_digest_views.xml",
        "views/hosting_backup_repository_views.xml",
        "views/hosting_backup_snapshot_views.xml",
        "views/hosting_backup_views.xml",
        "views/hosting_domain_views.xml",
        "views/hosting_audit_log_views.xml",
        "views/hosting_security_event_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/hosting_menu.xml",
    ],
    "demo": [
        "demo/hosting_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hosting_management/static/src/js/hosting_dashboard.js",
            "hosting_management/static/src/xml/hosting_dashboard.xml",
        ],
    },
}
