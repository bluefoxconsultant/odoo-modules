# BF Calendar CalDAV Snooze Bridge

Bidirectional RFC 9074 bridge between Odoo `calendar.attendee` snooze/dismiss
state (set by `bf_email_management`'s OWL popup) and the corresponding
`VALARM` blocks of Nextcloud `.ics` files (mapped via `calendar_nextcloud_sync`).

## Why

Without this bridge, the BF v1 popup writes `bf_snoozed_until` /
`bf_dismissed_at` on `calendar.attendee` but only Odoo knows about it.
Dismissing the same alarm in the Nextcloud web calendar — or in any
RFC 9074-compliant CalDAV client — has no effect on the Odoo state, so
the same reminder pops three times across three apps.

This module mirrors that state in both directions:

- **Odoo → CalDAV**: clicking *Snooze* or *Ignorer* in the Odoo popup
  immediately PUTs the patched `.ics` to Nextcloud. Snooze adds a
  `SNOOZE-VALARM` sibling with `RELATED-TO;RELTYPE=SNOOZE` and a
  fresh `TRIGGER;VALUE=DATE-TIME`. Dismiss adds `ACKNOWLEDGED:<UTC>`
  to the original VALARM.
- **CalDAV → Odoo**: the existing `calendar_nextcloud_sync` pull cron
  (every 15 min) now extracts `ACKNOWLEDGED` and `SNOOZE-VALARM`
  values from the parsed VEVENT and writes them to the matching
  attendee's `bf_dismissed_at` / `bf_snoozed_until` fields.

## Scope

- Only `calendar.event` (not `appointment.booking`).
- Only the calendar **owner**'s attendee row (i.e. the attendee whose
  `partner_id == config.calendar_owner_id.partner_id`). RFC 9074 state
  lives per-VALARM in a single `.ics`, so per-attendee semantics only
  map cleanly when each attendee has their own NC calendar instance.
  Other attendees on shared events stay in the v1 local-only flow.
- Only `ACTION:DISPLAY` VALARMs (the kind Odoo emits as
  `alarm_type='notification'`).

## Architecture

| Direction | Trigger | File:line |
|-----------|---------|-----------|
| Odoo → NC | `bf_snooze` / `bf_dismiss` RPC | `models/calendar_attendee.py` |
| NC → Odoo | `_parse_ics_vevent` override during pull | `models/nextcloud_sync_config.py` |
| Reconcile | 15-min cron (catches transient PUT failures) | `data/cron.xml` |

### Push side

`CalendarAttendee.bf_snooze()` / `bf_dismiss()` `super()` into the v1
implementation (writes the local field), then call
`_bf_push_valarm_to_caldav(attendee, ...)` which:

1. Checks scope guards (event has `x_caldav_href`, attendee is the
   calendar owner, config has CalDAV creds). Skips silently otherwise.
2. GETs the current `.ics` from Nextcloud with `Basic` auth (creds
   decrypted via `calendar_nextcloud_sync` Fernet helper).
3. Patches the VALARM block(s) using `_bf_patch_ics_valarm()`:
   - **Dismiss** → injects/replaces `ACKNOWLEDGED:<UTC>` inside the
     original DISPLAY VALARM. Generates a `UID:` for the VALARM if
     missing (RFC 9074 requires it for SNOOZE references).
   - **Snooze** → appends a sibling `BEGIN:VALARM…END:VALARM` block
     with `RELATED-TO;RELTYPE=SNOOZE:<original-uid>`,
     `ACTION:DISPLAY`, and `TRIGGER;VALUE=DATE-TIME:<UTC>`.
4. PUTs the patched `.ics` back with `If-Match: <x_caldav_etag>`.
   On `412 Precondition Failed` (etag stale), GETs once more and
   retries. Updates `x_caldav_etag` from the response on success.
5. Stamps `bf_caldav_pushed_at` on the attendee for the reconcile
   cron's tracking.

CalDAV failures **never** break the local snooze: any `requests`
exception is caught, logged at WARNING, and `bf_snoozed_until` /
`bf_dismissed_at` stay set in Odoo. The reconcile cron will retry.

### Pull side

`NextcloudCalendarSyncConfig._parse_ics_vevent()` `super()`s into the
existing parser (which still skips VALARM properties to avoid
overwriting VEVENT fields), then calls
`_bf_extract_valarm_state(ics_text)` in a separate pass that:

- Walks all VALARM blocks inside the first VEVENT.
- For `ACTION:DISPLAY` blocks **without** `RELATED-TO;RELTYPE=SNOOZE`
  (i.e. originals, not snooze siblings): keeps the latest
  `ACKNOWLEDGED` value.
- For DISPLAY blocks **with** `RELATED-TO;RELTYPE=SNOOZE`: keeps the
  latest `TRIGGER;VALUE=DATE-TIME` value.

Returns `{"acknowledged": <naive UTC datetime>, "snooze_trigger":
<naive UTC datetime>}` injected into the `ev_data` dict as the
`bf_valarm_state` key.

`CalendarEvent.create_from_nextcloud()` `super()`s the standard upsert,
then `_bf_apply_caldav_valarm_state(config_id, valarm_state)` finds
the calendar owner's attendee row and writes:

- `ACKNOWLEDGED` → `bf_dismissed_at = <ts>` AND
  `bf_caldav_acknowledged = <ts>`. Also bumps
  `partner.calendar_last_notif_ack = now()` so the v1 re-fire cron
  doesn't immediately re-push the bus.bus alarm.
- SNOOZE-VALARM TRIGGER → `bf_snoozed_until = <ts>` (only if the
  trigger is in the future; past triggers are local cron territory).

**Anti-loop guard**: the bridge writes only when the parsed
`ACKNOWLEDGED` differs from the previously-stored
`bf_caldav_acknowledged`. Without this, every 15-min pull cycle
would re-write `bf_dismissed_at` and `calendar_last_notif_ack` =
thrash with the v1 1-min re-fire cron.

### Reconcile cron (defensive)

`_bf_caldav_reconcile_pending` runs every 15 minutes. Searches for
attendees with active local snooze/dismiss state on an event that
has `x_caldav_href` set, where `bf_caldav_pushed_at < write_date`
(i.e. the local state is newer than the last successful push). For
each, retries `_bf_push_valarm_to_caldav`. Idempotent — patching a
VALARM twice produces the same `.ics`.

## Fields added

On `calendar.attendee`:

| Field | Type | Purpose |
|-------|------|---------|
| `bf_caldav_acknowledged` | Datetime | Last `ACKNOWLEDGED` value seen in the .ics. Anti-loop fingerprint. |
| `bf_caldav_pushed_at` | Datetime | Last successful PUT timestamp. Used by reconcile cron. |

(`bf_snoozed_until`, `bf_dismissed_at`, and `bf_ntfy_pushed_at` are
defined by the upstream `bf_email_management` v1 implementation.)

## Dependencies

- `bf_email_management` (v1 popup, snooze fields, RPC methods)
- `calendar_nextcloud_sync` (CalDAV credentials, ETag tracking,
  ICS parser hook, `x_caldav_href` field)

## Out of scope (would belong in v2.x)

- Snooze state for shared events (other attendees' calendars).
- VALARM types other than `DISPLAY` (audio, email, procedure).
- Migration of pre-deploy snoozes to CalDAV — only new snoozes sync.
- `appointment.booking` support.
- Conflict resolution beyond LWW (last-write-wins by datetime).

## Verification

E2E test on a real BF Olivier-personal NC calendar event:

```bash
# 1. Get the .ics URL from Odoo
psql -c "SELECT x_caldav_href FROM calendar_event WHERE id=<id>"

# 2. Snooze in Odoo popup, then verify SNOOZE-VALARM appears
curl -s --user olivier:<app-pw> \
  https://nextcloud.bluefoxconsultant.com/<href> \
  | grep -A4 'RELTYPE=SNOOZE'

# 3. Dismiss in NC web, force pull, verify bf_dismissed_at written
psql -c "SELECT bf_dismissed_at, bf_caldav_acknowledged
         FROM calendar_attendee WHERE event_id=<id>"
```

## License

LGPL-3.
