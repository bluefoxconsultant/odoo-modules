{
    "name": "BF Timer - Feuilles de temps",
    "version": "18.0.1.5.0",
    "category": "Services/Timesheets",
    "summary": "Timer global de feuilles de temps avec multi-timer et interface OWL",
    "author": "Blue Fox Inc",
    "website": "https://example.com",
    "license": "Other OSI approved licence",  # MIT — see README.md
    "depends": ["hr_timesheet", "project"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/bf_timer_stop_wizard_views.xml",
        "data/bf_timer_preset_data.xml",
        "views/bf_timer_description_preset_views.xml",
        "views/project_task_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bf_timesheet_timer/static/src/scss/bf_timer.scss",
            "bf_timesheet_timer/static/src/js/bf_timer_service.js",
            "bf_timesheet_timer/static/src/js/bf_timer_stop_dialog.js",
            "bf_timesheet_timer/static/src/js/bf_timer_systray.js",
            "bf_timesheet_timer/static/src/xml/bf_timer_stop_dialog.xml",
            "bf_timesheet_timer/static/src/xml/bf_timer_systray.xml",
        ],
    },
    "installable": True,
    "application": False,
}
