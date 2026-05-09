"""Pull side of the CalDAV snooze bridge.

Extends the existing CalDAV ICS parser to extract VALARM state (per RFC 9074:
``ACKNOWLEDGED`` and ``SNOOZE-VALARM``) and propagate it to the matching
``calendar.attendee`` rows after the upsert.

The base parser (``_parse_ics_vevent`` in ``calendar_nextcloud_sync``) skips
all VALARM blocks because their inner properties (DESCRIPTION, SUMMARY) would
otherwise overwrite the VEVENT's. We re-walk the unfolded text in a separate
helper that *only* looks at VALARMs, leaving the base parse untouched.
"""

import logging
import re
from datetime import datetime, timezone

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class NextcloudCalendarSyncConfig(models.Model):
    _inherit = "nextcloud.calendar.sync.config"

    def _parse_ics_vevent(self, ics_text):
        ev_data = super()._parse_ics_vevent(ics_text)
        if ev_data is None:
            return None
        ev_data["bf_valarm_state"] = self._bf_extract_valarm_state(ics_text)
        return ev_data

    @staticmethod
    def _bf_parse_ics_utc(value):
        """Parse a UTC DATE-TIME (e.g. ``20260508T172700Z``) into naive UTC."""
        if not value:
            return None
        value = value.strip()
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def _bf_extract_valarm_state(self, ics_text):
        """Walk VALARM blocks of the first VEVENT and extract bridge state.

        Returns a dict::

            {
                "acknowledged": <naive UTC datetime> or None,
                "snooze_trigger": <naive UTC datetime> or None,
            }

        ``acknowledged`` is the latest ``ACKNOWLEDGED`` value among all
        DISPLAY VALARMs whose own UID is *not* the target of a SNOOZE
        relationship (i.e. the original alarms, not the snooze siblings).

        ``snooze_trigger`` is the latest ``TRIGGER;VALUE=DATE-TIME`` of any
        VALARM that carries ``RELATED-TO;RELTYPE=SNOOZE`` — i.e. an active
        snooze.
        """
        unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
        lines = [ln.rstrip("\r") for ln in unfolded.split("\n")]

        in_vevent = False
        in_valarm = False
        valarm_buffer = []
        all_valarms = []

        for line in lines:
            stripped = line.strip()
            if stripped == "BEGIN:VEVENT":
                in_vevent = True
                continue
            if stripped == "END:VEVENT":
                break
            if not in_vevent:
                continue
            if stripped == "BEGIN:VALARM":
                in_valarm = True
                valarm_buffer = []
                continue
            if stripped == "END:VALARM":
                in_valarm = False
                all_valarms.append(valarm_buffer)
                valarm_buffer = []
                continue
            if in_valarm:
                valarm_buffer.append(stripped)

        latest_ack = None
        latest_snooze = None
        for block in all_valarms:
            action = None
            ack_value = None
            trigger_value = None
            is_snooze = False
            for prop in block:
                m_action = re.match(r"^ACTION\s*:\s*(\S+)", prop, re.I)
                if m_action:
                    action = m_action.group(1).upper()
                    continue
                m_ack = re.match(r"^ACKNOWLEDGED\s*:\s*(.+)", prop, re.I)
                if m_ack:
                    ack_value = m_ack.group(1).strip()
                    continue
                m_rel = re.match(
                    r"^RELATED-TO\b.*RELTYPE\s*=\s*SNOOZE", prop, re.I,
                )
                if m_rel:
                    is_snooze = True
                    continue
                m_trig_dt = re.match(
                    r"^TRIGGER\b[^:]*VALUE\s*=\s*DATE-TIME[^:]*:\s*(.+)",
                    prop, re.I,
                )
                if m_trig_dt:
                    trigger_value = m_trig_dt.group(1).strip()
                    continue
            if action != "DISPLAY":
                continue
            if is_snooze and trigger_value:
                snoozed_dt = self._bf_parse_ics_utc(trigger_value)
                if snoozed_dt and (
                    latest_snooze is None or snoozed_dt > latest_snooze
                ):
                    latest_snooze = snoozed_dt
            elif ack_value:
                ack_dt = self._bf_parse_ics_utc(ack_value)
                if ack_dt and (latest_ack is None or ack_dt > latest_ack):
                    latest_ack = ack_dt

        return {
            "acknowledged": latest_ack,
            "snooze_trigger": latest_snooze,
        }


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def create_from_nextcloud(self, data, config_id):
        result = super().create_from_nextcloud(data, config_id)
        valarm_state = data.get("bf_valarm_state") or {}
        if not (valarm_state.get("acknowledged") or
                valarm_state.get("snooze_trigger")):
            return result
        event_id = result.get("id")
        if not event_id:
            return result
        try:
            self.browse(event_id)._bf_apply_caldav_valarm_state(
                config_id, valarm_state,
            )
        except Exception as exc:  # noqa: BLE001 — never break sync on bridge bug
            _logger.warning(
                "bf_calendar_caldav_snooze: state apply failed for event=%s: %s",
                event_id, exc,
            )
        return result

    def _bf_apply_caldav_valarm_state(self, config_id, valarm_state):
        """Mirror VALARM state to the calendar owner's attendee row.

        Anti-loop: only write when the parsed ACKNOWLEDGED differs from
        ``bf_caldav_acknowledged`` (the last value we wrote on this attendee).
        Without this guard, the 15-min pull cron would re-write
        ``bf_dismissed_at`` on every poll, which would also reset the
        v1 partner-level ``calendar_last_notif_ack`` and could cause the
        re-fire cron to thrash.
        """
        self.ensure_one()
        config = self.env["nextcloud.calendar.sync.config"].browse(config_id)
        if not config.exists() or not config.calendar_owner_id:
            return
        owner_partner = config.calendar_owner_id.partner_id
        attendee = self.attendee_ids.filtered(
            lambda a: a.partner_id == owner_partner
        )[:1]
        if not attendee:
            return

        ack = valarm_state.get("acknowledged")
        snooze = valarm_state.get("snooze_trigger")

        vals = {}
        if ack and attendee.bf_caldav_acknowledged != ack:
            vals["bf_caldav_acknowledged"] = ack
            vals["bf_dismissed_at"] = ack
            # Clear any stale snooze — a fresh dismiss supersedes it.
            if not snooze and attendee.bf_snoozed_until:
                vals["bf_snoozed_until"] = False
        if snooze and snooze > fields.Datetime.now():
            # Only mirror future snoozes — past triggers mean the snooze has
            # already fired and the v1 cron will manage re-fire from local
            # state.
            if attendee.bf_snoozed_until != snooze:
                vals["bf_snoozed_until"] = snooze

        if vals:
            attendee.write(vals)
            # Mirror the v1 dismiss invariant: ack the partner so the
            # standard alarm_manager stops firing this trigger.
            if vals.get("bf_dismissed_at"):
                attendee.partner_id.write({
                    "calendar_last_notif_ack": fields.Datetime.now(),
                })
