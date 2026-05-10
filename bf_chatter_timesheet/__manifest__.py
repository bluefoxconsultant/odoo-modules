{
    "name": "Blue Fox — Feuille de temps depuis le chatter",
    "summary": "Case à cocher dans le composer du chatter pour journaliser une feuille de temps en même temps qu'une note interne.",
    "version": "18.0.1.0.0",
    "category": "Services/Timesheets",
    "author": "Blue Fox Inc.",
    "website": "https://bluefoxconsultant.com",
    "license": "LGPL-3",
    "depends": [
        "bf_timesheet_timer",
        "mail",
        "hr_timesheet",
        "project",
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "bf_chatter_timesheet/static/src/js/*.js",
            "bf_chatter_timesheet/static/src/xml/*.xml",
            "bf_chatter_timesheet/static/src/scss/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
