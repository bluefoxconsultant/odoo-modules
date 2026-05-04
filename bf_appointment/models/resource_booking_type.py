import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResourceBookingType(models.Model):
    _inherit = "resource.booking.type"

    project_id = fields.Many2one(
        "project.project",
        string="Projet associé",
        help="Projet Odoo dans lequel les tâches issues du Meeting Processor seront créées.",
    )
    is_public = fields.Boolean(
        string="Public Booking Page",
        default=False,
        help="Show this booking type on the public /appointment page.",
    )
    slug = fields.Char(
        string="URL Slug",
        index=True,
        copy=False,
        help="URL-friendly identifier for the public booking page.",
    )
    public_description = fields.Html(
        string="Public Description",
        translate=True,
        sanitize=True,
        help="Description shown to visitors on the public booking page.",
    )
    public_image = fields.Image(
        string="Public Image",
        max_width=512,
        max_height=512,
    )
    sequence = fields.Integer(default=10)
    video_provider = fields.Selection(
        [
            ("none", "None"),
            ("jitsi", "Jitsi Meet"),
            ("nextcloud_talk", "Nextcloud Talk"),
        ],
        string="Video Provider",
        default="nextcloud_talk",
    )
    is_in_person = fields.Boolean(
        string="In-Person Available",
        default=False,
        help="Indicate that in-person meetings are available for this type.",
    )
    reminder_hours = fields.Float(
        string="Reminder Before (hours)",
        default=24.0,
        help="Hours before appointment to send a reminder email.",
    )
    color_hex = fields.Char(
        string="Accent Color",
        default="#29ABE2",
        help="Hex color for the public page accent.",
    )
    duration_options = fields.Char(
        string="Duration Options (min)",
        help="Comma-separated list of selectable durations in minutes, "
        "e.g. '15,30,45,60'. Leave empty to use the fixed duration.",
    )
    default_duration = fields.Float(
        string="Default Duration (hours)",
        help="Pre-selected duration on the public page. "
        "Must match one of the duration options (in hours, e.g. 0.5 = 30 min).",
    )

    def get_duration_choices(self):
        """Return list of (hours_float, display_label) tuples for the template."""
        self.ensure_one()
        if not self.duration_options:
            return []
        choices = []
        for raw in self.duration_options.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                minutes = int(raw)
            except ValueError:
                continue
            hours = minutes / 60.0
            if minutes >= 60:
                h = minutes // 60
                m = minutes % 60
                label = f"{h}h{m:02d}" if m else f"{h}h"
            else:
                label = f"{minutes} min"
            choices.append((hours, label))
        return choices
    intake_field_ids = fields.One2many(
        "appointment.intake.field",
        "type_id",
        string="Intake Form Fields",
    )
    email_schedule_ids = fields.One2many(
        "appointment.email.schedule",
        "type_id",
        string="Email Schedules",
    )

    _sql_constraints = [
        (
            "slug_unique",
            "UNIQUE(slug)",
            "The URL slug must be unique.",
        ),
    ]

    @api.onchange("name")
    def _onchange_name_set_slug(self):
        for record in self:
            if record.name and not record.slug:
                record.slug = self._generate_slug(record.name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_public") and not vals.get("slug") and vals.get("name"):
                vals["slug"] = self._generate_slug(vals["name"])
        records = super().create(vals_list)
        for record in records:
            if record.is_public and not record.email_schedule_ids:
                record._create_default_email_schedules()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get("is_public"):
            for record in self:
                if not record.email_schedule_ids:
                    record._create_default_email_schedules()
        return result

    def _create_default_email_schedules(self):
        """Create default email schedules for a public booking type.

        The 48h/2h/1h pre-reminders are intentionally absent : keeping a
        single 24h-before reminder avoids spamming the booker. Three
        post-meeting touchpoints stay on by design (immediate thanks,
        +1h check-in, +2h summary).
        """
        self.ensure_one()
        Schedule = self.env["appointment.email.schedule"]
        defaults = [
            ("before", 24, "bf_appointment.mail_template_reminder_1d"),
            ("after", 0, "bf_appointment.mail_template_followup_immediate"),
            ("after", 1, "bf_appointment.mail_template_followup_1h"),
            ("after", 2, "bf_appointment.mail_template_followup_2h"),
        ]
        for trigger, hours, xmlid in defaults:
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if template:
                Schedule.create({
                    "type_id": self.id,
                    "trigger": trigger,
                    "hours": hours,
                    "template_id": template.id,
                })

    @api.model
    def _generate_slug(self, name):
        """Generate a URL-friendly slug from name."""
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        slug = slug.strip("-")
        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while self.search_count([("slug", "=", slug)]):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def action_view_public_page(self):
        """Open the public appointment page for this type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/appointment/{self.slug}",
            "target": "new",
        }
