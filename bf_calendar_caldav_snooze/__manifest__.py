{
    "name": "BF Calendar CalDAV Snooze Bridge",
    "summary": "RFC 9074 bridge: mirror calendar reminder snooze/dismiss "
               "between Odoo and Nextcloud CalDAV (.ics VALARM)",
    "version": "18.0.1.1.0",
    "category": "Productivity",
    'website': 'https://bluefoxconsultant.com',
    "author": "Blue Fox Inc.",
    'license': 'LGPL-3',
    "depends": [
        "bf_email_management",
        "calendar_nextcloud_sync",
        "bf_onboarding_base",
    ],
    "data": [
        "data/cron.xml",
        "data/bf_onboarding.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
