import base64
import logging
import uuid
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

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


# Minimal VTIMEZONE block for America/Toronto (EST/EDT). Hard-coded because it
# covers every BF booking today, and including a VTIMEZONE is required by
# RFC 5545 when TZID references are used in DTSTART/DTEND.
_VTIMEZONE_AMERICA_TORONTO = (
    "BEGIN:VTIMEZONE\r\n"
    "TZID:America/Toronto\r\n"
    "BEGIN:STANDARD\r\n"
    "DTSTART:19701101T020000\r\n"
    "TZOFFSETFROM:-0400\r\n"
    "TZOFFSETTO:-0500\r\n"
    "TZNAME:EST\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\r\n"
    "END:STANDARD\r\n"
    "BEGIN:DAYLIGHT\r\n"
    "DTSTART:19700308T020000\r\n"
    "TZOFFSETFROM:-0500\r\n"
    "TZOFFSETTO:-0400\r\n"
    "TZNAME:EDT\r\n"
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\r\n"
    "END:DAYLIGHT\r\n"
    "END:VTIMEZONE\r\n"
)


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

    def _sync_meeting(self):
        """Suppress calendar.event invite/update notifications.

        OCA's resource_booking._sync_meeting creates and writes the linked
        calendar.event with mail_notify_author=True (set in OCA's
        calendar_event create override) and from_ui=True on reschedule.
        Both paths fire the stock Odoo "Date mise à jour" notification to
        the booker, on top of our own branded confirmation/reminder
        emails. Inject suppression context before delegating so attendees
        do not get the duplicate calendar invite.
        """
        return super(
            ResourceBooking,
            self.with_context(
                no_mail_to_attendees=True,
                mail_notify_author=False,
                mail_create_nosubscribe=True,
                mail_create_nolog=True,
                mail_notrack=True,
                tracking_disable=True,
                dont_notify=True,
            ),
        )._sync_meeting()

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

    def action_cancel(self):
        """Override to preserve access_token after cancellation.

        OCA resource_booking clears access_token on cancel, which breaks the
        "Voir le rendez-vous" link in previously-sent confirmation emails. We
        still archive the record (active=False), but keep the token so the
        booker can land on the confirmation page and see the cancelled state.
        """
        tokens = {b.id: b.access_token for b in self}
        result = super().action_cancel()
        for booking in self:
            token = tokens.get(booking.id)
            if token and not booking.access_token:
                booking.sudo().access_token = token
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

        Raises UserError if the encryption key is missing or decryption fails,
        instead of falling back to returning the raw (potentially plaintext) value.
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
        from ._crypto import get_encryption_key
        key = get_encryption_key(self.env, auto_generate=False)
        if not key:
            _logger.error(
                "bf_appointment Fernet key not set (env/odoo.conf/ICP) - cannot decrypt NC Talk password"
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
        description = "\n".join(desc_parts)
        # Location
        location = self.videocall_location or self.location or ""
        # UID
        uid = f"bf-appointment-{self.id}@{base_url.split('//')[1] if '//' in base_url else 'odoo'}"
        # Format dates. Odoo stores datetimes naive-UTC; render with TZID so
        # calendar clients display the booking in the booker's local time
        # (the same time shown on the public booking page). The DTSTAMP stays
        # UTC per RFC 5545 (§3.8.7.2).
        tzname = self._get_ics_tzname()
        tz = ZoneInfo(tzname)
        start_local = self.start.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        end_local = stop.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        dtstart = start_local.strftime("%Y%m%dT%H%M%S")
        dtend = end_local.strftime("%Y%m%dT%H%M%S")
        dtstamp = fields.Datetime.now().strftime("%Y%m%dT%H%M%SZ")
        summary = _escape_ics(
            self.name or (_("RDV - %s") % self.type_id.name)
        )
        # Organizer/Attendee: METHOD:REQUEST requires an ORGANIZER (RFC 5546);
        # ATTENDEE makes the invite RSVP-able in Outlook / Google / Apple Mail.
        organizer_email = (
            self.env.company.email
            or "bonjour@bluefoxconsultant.com"
        )
        organizer_name = _escape_ics(
            self.env.company.name or "Blue Fox"
        )
        ics = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//Blue Fox Inc//BF Appointment//FR\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:REQUEST\r\n"
            + (_VTIMEZONE_AMERICA_TORONTO if tzname == "America/Toronto" else "")
            + "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART;TZID={tzname}:{dtstart}\r\n"
            f"DTEND;TZID={tzname}:{dtend}\r\n"
            f"SUMMARY:{summary}\r\n"
            f'ORGANIZER;CN="{organizer_name}":mailto:{organizer_email}\r\n'
        )
        if self.partner_id and self.partner_id.email:
            attendee_name = _escape_ics(self.partner_id.name or "")
            ics += (
                f'ATTENDEE;CN="{attendee_name}";ROLE=REQ-PARTICIPANT;'
                f"PARTSTAT=NEEDS-ACTION;RSVP=TRUE:"
                f"mailto:{self.partner_id.email}\r\n"
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

    def _get_ics_tzname(self):
        """Return the IANA TZ name used to render DTSTART/DTEND in the ICS.

        Priority: booker partner → assigned user → calendar → America/Toronto.
        res.company has no native ``tz`` field, so we read it from the
        company's resource_calendar_id instead (and from the booking's
        own resource_calendar_id as a closer match).
        """
        self.ensure_one()
        cal_company = self.env.company.resource_calendar_id
        cal_type = self.type_id.resource_calendar_id
        for candidate in (
            self.partner_id.tz if self.partner_id else None,
            self.user_id.tz if self.user_id else None,
            cal_type.tz if cal_type else None,
            cal_company.tz if cal_company else None,
        ):
            if candidate:
                try:
                    ZoneInfo(candidate)
                    return candidate
                except Exception:
                    continue
        return "America/Toronto"

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

    def _send_appointment_email(self, template, attach_ics=True):
        """Send an appointment email with optional ICS attachment.

        Respects the partner's language for both the email template
        rendering and the ICS attachment content. Pass ``attach_ics=False``
        for follow-up templates (suivi immédiat / 1h / 2h après) where the
        booking has already happened — re-sending an ICS REQUEST for a past
        event would just clutter the recipient's calendar client.
        """
        self.ensure_one()
        # Guarantee access_token: portal links in templates render empty when
        # access_token is False, producing 404s like /appointment/b/22/. The
        # public flow calls _portal_ensure_token() at create time, but cron
        # paths and admin-confirmed bookings can still reach this method
        # without a token.
        if not self.access_token:
            self._portal_ensure_token()
        # Use partner's language for ICS content
        partner_lang = self.partner_id.lang or self.env.lang or "fr_CA"
        booking_lang = self.with_context(lang=partner_lang)
        attachment = booking_lang._get_ics_attachment() if attach_ics else False
        # Create the mail.mail without sending, attach the ICS explicitly,
        # then send. Going through email_values={'attachment_ids': ...} on
        # send_mail() lost attachments in production (confirmation arrived
        # without ICS in QA on 2026-04-25); writing to the record directly is
        # the only path Odoo 18 honors reliably.
        mail_id = template.send_mail(self.id, force_send=False)
        mail = self.env["mail.mail"].browse(mail_id)
        if attachment:
            mail.write({"attachment_ids": [(4, attachment.id)]})
        mail.send()

    # ---- Cron ----

    @api.model
    def _cron_send_appointment_reminders(self):
        """Backward compat alias for old cron."""
        return self._cron_send_appointment_emails()

    # Postgres advisory-lock key used to serialize cron execution.
    # Picked arbitrarily; only this cron uses it.
    _CRON_ADVISORY_LOCK_KEY = 0x4250414F4C434C4B  # "BPAOLCLK"

    @api.model
    def _cron_send_appointment_emails(self):
        """Send scheduled appointment emails (reminders + follow-ups).

        Acquires a transaction-scoped Postgres advisory lock so two parallel
        runs (multi-worker cron, or scheduled tick + manual "Run Manually"
        click) cannot both pass the sent_schedule_ids check and double-send.
        Without this guard, QA on 2026-04-25 received the 24h reminder twice
        (38s apart) because the manual trigger raced the scheduled tick.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_xact_lock(%s)",
            (self._CRON_ADVISORY_LOCK_KEY,),
        )
        if not self.env.cr.fetchone()[0]:
            _logger.info(
                "bf_appointment cron already running on another worker, skipping"
            )
            return
        now = fields.Datetime.now()
        bookings = self.search([
            ("state", "in", ("confirmed", "scheduled")),
            ("start", "!=", False),
            ("type_id.email_schedule_ids", "!=", False),
        ])
        for booking in bookings:
            for schedule in booking.type_id.email_schedule_ids.filtered("active"):
                booking.invalidate_recordset(["sent_schedule_ids"])
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
                if not should_send:
                    continue
                # Claim the schedule BEFORE sending so a transient send
                # failure does not retry forever, and so any concurrent path
                # that bypasses the advisory lock still sees the claim.
                booking.sent_schedule_ids = [(4, schedule.id)]
                # Skip ICS on "after" follow-ups — the meeting already
                # happened, so re-sending the calendar invite is noise.
                attach_ics = schedule.trigger != "after"
                try:
                    booking._send_appointment_email(
                        schedule.template_id, attach_ics=attach_ics
                    )
                except Exception as e:
                    _logger.error(
                        "Failed to send scheduled email for booking %d "
                        "(schedule %d): %s",
                        booking.id,
                        schedule.id,
                        e,
                    )
