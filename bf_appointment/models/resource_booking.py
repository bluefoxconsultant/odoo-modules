import base64
import logging
import uuid
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


def _escape_ics(value):
    """Escape a string for use in ICS property values per RFC 5545."""
    if not value:
        return ""
    # Backslash must be escaped first
    value = value.replace("\\", "\\\\")
    # Semicolons and commas are special in ICS
    value = value.replace(";", "\\;")
    value = value.replace(",", "\\,")
    # Newlines must be escaped as literal \n
    value = value.replace("\r\n", "\\n")
    value = value.replace("\r", "\\n")
    value = value.replace("\n", "\\n")
    return value


class ResourceBooking(models.Model):
    _inherit = "resource.booking"

    video_room_token = fields.Char(
        string="Video Room Token",
        copy=False,
        help="Unique token for the video room URL.",
    )
    reminder_sent = fields.Boolean(
        default=False,
        copy=False,
        help="Whether the reminder email has been sent.",
    )
    sent_schedule_ids = fields.Many2many(
        "appointment.email.schedule",
        string="Sent Email Schedules",
        copy=False,
    )
    intake_answer_ids = fields.One2many(
        "appointment.intake.answer",
        "booking_id",
        string="Intake Answers",
    )

    def action_confirm(self):
        """Override to generate video URL on confirmation."""
        result = super().action_confirm()
        for booking in self:
            if (
                booking.type_id.video_provider
                and booking.type_id.video_provider != "none"
            ):
                url = booking._generate_video_url()
                if url:
                    booking.videocall_location = url
        return result

    def _generate_video_url(self):
        """Generate video meeting URL based on the type's video provider."""
        self.ensure_one()
        provider = self.type_id.video_provider
        if not provider or provider == "none":
            return False
        if not self.video_room_token:
            self.video_room_token = uuid.uuid4().hex[:12]
        if provider == "jitsi":
            return self._generate_jitsi_url()
        if provider == "nextcloud_talk":
            return self._generate_nc_talk_url()
        return False

    def _generate_jitsi_url(self):
        """Generate a Jitsi Meet URL."""
        ICP = self.env["ir.config_parameter"].sudo()
        domain = ICP.get_param(
            "bf_appointment.jitsi_domain", "meet.jit.si"
        )
        room_name = f"bf-{self.id}-{self.video_room_token}"
        return f"https://{domain}/{room_name}"

    def _generate_nc_talk_url(self):
        """Generate a Nextcloud Talk room URL via API."""
        ICP = self.env["ir.config_parameter"].sudo()
        base_url = ICP.get_param("bf_appointment.nc_talk_base_url")
        user = ICP.get_param("bf_appointment.nc_talk_user")
        password_enc = ICP.get_param("bf_appointment.nc_talk_password_encrypted")
        if not all([base_url, user, password_enc]):
            _logger.warning(
                "Nextcloud Talk not configured, falling back to type videocall_location"
            )
            return self.type_id.videocall_location or False
        password = self._decrypt_nc_talk_password(password_enc)
        if not password:
            return self.type_id.videocall_location or False
        try:
            import requests

            api_url = f"{base_url.rstrip('/')}/ocs/v2.php/apps/spreed/api/v4/room"
            response = requests.post(
                api_url,
                auth=(user, password),
                headers={
                    "OCS-APIREQUEST": "true",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "roomType": 3,  # public
                    "roomName": f"Rendez-vous #{self.id}",
                },
                timeout=5,
            )
            response.raise_for_status()
            data = response.json()
            room_token = data["ocs"]["data"]["token"]
            return f"{base_url.rstrip('/')}/call/{room_token}"
        except Exception as e:
            _logger.error("Failed to create Nextcloud Talk room: %s", e)
            return self.type_id.videocall_location or False

    def _decrypt_nc_talk_password(self, encrypted_value):
        """Decrypt Nextcloud Talk password using Fernet.

        Returns False (with an error log) if the cryptography package is
        missing, the encryption key is unset, or decryption fails. Never
        falls back to returning the raw ciphertext, which could leak an
        un-decryptable value to the API as if it were a password.
        """
        if not encrypted_value:
            return False
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError:
            _logger.error(
                "cryptography package not installed - cannot decrypt NC Talk password"
            )
            return False
        ICP = self.env["ir.config_parameter"].sudo()
        key = ICP.get_param("bf_appointment.encryption_key")
        if not key:
            _logger.error(
                "bf_appointment.encryption_key not set - cannot decrypt NC Talk password"
            )
            return False
        try:
            f = Fernet(key.encode())
            return f.decrypt(encrypted_value.encode()).decode()
        except InvalidToken:
            _logger.error(
                "NC Talk password decryption failed - key mismatch or corrupted data"
            )
            return False
        except Exception:
            _logger.exception("NC Talk password decryption error")
            return False

    def get_duration_display(self):
        """Return human-readable duration label."""
        self.ensure_one()
        minutes = int(self.duration * 60)
        if minutes >= 60:
            h = minutes // 60
            m = minutes % 60
            return f"{h}h{m:02d}" if m else f"{h}h"
        return f"{minutes} min"

    # ---- ICS Generation ----

    def _generate_ics_data(self):
        """Generate ICS calendar data for this booking."""
        self.ensure_one()
        if not self.start:
            return False
        duration_hours = self.duration or 1.0
        stop = self.start + timedelta(hours=duration_hours)
        base_url = self.get_base_url()
        booking_url = (
            f"{base_url}/appointment/b/{self.id}/{self.access_token}"
        )
        cancel_url = f"{booking_url}/cancel"
        schedule_url = f"{booking_url}/schedule"
        # Build description with all pertinent info
        desc_parts = [self.type_id.name or _("Rendez-vous")]
        desc_parts.append("")
        desc_parts.append(
            _("Date : %s") % self.start.strftime("%A %d %B %Y")
        )
        desc_parts.append(
            _("Heure : %s") % self.start.strftime("%H:%M")
        )
        desc_parts.append(
            _("Dur\u00e9e : %s") % self.get_duration_display()
        )
        if self.partner_id:
            desc_parts.append(
                _("Participant : %s") % self.partner_id.name
            )
        if self.videocall_location:
            desc_parts.append("")
            desc_parts.append(
                _("Vid\u00e9oconf\u00e9rence : %s") % self.videocall_location
            )
        if self.location:
            desc_parts.append(_("Lieu : %s") % self.location)
        # Intake form answers
        if self.intake_answer_ids:
            desc_parts.append("")
            for answer in self.intake_answer_ids:
                desc_parts.append(
                    f"{answer.field_name} : {answer.value}"
                )
        desc_parts.append("")
        desc_parts.append(_("Voir mon rendez-vous : %s") % booking_url)
        desc_parts.append(_("Modifier l'horaire : %s") % schedule_url)
        desc_parts.append(_("Annuler : %s") % cancel_url)
        description = "\\n".join(desc_parts)
        # Location
        location = self.videocall_location or self.location or ""
        # UID
        uid = f"bf-appointment-{self.id}@{base_url.split('//')[1] if '//' in base_url else 'odoo'}"
        # Format dates
        dtstart = self.start.strftime("%Y%m%dT%H%M%SZ")
        dtend = stop.strftime("%Y%m%dT%H%M%SZ")
        dtstamp = fields.Datetime.now().strftime("%Y%m%dT%H%M%SZ")
        summary = _escape_ics(
            self.name or (_("RDV - %s") % self.type_id.name)
        )
        ics = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//Blue Fox Inc//BF Appointment//FR\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart}\r\n"
            f"DTEND:{dtend}\r\n"
            f"SUMMARY:{summary}\r\n"
        )
        if location:
            ics += f"LOCATION:{_escape_ics(location)}\r\n"
        if self.videocall_location:
            ics += f"URL:{self.videocall_location}\r\n"
        ics += f"DESCRIPTION:{_escape_ics(description)}\r\n"
        ics += (
            "STATUS:CONFIRMED\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        return ics.encode("utf-8")

    def _get_ics_attachment(self):
        """Return an ir.attachment record with the ICS file for email attachment."""
        self.ensure_one()
        ics_data = self._generate_ics_data()
        if not ics_data:
            return self.env["ir.attachment"]
        attachment = self.env["ir.attachment"].create({
            "name": _("rendez-vous.ics"),
            "type": "binary",
            "datas": base64.b64encode(ics_data),
            "mimetype": "text/calendar",
            "res_model": "resource.booking",
            "res_id": self.id,
        })
        return attachment

    def _send_appointment_email(self, template):
        """Send an appointment email with ICS attachment.

        Respects the partner's language for both the email template
        rendering and the ICS attachment content.
        """
        self.ensure_one()
        # Use partner's language for ICS content
        partner_lang = self.partner_id.lang or self.env.lang or "fr_CA"
        booking_lang = self.with_context(lang=partner_lang)
        attachment = booking_lang._get_ics_attachment()
        ctx = {}
        if attachment:
            ctx["default_attachment_ids"] = [(4, attachment.id)]
        template.with_context(**ctx).send_mail(
            self.id,
            force_send=True,
            email_values={
                "attachment_ids": [(4, attachment.id)] if attachment else [],
            },
        )

    # ---- Cron ----

    @api.model
    def _cron_send_appointment_reminders(self):
        """Backward compat alias for old cron."""
        return self._cron_send_appointment_emails()

    @api.model
    def _cron_send_appointment_emails(self):
        """Send scheduled appointment emails (reminders + follow-ups)."""
        now = fields.Datetime.now()
        # Process confirmed bookings with active schedules
        bookings = self.search([
            ("state", "in", ("confirmed", "scheduled")),
            ("start", "!=", False),
            ("type_id.email_schedule_ids", "!=", False),
        ])
        for booking in bookings:
            for schedule in booking.type_id.email_schedule_ids.filtered("active"):
                if schedule in booking.sent_schedule_ids:
                    continue
                should_send = False
                if schedule.trigger == "before":
                    send_at = booking.start - timedelta(hours=schedule.hours)
                    should_send = now >= send_at and now < booking.start
                elif schedule.trigger == "after":
                    stop = booking.start + timedelta(
                        hours=booking.duration or 1.0
                    )
                    send_at = stop + timedelta(hours=schedule.hours)
                    should_send = now >= send_at
                if should_send:
                    try:
                        booking._send_appointment_email(schedule.template_id)
                        booking.sent_schedule_ids = [(4, schedule.id)]
                    except Exception as e:
                        _logger.error(
                            "Failed to send scheduled email for booking %d "
                            "(schedule %d): %s",
                            booking.id,
                            schedule.id,
                            e,
                        )
