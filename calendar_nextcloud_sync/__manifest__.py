{
    "name": "Calendar Nextcloud Sync",
    "summary": "Bidirectional calendar synchronization between Odoo and Nextcloud via n8n",
    "version": "18.0.1.20.0",
    "category": "Calendar",
    "website": "https://example.com",
    "author": "Blue Fox Inc.",
    "license": "Other OSI approved licence",
    "application": False,
    "installable": True,
    "depends": [
        "calendar",
        "base_automation",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        # Views
        "views/calendar_event_views.xml",
        "views/nextcloud_sync_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu.xml",
        # Data (automated actions + cron)
        "data/ir_actions_server.xml",
        "data/nextcloud_sync_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "calendar_nextcloud_sync/static/src/js/attendee_calendar_color_patch.js",
        ],
    },
}
