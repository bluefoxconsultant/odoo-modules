{
    "name": "Blue Fox Appointment",
    "version": "18.0.2.15.5",
    "category": "Appointments",
    "summary": "Public self-service booking pages extending Resource Booking",
    "author": "Blue Fox Inc",
    "license": "AGPL-3",
    "depends": ["resource_booking", "portal", "mail", "project", "privacy_consent"],
    "data": [
        "security/appointment_security.xml",
        "security/ir.model.access.csv",
        "data/appointment_mail_templates.xml",
        "data/appointment_cron.xml",
        "data/appointment_menu.xml",
        "templates/appointment_public.xml",
        "templates/appointment_confirmation.xml",
        "views/resource_booking_type_views.xml",
        "views/resource_booking_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "bf_appointment/static/src/js/timezone_detect.js",
            "bf_appointment/static/src/scss/appointment.scss",
        ],
    },
    "installable": True,
    "application": False,
}
