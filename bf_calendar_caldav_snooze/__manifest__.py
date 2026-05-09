{
    "name": "BF Calendar CalDAV Snooze Bridge",
    "summary": "RFC 9074 bridge: mirror calendar reminder snooze/dismiss "
               "between Odoo and Nextcloud CalDAV (.ics VALARM)",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://bluefox.ca",
    "author": "Blue Fox Inc.",
    "license": "LGPL-3",
    "depends": [
        "bf_email_management",
        "calendar_nextcloud_sync",
    ],
    "data": [
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
