# Blue Fox Appointment

Odoo 18 Community module that extends `resource_booking` with self-service public booking pages, automated email reminders, and client-side timezone detection.

## Use case

Let a prospect or client book a meeting (demo, consultation, follow-up) without creating an Odoo account, with email-based confirmation, reminders, and cancellation — all integrated into the booked resource's calendar.

## Features

- **Public booking page** — one URL per booking type, accessible without authentication
- **Client-side timezone detection** — JavaScript detects the browser TZ and converts displayed slots
- **Intake questions** — custom fields per booking type, collected when the appointment is made
- **Email templates** — confirmation, reminder (D-1), follow-up email, cancellation
- **Configurable reminder sequence** — schedule multiple sends before the meeting (`appointment.email.schedule` model)
- **Dispatch cron** — sends scheduled emails according to the configured delay
- **Cancellation portal** — signed link in the emails so the client can cancel themselves

## Technical architecture

### Models

| Model | Role |
|---|---|
| `resource.booking.type` (inherited) | Adds: public URL, email templates, timezone |
| `resource.booking` (inherited) | Link to intake answers, notification state |
| `calendar.event` (inherited) | Propagates data from the booking |
| `appointment.intake` | Intake questions per booking type |
| `appointment.email.schedule` | Schedule for automated reminders |
| `res.config.settings` (inherited) | Global configuration (branding, URLs) |

### Dependencies

| Module | Role |
|---|---|
| `resource_booking` | Base booking model |
| `portal` | Unauthenticated access to public pages |
| `mail` | Email templates and dispatch |

### Security

- `ir.rule` blocking direct access to `appointment.intake.answer` for public users (only via the signed controller)
- Standard ACLs for internal users

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_appointment --stop-after-init
```

Then configure a `resource.booking.type` with its public URL and the associated email templates.

## License

AGPL-3

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
