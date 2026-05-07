# Meetings (bf_meeting)

Odoo 18 Community module covering the full meeting lifecycle: agenda, calendar event, structured meeting record, decisions, attendance, and bidirectional links to tasks and knowledge matrices.

## Use case

Lets a project team plan, run, and document its meetings from inside Odoo, with no external tool: agenda preparation from open tasks, email dispatch to participants, structured note-taking, branded PDF report generation, and tracking of decisions as knowledge-matrix lines.

## Features

- **Agendas (`meeting.agenda`)** — title, date, project, participants, planned topics, email dispatch to recipients
- **Meeting records (`meeting.record`)** — discussed topics, decisions, structured JSON notes rendered as safe HTML, PDF report, send tracking
- **Decisions (`meeting.decision`)** — decision-makers, context, optional transfer to knowledge matrices
- **Attendance (`meeting.attendance`)** — status (present / absent / excused) and role per participant
- **Tasks to discuss** — four ways to attach a `project.task` to an upcoming meeting:
  - *Pinned*: explicit link to a specific agenda
  - *Next client meeting*: shows up at the next eligible client agenda
  - *Next project meeting*: shows up at the next eligible project agenda
  - *All client/project meetings*: shows up at every eligible agenda as long as the task is open
- **Dynamic resolution** — tagged tasks are computed on every agenda open (form, PDF, email) and disappear as soon as they close
- **Cancelling an agenda** — hard-linked tasks without a soft tag receive a "To-do" activity due today for reassignment; tagged tasks automatically roll over to the next eligible agenda
- **Transfer to meeting record** — `action_create_meeting_record` transfers hard-linked tasks to `meeting.record.task_ids` and clears the soft tag
- **Smart buttons** — next meeting on the task, meeting records and agendas on the project and on the calendar event, tasks-to-discuss on the agenda
- **Emails** — templates for sending the agenda and the meeting record, with a dedicated section for tasks-to-discuss
- **PDF report** — branded agenda render with an "Action items to discuss" section
- **Agenda ↔ meeting record ↔ calendar event unification** — the same `calendar.event` can carry an agenda and a meeting record; creating a meeting record from an event that already has an agenda automatically links the two (`meeting.agenda.meeting_record_id`) and propagates the project
- **"Needs an agenda" flag** — on `calendar.event`, computed `bf_needs_agenda` (true if the meeting is upcoming, has no agenda, and is not opted out); banner alert on the form and a dedicated filter in the search view
- **Per-meeting opt-out** — `bf_skip_agenda` checkbox on `calendar.event` for short or recurring internal meetings
- **Pre-meeting reminder** — daily cron `_cron_remind_unsent_agenda` creating a "To-do" activity due today on the organizer (internal user only) if the meeting is within the next 7 days and the agenda has not yet been sent; idempotent via the activity `summary`

## Technical architecture

### Models

| Model | Role |
|---|---|
| `meeting.agenda` | Agenda (project, date, topics, tasks, recipients, state) |
| `meeting.agenda.topic` | Topic planned in an agenda (sequence, duration, presenter) |
| `meeting.record` | Structured meeting record (project, date, JSON notes, PDF report) |
| `meeting.topic` | Topic discussed in a meeting record (key points, verbatim) |
| `meeting.decision` | Decision made during a meeting (context, decision-maker) |
| `meeting.attendance` | Participant attendance (status, role) |
| `project.task` (inherited) | Meeting-attachment fields (`meeting_id`, `bf_meeting_agenda_id`, `bf_discuss_tag`, `bf_next_agenda_id`) |
| `project.project` (inherited) | "Meeting records" smart button |
| `calendar.event` (inherited) | "Meeting records" and "Agenda" smart buttons, fields `meeting_agenda_ids/id/count`, `bf_skip_agenda` (opt-out), `bf_needs_agenda` (computed), creation of an agenda or meeting record from the event |
| `project.knowledge.item` (inherited) | Many2many link to meeting records that reference the item |

### Dependencies

| Module | Role |
|---|---|
| `project` | Projects, tasks, meeting attachment |
| `mail` | Chatter, activities, email templates |
| `calendar` | Link to Odoo calendar events |
| `project_knowledge_matrix` | Knowledge matrices fed by decisions |

### Security

- Group `group_meeting_user` — read and modify meetings of projects the user has access to (via `project.message_partner_ids`)
- Group `group_meeting_manager` — full access to all meeting records, agendas, decisions and attendance
- `ir.rule` on `meeting.record`, `meeting.agenda`, `meeting.topic`, `meeting.decision`, `meeting.agenda.topic`, `meeting.attendance`
- Standard ACLs declared in `security/ir.model.access.csv`

### Scheduled task

| Cron | Model | Frequency | Role |
|---|---|---|---|
| `ir_cron_remind_unsent_agenda` | `meeting.agenda` | daily | Creates a "To-do" activity on the agenda for the organizer if the meeting is within 7 days and the agenda is not sent |

### Safe HTML rendering

Structured JSON notes (topic title, bullets, open questions) are rendered to HTML through `markupsafe.escape()` before concatenation, to prevent any injection when the content comes from an external source (AI transcription, user paste).

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_meeting --stop-after-init --no-http
```

After install, the "Manager" group is granted to `base.user_admin` by default; other users get the "User" group via the user profile settings.

## License

LGPL-3

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
