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

    # K-of-N support: actual subset of combination resources that took the slot.
    # Equal to combination_id.resource_ids when min_required is 0 / >= N
    # (standard OCA behavior). For K-of-N (min_required = K < N), holds the K
    # resources that were free at booking time. Used by _prepare_meeting_vals
    # to add only those partners as calendar.event attendees.
    # Stored computed so it's set BEFORE _sync_meeting fires (which is
    # triggered on the same write that sets `start`).
    attendee_resource_ids = fields.Many2many(
        "resource.resource",
        "rb_attendee_resource_rel",
        "booking_id",
        "resource_id",
        string="Assigned Resources",
        compute="_compute_attendee_resources",
        store=True,
        copy=False,
        help="Subset of the combination's resources actually assigned to "
             "this booking (relevant for K-of-N combinations).",
    )

    @api.depends("start", "stop", "combination_id", "combination_id.resource_ids",
                 "combination_id.min_required")
    def _compute_attendee_resources(self):
        import pytz
        from itertools import combinations as _icombs
        from odoo.addons.resource.models.utils import Intervals
        for rec in self:
            combo = rec.combination_id
            if not combo:
                rec.attendee_resource_ids = [(5, 0, 0)]
                continue
            n = len(combo.resource_ids)
            k = combo.min_required
            if k <= 0 or k >= n or not rec.start or not rec.stop:
                rec.attendee_resource_ids = [(6, 0, combo.resource_ids.ids)]
                continue
            start_aware = pytz.utc.localize(rec.start) if rec.start.tzinfo is None else rec.start
            stop_aware = pytz.utc.localize(rec.stop) if rec.stop.tzinfo is None else rec.stop
            base = Intervals([(start_aware, stop_aware, combo)])
            sorted_resources = combo.resource_ids.sorted(lambda r: r.id)
            picked = None
            for subset in _icombs(sorted_resources, k):
                subset_intervals = base
                ok = True
                for res in subset:
                    calendar = combo.forced_calendar_id or res.calendar_id
                    free = calendar._work_intervals_batch(start_aware, stop_aware, res)[res.id]
                    subset_intervals &= free
                    if not subset_intervals:
                        ok = False
                        break
                if ok and subset_intervals:
                    picked = subset
                    break
            ids_picked = [r.id for r in picked] if picked else combo.resource_ids[:k].ids
            rec.attendee_resource_ids = [(6, 0, ids_picked)]

    # QWeb mail templates have non-deterministic behaviour with
    # format_datetime(tz=...) in some render paths, so we precompute the
    # localized date/time strings here for the booking type's resource calendar
    # timezone (defaults to America/Toronto).
    start_date_local = fields.Char(
        compute="_compute_start_local_strings",
        string="Local Start Date",
    )
    start_time_local = fields.Char(
        compute="_compute_start_local_strings",
        string="Local Start Time",
    )

    @api.depends("start", "type_id.resource_calendar_id.tz")
    def _compute_start_local_strings(self):
        import pytz
        for rec in self:
            if not rec.start:
                rec.start_date_local = ""
                rec.start_time_local = ""
                continue
            tz_name = rec.type_id.resource_calendar_id.tz or "America/Toronto"
            try:
                start_dt = rec.start
                if isinstance(start_dt, str):
                    start_dt = fields.Datetime.from_string(start_dt)
                aware_utc = pytz.utc.localize(start_dt) if start_dt.tzinfo is None else start_dt.astimezone(pytz.utc)
                local_dt = aware_utc.astimezone(pytz.timezone(tz_name))
                rec.start_date_local = local_dt.strftime("%Y-%m-%d")
                rec.start_time_local = local_dt.strftime("%H:%M")
            except Exception as e:
                _logger.warning("start_local compute failed for booking %s: %s", rec.id, e)
                rec.start_date_local = rec.start.strftime("%Y-%m-%d") if rec.start else ""
                rec.start_time_local = rec.start.strftime("%H:%M") if rec.start else ""

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
        """Override to generate video URL + strip non-attendee resource partners
        for K-of-N bookings.

        OCA's action_confirm unions in `combination_id.resource_ids.user_id.partner_id`
        on the meeting (re-adding ALL combination resources, including non-attendees
        for K-of-N). We post-process to keep only `attendee_resource_ids` partners.
        """
        result = super().action_confirm()
        for booking in self:
            # K-of-N: remove non-attendee resource partners from the meeting.
            combo = booking.combination_id
            if combo and 0 < combo.min_required < len(combo.resource_ids) and booking.meeting_id:
                full_partners = combo.resource_ids.filtered(
                    lambda r: r.resource_type == "user"
                ).mapped("user_id.partner_id")
                attendee_partners = booking.attendee_resource_ids.filtered(
                    lambda r: r.resource_type == "user"
                ).mapped("user_id.partner_id")
                excluded = full_partners - attendee_partners
                if excluded:
                    booking.meeting_id.partner_ids -= excluded
            if (
                booking.type_id.video_provider
                and booking.type_id.video_provider != "none"
            ):
                url = booking._generate_video_url()
                if url:
                    booking.videocall_location = url
        return result

    def _prepare_meeting_vals(self):
        """Override to use attendee_resource_ids (K-of-N aware) instead of
        combination_id.resource_ids when populating calendar.event partners."""
        vals = super()._prepare_meeting_vals()
        if not self.attendee_resource_ids:
            return vals
        # Replace resource_partners with K-of-N subset
        full_resource_partners = self.combination_id.resource_ids.filtered(
            lambda res: res.resource_type == "user"
        ).mapped("user_id.partner_id")
        attendee_partners = self.attendee_resource_ids.filtered(
            lambda res: res.resource_type == "user"
        ).mapped("user_id.partner_id")
        # Remove any partners from the full set that aren't in the K subset,
        # then ensure the K subset partners are present.
        partner_cmd = list(vals.get("partner_ids", []))
        # Strip OCA's add commands for non-attendee resource partners
        excluded_partner_ids = (full_resource_partners - attendee_partners).ids
        partner_cmd = [
            cmd for cmd in partner_cmd
            if not (cmd[0] == 4 and cmd[1] in excluded_partner_ids)
        ]
        # Ensure attendee subset is added
        for p in attendee_partners:
            if not any(c[0] == 4 and c[1] == p.id for c in partner_cmd):
                partner_cmd.append((4, p.id, 0))
        vals["partner_ids"] = partner_cmd
        return vals

    def action_cancel(self):
        """Override to preserve access_token AND unlink the orphan calendar.event.

        Two OCA resource_booking gotchas patched here:

        1. action_cancel clears access_token, which breaks the "Voir le
           rendez-vous" link in previously-sent confirmation emails. We
           preserve the token so the booker still lands on the confirmation
           page (showing cancelled state).
        2. action_cancel sets active=False on the booking but leaves the
           linked calendar.event behind. The orphan event keeps blocking
           slots in combinations._get_intervals(), so the same combination
           shows "no availability" on slots that should be free. We unlink
           the calendar.event after cancellation. The
           calendar_event._track_subtype override already suppresses any
           tracking notifications on these events, so the unlink is silent.
        """
        tokens = {b.id: b.access_token for b in self}
        meeting_ids = [b.meeting_id.id for b in self if b.meeting_id]
        result = super().action_cancel()
        for booking in self:
            token = tokens.get(booking.id)
            if token and not booking.access_token:
                booking.sudo().access_token = token
        if meeting_ids:
            # Belt + suspenders. Current OCA action_unschedule unlinks the
            # meeting before we get here, so .exists() filters those out and
            # this is usually a no-op. But if a future OCA regression or
            # an alternative cancel path leaves the event behind, this
            # ensures the slot is freed immediately.
            events = (
                self.env["calendar.event"]
                .sudo()
                .browse(meeting_ids)
                .exists()
            )
            if events:
                events.with_context(
                    no_mail_to_attendees=True,
                    tracking_disable=True,
                    mail_notrack=True,
                ).unlink()
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
            import pytz
            import requests

            booker = self.partner_id or (self.partner_ids[:1] if self.partner_ids else False)
            booker_name = (booker.name if booker else "").strip() or "Invité"
            tz_name = self.type_id.resource_calendar_id.tz or "America/Toronto"
            local_start = ""
            if self.start:
                local_start = pytz.utc.localize(self.start).astimezone(
                    pytz.timezone(tz_name)
                ).strftime("%Y-%m-%d %H:%M")
            type_name = (self.type_id.name or "Rendez-vous").strip()
            room_name = " | ".join(p for p in (type_name, booker_name, local_start) if p)
            # Nextcloud caps room names at 200 chars
            room_name = room_name[:200]

            api_url = f"{base_url.rstrip('/')}/ocs/v2.php/apps/spreed/api/v4/room"
            response = requests.post(
                api_url,
                auth=(user, password),
                headers={
                    "OCS-APIREQUEST": "true",
                    "Accept": "application/json",
                },
                data={
                    "roomType": 3,  # public — anyone with the link can join as guest
                    "roomName": room_name,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            room_token = data["ocs"]["data"]["token"]
            return f"{base_url.rstrip('/')}/index.php/call/{room_token}"
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
