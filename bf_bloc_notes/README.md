# BF Bloc-notes

Rich quick notes for Odoo 18, with multi-record links, one-click activity conversion, keyboard shortcuts, and a systray icon.

## License

LGPL-3 — see `LICENSE`.

## Features

### Quick capture
- **Systray icon 📝**: left-click = new note, right-click = list filtered to your notes.
- **Keyboard shortcuts**: `Alt+N` opens the capture dialog, `Alt+Shift+N` opens the list.
- **Auto-link**: if you are on a partner / task / project / lead form, the dialog pre-fills the link.
- **Image drop-zone**: paste (`Ctrl+V`) or drag an image into the editor — the attachment is created automatically and the image inserted into the note body.
- **Ctrl+Enter** in the dialog saves the note.

### Multi-link (m2m)
A note can be attached to multiple records at once. Model `bf.note.link` (`note_id`, `res_model`, `res_id`); the `res_ref` field remains as the "primary link" for backward compatibility. "Notes (N)" smart button on partner / task / project / lead via the batch mixin.

### Conversion to activity
From a note's form view, quick header buttons:
- **Today** (D)
- **Tomorrow** (D+1)
- **+2 days** / **+1 week**
- **Customize…** (wizard with date, activity type, assignment, editable summary)

One activity is created per linked record (e.g. a note linked to 3 tasks → 3 activities). Default type: **To-do** (`mail.mail_activity_data_todo`). "Activities (N)" smart button on the note for finding all created activities.

### Hybrid visibility
- Private by default (`is_shared=False`): only the author sees it.
- Toggling "Shared" makes it readable by all internal users; only the author can still edit.

### Views
- **Kanban**: colored cards (color picker), built-in pin button, body snippet, tags, primary link, deadline.
- **List**: direct pin toggle, filters "My notes / Pinned / Shared / Linked / Overdue".
- **Calendar**: if you set a `deadline_date`, the note appears in your calendar (not conflated with an activity).
- **Form**: HTML editor, "Links" tab with a sequence handle for reordering.

### Security
| Risk | Mitigation |
| --- | --- |
| RPC injection on `quick_create_from_context` | Explicit key whitelist (`name`, `body`, `tag_ids`, `pinned`, `color`, `deadline_date`, `is_shared`, `res_model`, `res_id`, `link_ids`). `user_id` is forced to `env.user.id` regardless of payload. |
| Model enumeration via `Reference` | `_selection_target_model` filters by the `ir.config_parameter` `bf_bloc_notes.reference_models` (10 models by default). |
| AccessError on the target record | `bf.note.link._compute_res_name` runs `check_access_rights("read")` + `check_access_rule("read")` as the calling user — no `sudo()` — and falls back to `False` on AccessError. `action_open` / `action_open_record` validate access before returning the `act_window`. |
| Note visibility | Two separate `ir.rule` records: read (author OR `is_shared`), write/unlink (author only). |
| Smart-button N+1 | `bf.note.link.mixin` uses batched `read_group` — 1 query for 200 records. |

### Performance
- `bf_note_count` computed in a single `read_group` query — no N+1 on list views / kanban.
- `res_name` stored (compute store=True) on `bf.note.link`, not recomputed on each render.
- Tracking of activities/tasks born from a note via two dedicated m2m fields (`tracked_activity_ids`, `tracked_task_ids`) instead of an expensive join on `mail.activity`.

## Architecture

```
bf.note ──┬── link_ids ──> bf.note.link ──(res_model, res_id)──> {res.partner, project.task, …}
          ├── tag_ids ──> bf.note.tag
          └── activity_ids (m2m) ──> mail.activity (on the target record)

bf.note.link.mixin (AbstractModel)
   └─ inherited by: res.partner, project.task, project.project, crm.lead
        └─ adds: bf_note_count (batch), action_open_bf_notes
```

## Dependencies

- `web`, `mail` (always present)
- `project` (smart button + form heritage on `project.task`, `project.project`)
- `crm` (smart button + form heritage on `crm.lead`) — Odoo Community
- `contacts` (smart button + form heritage on `res.partner`)

## Configuration

- **Models available in `Reference`**: `ir.config_parameter` key `bf_bloc_notes.reference_models` (CSV). Default: `res.partner,project.project,project.task,crm.lead,helpdesk.ticket,calendar.event,account.move,sale.order,purchase.order,hr.employee`.
- **Seeded tags**: Idea, To-do, Reference, Draft (created once, `noupdate=1`).

## Tests

```bash
odoo -d <db> -u bf_bloc_notes --test-enable --test-tags /bf_bloc_notes --stop-after-init --http-port=0
```

9 tests cover: auto-title, multi-link, batch count, RPC whitelist, private/shared visibility (read + write), per-link activity creation, unlinked-note guard.

## Changelog

### 18.0.2.7.1 (2026-06-21)
- Fix: `_compute_res_ref` validates `res_model` against the reference field's model selection before building the value, avoiding a `ValueError` that could break `web_read` when a note points at a model that is no longer installed.

### 18.0.2.5.0 (2026-05-06)
- Security: `bf.note.link._compute_res_name` no longer uses `sudo()`; ACLs applied via `check_access_rights` / `check_access_rule` (prevents leaking `display_name` for unreadable records).
- Security: `action_open` (on link and primary note) validates access before returning the `act_window`.
- UX: Alt+N focuses the title, not the body.
- UX: new secondary "Create a task" button in the quick-create dialog — pre-fills `default_name` / `default_description` (+ project / parent / partner where the context allows) and opens a fresh `project.task` form without creating a note.
- Fix: `getCurrentContext()` (auto-link) now ignores `context.active_id`; auto-links only on a real form view, to avoid creating an activity on the wrong chatter.
- Tests: aligned with the current API (`tracked_activity_count`, fallback creation-on-self) + new ACL test for `res_name`.

### 18.0.2.0.0 (2026-05-02)
- Added: multi-links via `bf.note.link` (m2m to records).
- Added: conversion to activity (quick buttons + wizard).
- Added: hybrid visibility (`is_shared`).
- Added: `deadline_date` + calendar view.
- Added: image drop-zone in the quick-create editor.
- Added: pin/unpin directly from the kanban.
- Security: RPC `quick_create_from_context` whitelisted, `user_id` forced.
- Performance: `bf.note.link.mixin` with batched `read_group` (eliminates N+1 on smart buttons).
- Stack: removed `mail.activity.mixin` (overhead) and `tracking=True` (chatter noise).

### 18.0.1.0.0 (2026-05-02)
- Initial release: `bf.note` + `bf.note.tag`, systray, hotkeys Alt+N / Alt+Shift+N, smart buttons on 4 models.

## Credits

Blue Fox Inc — https://bluefoxconsultant.com

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
