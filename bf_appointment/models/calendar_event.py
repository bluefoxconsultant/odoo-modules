import logging

from odoo import models

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

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
