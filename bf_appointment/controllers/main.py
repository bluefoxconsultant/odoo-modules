import hmac
import logging
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from dateutil.parser import isoparse

import pytz

from odoo.exceptions import ValidationError
from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

# Rate limiting for token validation (anti brute-force)
_token_fail_lock = threading.Lock()
_token_fail_data = defaultdict(list)  # IP -> [timestamps of failed attempts]
_TOKEN_FAIL_MAX = 10  # max failed attempts
_TOKEN_FAIL_WINDOW = 300  # per 5 minutes


def _client_ip():
    """Return the real client IP, honoring X-Forwarded-For when behind a proxy.

    Odoo's proxy_mode applies ProxyFix at the WSGI layer, which replaces
    REMOTE_ADDR with the leftmost X-Forwarded-For entry. But that rewrite only
    fires when the raw REMOTE_ADDR matches a trusted proxy. Reading the header
    ourselves as a fallback keeps the rate-limit bucket per-client instead of
    per-proxy, so a single abusive client cannot lock out everyone behind the
    reverse proxy.
    """
    try:
        env = request.httprequest.environ
        for key in ("HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR"):
            value = env.get(key, "")
            if value:
                return value.split(",")[0].strip()
        return request.httprequest.remote_addr or "unknown"
    except Exception:
        return "unknown"


def _check_token_rate_limit():
    """Return True if IP is within rate limits for token validation."""
    ip = _client_ip()
    now = time.monotonic()
    with _token_fail_lock:
        attempts = _token_fail_data[ip]
        cutoff = now - _TOKEN_FAIL_WINDOW
        _token_fail_data[ip] = [t for t in attempts if t > cutoff]
        return len(_token_fail_data[ip]) < _TOKEN_FAIL_MAX


def _record_token_failure():
    """Record a failed token validation attempt for rate limiting."""
    ip = _client_ip()
    now = time.monotonic()
    with _token_fail_lock:
        _token_fail_data[ip].append(now)


# BF only ships fr_CA and en_CA. Anything en* maps to en_CA, everything else
# (and missing header) falls back to fr_CA.
_BF_DEFAULT_LANG = "fr_CA"


def _resolve_lang_from_accept_header():
    """Return en_CA if Accept-Language asks for English, fr_CA otherwise."""
    try:
        header = request.httprequest.headers.get("Accept-Language", "")
    except Exception:
        return _BF_DEFAULT_LANG
    if not header:
        return _BF_DEFAULT_LANG
    # Simple parse: take first non-q-flagged tag, lowercased.
    first = header.split(",")[0].split(";")[0].strip().lower()
    if first.startswith("en"):
        return "en_CA"
    return _BF_DEFAULT_LANG


def _apply_locale_from_request():
    """Switch request env lang based on Accept-Language. Idempotent."""
    lang = _resolve_lang_from_accept_header()
    if request.env.context.get("lang") != lang:
        request.update_context(lang=lang)


# Security headers applied to every public /appointment* response. CSP is
# permissive on inline styles because Odoo emits inline t-att-style on widgets;
# scripts and frames are locked down. frame-ancestors 'none' + X-Frame-Options
# DENY together protect against clickjacking on legacy browsers.
_APPOINTMENT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def _apply_security_headers(response):
    """Add CSP + X-Frame-Options + nosniff to a response object. No-op on redirects."""
    try:
        headers = response.headers
    except AttributeError:
        return response
    headers["Content-Security-Policy"] = _APPOINTMENT_CSP
    headers["X-Frame-Options"] = "DENY"
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Pragmatic location validation: refuse strings that are too short, lack any
# letters, or are a single short token. Rejects "abc", "123", "x", "..." while
# accepting "1072 Bellemare", "Bureau Olivier", "Café du Coin".
_LOCATION_MIN_LEN = 5
_LOCATION_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def _validate_location_format(value):
    """Return True when the location looks like a real lieu/adresse."""
    if not value or len(value) < _LOCATION_MIN_LEN:
        return False
    if not _LOCATION_RE.search(value):
        return False
    return True


class AppointmentController(Controller):

    @route(
        "/appointment",
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def appointment_landing(self, **kwargs):
        """Public landing page listing all public booking types."""
        _apply_locale_from_request()
        BookingType = request.env["resource.booking.type"].sudo()
        types = BookingType.search(
            [("is_public", "=", True)],
            order="sequence, name",
        )
        response = request.render(
            "bf_appointment.appointment_landing",
            {"booking_types": types},
        )
        return _apply_security_headers(response)

    @route(
        "/appointment/<string:slug>",
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def appointment_type_page(self, slug, **kwargs):
        """Detail page for a specific booking type with intake form."""
        _apply_locale_from_request()
        booking_type = self._get_type_by_slug(slug)
        if not booking_type:
            return request.redirect("/appointment")
        response = request.render(
            "bf_appointment.appointment_type_page",
            {"booking_type": booking_type, "error": kwargs.get("error")},
        )
        return _apply_security_headers(response)

    @route(
        "/appointment/<string:slug>/book",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def appointment_book(self, slug, **kwargs):
        """Create a pending booking from the intake form."""
        _apply_locale_from_request()
        booking_type = self._get_type_by_slug(slug)
        if not booking_type:
            return request.redirect("/appointment")
        # Honeypot spam check
        if kwargs.get("website_url"):
            _logger.info("Honeypot triggered on appointment form")
            return request.redirect("/appointment")
        name = (kwargs.get("name") or "").strip()
        email = (kwargs.get("email") or "").strip()
        phone = (kwargs.get("phone") or "").strip()
        tz = (kwargs.get("tz") or "").strip()
        duration_str = (kwargs.get("duration") or "").strip()
        location_input = (kwargs.get("location") or "").strip()
        # Validate required fields
        if not name or not email:
            return request.redirect(
                f"/appointment/{slug}?error={quote_plus('Veuillez remplir tous les champs obligatoires.')}"
            )
        # Loi 25, explicit consent required for personal information collection.
        # The form has client-side `required`, but a tampered submission could
        # bypass that, so we enforce server-side too.
        if not kwargs.get("bf_consent"):
            return request.redirect(
                f"/appointment/{slug}?error={quote_plus('Veuillez accepter la politique de confidentialité pour soumettre votre demande.')}"
            )
        # If in-person without fixed location, the booker must provide one
        if booking_type.is_in_person and not booking_type.location and not location_input:
            return request.redirect(
                f"/appointment/{slug}?error={quote_plus('Veuillez indiquer un lieu de rencontre.')}"
            )
        # Validate the format of a booker-provided location: short or
        # letter-less strings ("abc", "123", "...") slip past the empty check
        # but are useless for the organizer.
        if location_input and not _validate_location_format(location_input):
            return request.redirect(
                f"/appointment/{slug}?error={quote_plus('Veuillez fournir une adresse ou un lieu reconnaissable.')}"
            )
        # Basic email validation
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return request.redirect(
                f"/appointment/{slug}?error={quote_plus('Adresse courriel invalide.')}"
            )
        # Validate timezone
        if tz and tz not in pytz.all_timezones_set:
            tz = ""
        # Validate required intake fields. We re-run _validate_intake_value so
        # a tampered select/email/phone (non-empty but invalid) is treated as
        # missing rather than silently dropped downstream.
        for field in booking_type.intake_field_ids.filtered("required"):
            key = f"intake_{field.id}"
            raw = (kwargs.get(key) or "").strip()
            if not raw or not self._validate_intake_value(field, raw):
                return request.redirect(
                    f"/appointment/{slug}?error={quote_plus(f'Le champ « {field.name} » est obligatoire.')}"
                )
        # Find or create partner
        Partner = request.env["res.partner"].sudo()
        partner = Partner.search([("email", "=ilike", email)], limit=1)
        if not partner:
            partner_vals = {
                "name": name,
                "email": email,
                "phone": phone or False,
            }
            if tz:
                partner_vals["tz"] = tz
            partner = Partner.create(partner_vals)
        else:
            # Update name if currently set to the email (auto-created contacts)
            if not partner.name or partner.name.strip().lower() == partner.email.strip().lower():
                partner.name = name
            if phone and not partner.phone:
                partner.phone = phone
            # Capture the browser-detected TZ on the partner if missing.
            # We never overwrite an existing tz: a user who manually picked
            # a different TZ in their res.users profile (e.g. a colleague
            # travelling) shouldn't have it blasted by the booking form.
            if tz and not partner.tz:
                partner.tz = tz
        # Find a real user for organizer (first resource's user or admin)
        organizer_user = (
            booking_type.combination_rel_ids[:1]
            .combination_id.resource_ids[:1]
            .filtered(lambda r: r.resource_type == "user")
            .user_id
        )
        if not organizer_user:
            organizer_user = request.env.ref("base.user_admin").sudo()
        # Create pending booking, suppress ALL notifications
        Booking = request.env["resource.booking"].sudo().with_context(
            no_mail_to_attendees=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
            tracking_disable=True,
            mail_notrack=True,
        )
        booking_vals = {
            "type_id": booking_type.id,
            "partner_ids": [(6, 0, [partner.id])],
            "name": f"RDV - {name}",
            "user_id": organizer_user.id,
        }
        # Booker-provided location overrides type's blank location for in-person types
        if location_input:
            booking_vals["location"] = location_input
        # Apply custom duration if provided and valid
        if duration_str and booking_type.duration_options:
            try:
                duration_hours = float(duration_str)
                valid_durations = [
                    c[0] for c in booking_type.get_duration_choices()
                ]
                if duration_hours in valid_durations:
                    booking_vals["duration"] = duration_hours
            except (ValueError, TypeError):
                pass
        booking = Booking.create(booking_vals)
        # Save custom field answers
        self._save_intake_answers(booking, booking_type, kwargs)
        # Generate access token
        booking._portal_ensure_token()
        # Build schedule URL
        schedule_url = (
            f"/appointment/b/{booking.id}/{booking.access_token}/schedule"
        )
        if tz:
            schedule_url += f"?tz={tz}"
        return request.redirect(schedule_url)

    @route(
        [
            "/appointment/b/<int:booking_id>/<string:token>/schedule",
            "/appointment/b/<int:booking_id>/<string:token>/schedule/<int:year>/<int:month>",
        ],
        type="http",
        auth="public",
        website=True,
    )
    def appointment_schedule(
        self, booking_id, token, year=None, month=None, **kwargs
    ):
        """Show the scheduling calendar for the booking."""
        _apply_locale_from_request()
        booking_sudo = self._get_booking_sudo(booking_id, token)
        if not booking_sudo:
            return request.redirect("/appointment")
        # Cancelled bookings cannot be rescheduled: OCA clears the resource
        # combination on cancel, so any POST /confirm would 400. Route the
        # user straight to the confirmation page (which shows the cancelled
        # state) instead of a misleading calendar picker.
        if booking_sudo.state == "canceled":
            return request.redirect(
                f"/appointment/b/{booking_id}/{token}"
            )
        tz = kwargs.get("tz") or ""
        if tz and tz in pytz.all_timezones_set:
            booking_sudo = booking_sudo.with_context(tz=tz)
        calendar_ctx = booking_sudo._get_calendar_context(year, month)
        # Effective TZ for the labels next to the picker. Falls back to the
        # type's resource calendar tz so we never show an empty TZ next to
        # the slots.
        effective_tz = (
            tz
            or booking_sudo.type_id.resource_calendar_id.tz
            or "America/Toronto"
        )
        values = {
            "booking_sudo": booking_sudo,
            "access_token": token,
            "error": kwargs.get("error"),
            "visitor_tz": tz,
            "effective_tz": effective_tz,
            "common_timezones": pytz.common_timezones,
            **calendar_ctx,
        }
        response = request.render(
            "bf_appointment.appointment_schedule", values
        )
        return _apply_security_headers(response)

    @route(
        "/appointment/b/<int:booking_id>/<string:token>/confirm",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def appointment_confirm(self, booking_id, token, when, **kwargs):
        """Confirm the booking at the chosen time slot."""
        booking_sudo = self._get_booking_sudo(booking_id, token)
        if not booking_sudo:
            return request.redirect("/appointment")
        if booking_sudo.state == "canceled":
            return request.redirect(
                f"/appointment/b/{booking_id}/{token}"
            )
        try:
            when_tz_aware = isoparse(when)
            when_naive = datetime.fromtimestamp(
                when_tz_aware.timestamp(), tz=timezone.utc
            ).replace(tzinfo=None)
        except (ValueError, TypeError):
            return request.redirect(
                f"/appointment/b/{booking_id}/{token}/schedule"
                f"?error=Format de date invalide."
            )
        # Suppress ALL notifications, we send our own branded email
        booking_sudo = booking_sudo.with_context(
            no_mail_to_attendees=True,
            dont_notify=True,
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
        )
        try:
            booking_sudo.start = when_naive
        except ValidationError as error:
            tz = kwargs.get("tz", "")
            tz_param = f"&tz={tz}" if tz else ""
            return request.redirect(
                f"/appointment/b/{booking_id}/{token}"
                f"/schedule/{when_tz_aware:%Y/%m}"
                f"?error={quote_plus(str(error.args[0]))}{tz_param}"
            )
        booking_sudo.action_confirm()
        # Send our branded confirmation email with ICS attachment
        try:
            template = request.env.ref(
                "bf_appointment.mail_template_appointment_confirmation"
            ).sudo()
            booking_sudo._send_appointment_email(template)
        except Exception as e:
            _logger.error(
                "Failed to send confirmation email for booking %d: %s",
                booking_sudo.id,
                e,
            )
        # Notify the organizer (BF employee) so they get a heads-up. Stock
        # Odoo calendar.event invitations are suppressed by our
        # CalendarEvent._track_subtype override (avoids the duplicate "Date
        # mise à jour" notification storm), so we deliver our own branded
        # internal email instead. Skip if the organizer would just be the
        # booker (e.g. self-test where employee email == booker partner).
        try:
            organizer_partner = booking_sudo.user_id.partner_id
            booker_emails = booking_sudo.partner_ids.mapped("email")
            if (
                organizer_partner
                and organizer_partner.email
                and organizer_partner.email not in booker_emails
            ):
                org_template = request.env.ref(
                    "bf_appointment.mail_template_organizer_new_booking"
                ).sudo()
                booking_sudo._send_appointment_email(
                    org_template, attach_ics=True
                )
        except Exception as e:
            _logger.error(
                "Failed to notify organizer for booking %d: %s",
                booking_sudo.id,
                e,
            )
        # Mark past-due "before" schedules as already sent to prevent
        # the cron from sending all reminders at once for near-future bookings
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for schedule in booking_sudo.type_id.email_schedule_ids.filtered(
            lambda s: s.active and s.trigger == "before"
        ):
            send_at = booking_sudo.start - timedelta(hours=schedule.hours)
            if now >= send_at:
                booking_sudo.sent_schedule_ids = [(4, schedule.id)]
        return request.redirect(
            f"/appointment/b/{booking_id}/{token}"
        )

    @route(
        "/appointment/b/<int:booking_id>/<string:token>",
        type="http",
        auth="public",
        website=True,
    )
    def appointment_confirmation_page(self, booking_id, token, **kwargs):
        """Show the booking confirmation/details page."""
        _apply_locale_from_request()
        booking_sudo = self._get_booking_sudo(booking_id, token)
        if not booking_sudo:
            return request.redirect("/appointment")
        tz_name = (
            kwargs.get("tz")
            or booking_sudo.type_id.resource_calendar_id.tz
            or "UTC"
        )
        if tz_name in pytz.all_timezones_set:
            booking_sudo = booking_sudo.with_context(tz=tz_name)
        values = {
            "booking_sudo": booking_sudo,
            "access_token": token,
            "tz_name": tz_name,
        }
        response = request.render(
            "bf_appointment.appointment_confirmation_page", values
        )
        return _apply_security_headers(response)

    @route(
        "/appointment/b/<int:booking_id>/<string:token>/cancel",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
    )
    def appointment_cancel(self, booking_id, token, **kwargs):
        """Cancel a booking."""
        _apply_locale_from_request()
        booking_sudo = self._get_booking_sudo(booking_id, token)
        if not booking_sudo:
            return request.redirect("/appointment")
        # Skip if already cancelled (idempotent + avoid duplicate emails)
        already_cancelled = booking_sudo.state == "canceled"
        # Capture cancellation reason before action_cancel (it may flip
        # active=False / clear writable state in some flows).
        reason = (kwargs.get("cancellation_reason") or "").strip()
        if reason and not already_cancelled:
            booking_sudo.sudo().cancellation_reason = reason[:2000]
        booking_sudo.with_context(
            no_mail_to_attendees=True,
            tracking_disable=True,
            mail_notrack=True,
        ).action_cancel()
        # Send our branded cancellation emails (suppress stock Odoo notifications above).
        if not already_cancelled:
            try:
                client_template = request.env.ref(
                    "bf_appointment.mail_template_appointment_cancellation"
                ).sudo()
                booking_sudo._send_appointment_email(
                    client_template, attach_ics=False
                )
            except Exception as e:
                _logger.error(
                    "Failed to send cancellation email for booking %d: %s",
                    booking_sudo.id, e,
                )
            try:
                organizer_partner = booking_sudo.user_id.partner_id
                booker_emails = booking_sudo.partner_ids.mapped("email")
                if (
                    organizer_partner
                    and organizer_partner.email
                    and organizer_partner.email not in booker_emails
                ):
                    org_template = request.env.ref(
                        "bf_appointment.mail_template_organizer_cancellation"
                    ).sudo()
                    booking_sudo._send_appointment_email(
                        org_template, attach_ics=False
                    )
            except Exception as e:
                _logger.error(
                    "Failed to notify organizer of cancellation for booking %d: %s",
                    booking_sudo.id, e,
                )
        response = request.render(
            "bf_appointment.appointment_cancelled", {}
        )
        return _apply_security_headers(response)

    # ---- Helpers ----

    def _get_type_by_slug(self, slug):
        """Get a public booking type by its slug."""
        BookingType = request.env["resource.booking.type"].sudo()
        return BookingType.search(
            [("slug", "=", slug), ("is_public", "=", True)],
            limit=1,
        )

    def _get_booking_sudo(self, booking_id, access_token):
        """Validate access token and return sudoed booking."""
        if not access_token:
            return False
        # Rate limit: block IPs with too many failed token attempts
        if not _check_token_rate_limit():
            _logger.warning(
                "Token rate limit exceeded for IP %s",
                _client_ip(),
            )
            return False
        booking_sudo = (
            request.env["resource.booking"]
            .sudo()
            .with_context(active_test=False)
            .browse(booking_id)
        )
        if (
            not booking_sudo.exists()
            or not booking_sudo.access_token
            or not hmac.compare_digest(booking_sudo.access_token, access_token)
        ):
            _record_token_failure()
            return False
        return booking_sudo.with_context(
            using_portal=True,
            active_test=False,
            tz=booking_sudo.type_id.resource_calendar_id.tz,
        )

    @staticmethod
    def _validate_intake_value(field, value):
        """Validate an intake field value against its declared type."""
        if not value:
            return value
        if field.field_type == "email":
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
                return ""
        elif field.field_type == "phone":
            # Allow digits, spaces, dashes, parens, plus sign
            if not re.match(r"^[\d\s\-()+.]{7,20}$", value):
                return ""
        elif field.field_type == "number":
            try:
                float(value)
            except ValueError:
                return ""
        elif field.field_type == "select":
            # Validate against allowed options
            if field.select_options:
                allowed = {
                    opt.strip()
                    for opt in field.select_options.split("\n")
                    if opt.strip()
                }
                if value not in allowed:
                    return ""
        return value

    def _save_intake_answers(self, booking, booking_type, kwargs):
        """Save custom intake field answers from the form."""
        IntakeAnswer = request.env["appointment.intake.answer"].sudo()
        for field in booking_type.intake_field_ids:
            key = f"intake_{field.id}"
            value = (kwargs.get(key) or "").strip()
            value = self._validate_intake_value(field, value)
            if value:
                IntakeAnswer.create({
                    "booking_id": booking.id,
                    "field_id": field.id,
                    "value": value,
                })
