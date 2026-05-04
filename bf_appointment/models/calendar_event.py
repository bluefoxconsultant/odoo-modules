import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    @api.model
    def _cron_cleanup_orphan_booking_events(self):
        """Unlink past calendar.event records orphaned from a resource.booking.

        OCA action_unschedule already unlinks the meeting on a normal cancel,
        but custom cleanup scripts (`--cleanup` flags), direct DB ops, or
        future regressions can leave the calendar.event behind. The orphan
        keeps blocking slots in resource_booking_combination._get_intervals
        because it still belongs to the resource user's calendar.

        We target events that:
          - have the BF appointment naming convention "RDV - <name>"
          - have NO active or archived resource.booking pointing back to them
          - have already started (so we never touch in-flight bookings)
        """
        cutoff = fields.Datetime.now()
        candidates = self.search([
            ("name", "=like", "RDV - %"),
            ("start", "<", cutoff),
            ("resource_booking_ids", "=", False),
        ])
        # Skip events still linked from an *active* booking — that should
        # never happen given the inverse one2many is empty above, but it's a
        # cheap belt-and-suspenders against active_test edge cases.
        # Archived/cancelled booking references are fine: meeting_id is
        # ondelete=set null, so the booking record stays intact when we
        # unlink its old meeting.
        if candidates:
            still_active = self.env["resource.booking"].sudo().search([
                ("meeting_id", "in", candidates.ids),
            ]).mapped("meeting_id")
            to_unlink = candidates - still_active
            if to_unlink:
                _logger.info(
                    "Unlinking %d orphan calendar.event(s) from cancelled bookings",
                    len(to_unlink),
                )
                to_unlink.with_context(
                    no_mail_to_attendees=True,
                    tracking_disable=True,
                    mail_notrack=True,
                ).unlink()

    def _track_subtype(self, init_values):
        """Suppress tracking notifications on events linked to a booking.

        Resource bookings drive their own branded confirmation/reminder
        emails. Stock Odoo otherwise fires a "Date mise à jour" notification
        on every reschedule, AND any orphan calendar.event left behind by
        cancel/rebook cycles (with the booker still in attendee_ids) keeps
        firing them forever. The suppression context set by
        ResourceBooking._sync_meeting only covers the sync path; this guard
        catches every write to a booking-linked event.
        """
        if self.resource_booking_ids:
            return False
        return super()._track_subtype(init_values)

    def _get_ics_file(self):
        """Override to include videocall_location in ICS LOCATION and DESCRIPTION."""
        result = super()._get_ics_file()
        # Patch each ICS to include videocall_location if present
        for event in self:
            if not event.videocall_location:
                continue
            ics_data = result.get(event.id)
            if not ics_data:
                continue
            try:
                import vobject

                cal = vobject.readOne(ics_data.decode("utf-8"))
                vevent = cal.vevent
                # Set LOCATION to the video URL
                if hasattr(vevent, "location"):
                    vevent.location.value = event.videocall_location
                else:
                    vevent.add("location").value = event.videocall_location
                # Add URL property
                if not hasattr(vevent, "url"):
                    vevent.add("url").value = event.videocall_location
                # Enrich DESCRIPTION with video link
                desc = ""
                if hasattr(vevent, "description"):
                    desc = vevent.description.value or ""
                if event.videocall_location not in desc:
                    video_line = (
                        f"\n\nVid\u00e9oconf\u00e9rence : {event.videocall_location}"
                    )
                    desc = desc.rstrip() + video_line
                    if hasattr(vevent, "description"):
                        vevent.description.value = desc
                    else:
                        vevent.add("description").value = desc
                result[event.id] = cal.serialize().encode("utf-8")
            except Exception as e:
                _logger.warning(
                    "Failed to patch ICS for event %d: %s", event.id, e
                )
        return result
