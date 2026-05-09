"""Push side of the CalDAV snooze bridge.

When the BF v1 popup writes ``bf_snoozed_until`` or ``bf_dismissed_at`` on a
``calendar.attendee``, mirror that state into the corresponding Nextcloud .ics
using RFC 9074 (``ACKNOWLEDGED`` for dismiss, ``SNOOZE-VALARM`` for snooze).

Scope guard: we only write to the .ics if the attendee row belongs to the
``calendar_owner_id`` of the Nextcloud calendar this event lives on. RFC 9074
state is per-VALARM in a single .ics; per-attendee semantics only map cleanly
when each attendee has their own calendar instance.

CalDAV failures never break the local snooze: log + skip.
"""

import logging
import re
import uuid
from datetime import timedelta, timezone

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Attempts to PUT the patched .ics. One retry on 412 (etag stale) after refresh.
_HTTP_TIMEOUT = 10


class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    bf_caldav_acknowledged = fields.Datetime(
        string="CalDAV ACKNOWLEDGED",
        help="Last ACKNOWLEDGED value seen in the CalDAV .ics for this "
             "attendee's VALARM. Used as anti-loop fingerprint by the pull "
             "parser so identical re-reads don't re-write bf_dismissed_at.",
    )
    bf_caldav_pushed_at = fields.Datetime(
        string="CalDAV pushed at",
        help="Timestamp of the last successful PUT of this attendee's "
             "snooze/dismiss state to Nextcloud. Used by the reconcile cron "
             "to detect failed pushes that need a retry.",
    )

    # ------------------------------------------------------------------
    # Hook into v1 actions — mirror state to CalDAV after local write
    # ------------------------------------------------------------------

    @api.model
    def bf_snooze(self, event_id, minutes=None, until=None):
        result = super().bf_snooze(event_id, minutes=minutes, until=until)
        attendee = self._bf_attendee_for_user(event_id)
        snooze_dt = fields.Datetime.from_string(result["snoozed_until"])
        try:
            self._bf_push_valarm_to_caldav(attendee, snooze_until=snooze_dt)
        except Exception as exc:  # noqa: BLE001 — never break local snooze
            _logger.warning(
                "CalDAV snooze push failed for attendee=%s event=%s: %s",
                attendee.id, event_id, exc,
            )
        return result

    @api.model
    def bf_dismiss(self, event_id):
        result = super().bf_dismiss(event_id)
        attendee = self._bf_attendee_for_user(event_id)
        dismiss_dt = fields.Datetime.from_string(result["dismissed_at"])
        try:
            self._bf_push_valarm_to_caldav(attendee, dismissed_at=dismiss_dt)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "CalDAV dismiss push failed for attendee=%s event=%s: %s",
                attendee.id, event_id, exc,
            )
        return result

    # ------------------------------------------------------------------
    # CalDAV push — GET, patch VALARM, PUT with If-Match
    # ------------------------------------------------------------------

    def _bf_push_valarm_to_caldav(self, attendee, snooze_until=None, dismissed_at=None):
        """Patch the .ics on Nextcloud to reflect snooze/dismiss state.

        At least one of ``snooze_until`` / ``dismissed_at`` must be provided.
        Skipped silently when the event is local-only or this attendee is not
        the calendar owner.
        """
        if not (snooze_until or dismissed_at):
            return False
        event = attendee.event_id
        config = event.x_nc_calendar_id
        if not config or config.backend_type != "nextcloud":
            return False
        if not event.x_caldav_href:
            return False  # event hasn't been synced to NC yet
        if not config.calendar_owner_id or \
                attendee.partner_id != config.calendar_owner_id.partner_id:
            return False  # state has no per-VALARM mapping for this attendee
        if not config.nextcloud_user or not config.nextcloud_app_password:
            _logger.warning(
                "CalDAV push skipped: config %s missing credentials", config.id,
            )
            return False

        url = self._bf_resolve_caldav_url(event, config)
        auth = (config.nextcloud_user, config.nextcloud_app_password)

        return self.with_context(
            bf_caldav_attendee_ids=[attendee.id],
        )._bf_put_with_etag_retry(
            url, auth, event,
            snooze_until=snooze_until, dismissed_at=dismissed_at,
        )

    # ------------------------------------------------------------------
    # Cron — reconcile attendees whose push was never confirmed
    # ------------------------------------------------------------------

    @api.model
    def _bf_caldav_reconcile_pending(self):
        """Re-push snooze/dismiss state for attendees missing confirmation.

        Catches transient PUT failures (network blip, prolonged etag stale).
        Idempotent — patching a VALARM twice produces the same .ics.
        """
        now = fields.Datetime.now()
        recent_dismiss_floor = now - timedelta(hours=24)
        pending = self.search([
            "|",
                "&", ("bf_snoozed_until", "!=", False),
                     ("bf_snoozed_until", ">", now),
                "&", ("bf_dismissed_at", "!=", False),
                     ("bf_dismissed_at", ">=", recent_dismiss_floor),
            ("event_id.x_caldav_href", "!=", False),
            ("event_id.x_nc_calendar_id", "!=", False),
        ])
        for attendee in pending:
            # Skip if push already happened after the last state write.
            last_state = max(filter(None, [
                attendee.bf_snoozed_until,
                attendee.bf_dismissed_at,
            ]))
            if (attendee.bf_caldav_pushed_at and
                    attendee.bf_caldav_pushed_at >= last_state):
                continue
            try:
                self._bf_push_valarm_to_caldav(
                    attendee,
                    snooze_until=attendee.bf_snoozed_until or None,
                    dismissed_at=attendee.bf_dismissed_at or None,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "bf_caldav reconcile failed for attendee=%s: %s",
                    attendee.id, exc,
                )

    def _bf_resolve_caldav_url(self, event, config):
        """Return the absolute URL of the .ics on Nextcloud."""
        href = event.x_caldav_href
        if href.startswith("http"):
            return href
        base = config.nextcloud_base_url.rstrip("/")
        if not href.startswith("/"):
            href = "/" + href
        return base + href

    def _bf_put_with_etag_retry(self, url, auth, event,
                                snooze_until=None, dismissed_at=None):
        """GET .ics, patch VALARM, PUT with If-Match. One retry on 412."""
        for attempt in range(2):
            try:
                resp = requests.get(url, auth=auth, timeout=_HTTP_TIMEOUT)
            except requests.RequestException as exc:
                _logger.warning("CalDAV GET failed for %s: %s", url, exc)
                return False
            if resp.status_code != 200:
                _logger.warning(
                    "CalDAV GET %s returned %s", url, resp.status_code,
                )
                return False
            etag = resp.headers.get("ETag") or event.x_caldav_etag
            patched = self._bf_patch_ics_valarm(
                resp.text,
                snooze_until=snooze_until,
                dismissed_at=dismissed_at,
            )
            if patched is None:
                # No notification VALARM to patch — nothing to do.
                return False
            headers = {"Content-Type": "text/calendar; charset=utf-8"}
            if etag:
                headers["If-Match"] = etag
            try:
                put_resp = requests.put(
                    url, data=patched.encode("utf-8"),
                    headers=headers, auth=auth, timeout=_HTTP_TIMEOUT,
                )
            except requests.RequestException as exc:
                _logger.warning("CalDAV PUT failed for %s: %s", url, exc)
                return False
            if put_resp.status_code in (200, 201, 204):
                new_etag = put_resp.headers.get("ETag")
                if new_etag and new_etag != event.x_caldav_etag:
                    event.with_context(skip_n8n_sync=True).write({
                        "x_caldav_etag": new_etag,
                    })
                # Track success on every attendee row of this event whose
                # state we just pushed (caller scopes to one attendee).
                self.env["calendar.attendee"].browse(
                    self._context.get("bf_caldav_attendee_ids") or []
                ).write({"bf_caldav_pushed_at": fields.Datetime.now()})
                return True
            if put_resp.status_code == 412 and attempt == 0:
                _logger.info(
                    "CalDAV ETag stale on PUT %s, refreshing and retrying",
                    url,
                )
                continue
            _logger.warning(
                "CalDAV PUT %s returned %s: %s",
                url, put_resp.status_code, put_resp.text[:200],
            )
            return False
        return False

    # ------------------------------------------------------------------
    # ICS patching (RFC 5545 + RFC 9074)
    # ------------------------------------------------------------------

    @staticmethod
    def _bf_format_utc(dt):
        """Format a naive UTC Datetime as ICS DATE-TIME (YYYYMMDDTHHMMSSZ)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _bf_uid_domain(self):
        """Return the hostname slot used as the right-hand side of generated
        VALARM UIDs (RFC 5545 ``<unique>@<domain>`` convention).

        Derived from ``web.base.url`` so each tenant produces UIDs scoped to
        its own host (avoids cross-tenant clashes when the same calendar is
        shared across multiple Odoo instances). Falls back to a generic
        identifier if the parameter is missing.
        """
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "",
        )
        if base_url:
            from urllib.parse import urlparse
            host = urlparse(base_url).hostname
            if host:
                return host
        return "bf-caldav-snooze.local"

    def _bf_patch_ics_valarm(self, ics_text, snooze_until=None, dismissed_at=None):
        """Add ACKNOWLEDGED and/or SNOOZE-VALARM to the first DISPLAY VALARM.

        Returns the patched .ics text, or None if no DISPLAY VALARM is present
        (nothing to patch — the event has no notification reminder).
        """
        # Unfold so we can split on simple linebreaks. We re-fold via CRLF on
        # output (most CalDAV servers tolerate either; NC accepts both).
        unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
        # Use \r\n for output per RFC 5545 §3.1.
        eol = "\r\n"
        lines = unfolded.split("\n")
        lines = [ln.rstrip("\r") for ln in lines]

        out = []
        in_valarm = False
        valarm_buffer = []
        original_valarm_uid = None
        first_display_idx = -1  # index in `out` where we'll append SNOOZE-VALARM
        patched_any = False

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped == "BEGIN:VALARM":
                in_valarm = True
                valarm_buffer = [line]
                original_valarm_uid = None
                i += 1
                continue
            if stripped == "END:VALARM":
                in_valarm = False
                valarm_buffer.append(line)
                # Decide: is this a DISPLAY (notification) VALARM?
                actions = [
                    re.match(r"^ACTION\s*:\s*(\S+)", b.strip(), re.I)
                    for b in valarm_buffer
                ]
                action_value = next(
                    (m.group(1).upper() for m in actions if m), None,
                )
                # Skip non-DISPLAY (audio, email, procedure, snooze with
                # RELATED-TO already — we don't touch existing snooze siblings).
                is_display = action_value == "DISPLAY"
                has_related_snooze = any(
                    re.match(r"^RELATED-TO\b.*RELTYPE\s*=\s*SNOOZE",
                             b.strip(), re.I)
                    for b in valarm_buffer
                )
                if is_display and not has_related_snooze:
                    # Ensure the original VALARM has a UID (RFC 9074 needs it
                    # for SNOOZE references).
                    uid_match = next(
                        (m for m in (re.match(r"^UID\s*:\s*(.+)", b.strip())
                                     for b in valarm_buffer) if m),
                        None,
                    )
                    if uid_match:
                        original_valarm_uid = uid_match.group(1).strip()
                    else:
                        original_valarm_uid = (
                            uuid.uuid4().hex + "@" + self._bf_uid_domain()
                        )
                        # Insert UID right after BEGIN:VALARM
                        valarm_buffer.insert(1, f"UID:{original_valarm_uid}")

                    if dismissed_at is not None:
                        ack_line = (
                            "ACKNOWLEDGED:"
                            + self._bf_format_utc(dismissed_at)
                        )
                        # Replace existing ACKNOWLEDGED if any, else insert
                        # before END:VALARM.
                        replaced = False
                        for idx, b in enumerate(valarm_buffer):
                            if b.strip().upper().startswith("ACKNOWLEDGED"):
                                valarm_buffer[idx] = ack_line
                                replaced = True
                                break
                        if not replaced:
                            valarm_buffer.insert(-1, ack_line)
                    patched_any = True
                    if first_display_idx < 0:
                        # Mark insertion point for SNOOZE-VALARM (after this
                        # block, in the output).
                        first_display_idx = len(out) + len(valarm_buffer)
                out.extend(valarm_buffer)
                valarm_buffer = []
                i += 1
                continue
            if in_valarm:
                valarm_buffer.append(line)
                i += 1
                continue
            out.append(line)
            i += 1

        if not patched_any:
            return None

        # Append the SNOOZE-VALARM block right after the patched original
        # VALARM (so it sits inside the same VEVENT).
        if snooze_until is not None and first_display_idx >= 0:
            snooze_uid = uuid.uuid4().hex + "@" + self._bf_uid_domain()
            snooze_block = [
                "BEGIN:VALARM",
                f"UID:{snooze_uid}",
                f"RELATED-TO;RELTYPE=SNOOZE:{original_valarm_uid}",
                "ACTION:DISPLAY",
                f"TRIGGER;VALUE=DATE-TIME:{self._bf_format_utc(snooze_until)}",
                "DESCRIPTION:Snoozed",
                "END:VALARM",
            ]
            out[first_display_idx:first_display_idx] = snooze_block

        return eol.join(out)
