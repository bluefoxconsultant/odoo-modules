# BF Time of Day

Admin-configurable time slots (Morning / Noon / End of day / Off hours, …) for Odoo tasks and activities. Each slot has a name, an icon, a color, and a suggested time. Selecting a slot on a task rewrites the deadline's time to point to the slot. Each user can override the suggested time with their own (flex time).

## License

LGPL-3 — see `LICENSE`.

## Features

### Admin-configurable time slots
- Model `bf.time.of.day` (`name`, `code`, `sequence`, `color`, `icon`, `default_time`, `active`).
- 4 seeded presets (`noupdate=1`): **Morning** (09:00, ☕), **Noon** (12:00, 🌞), **End of day** (16:00, 🕓), **Off hours** (19:00, 🌙). Renamable, recolorable, extendable — admins can add as many as they want.
- Admin menu under *Settings → Technical → Time slots*. Inline-editable list with `widget="color_picker"` and `widget="float_time"` to the minute.

### Application on `project.task`
- `time_of_day_id` field (Many2one, indexed, `group_expand` to show empty kanban columns).
- On create / write: if `date_deadline` is defined AND a slot is chosen, the **time** of the deadline is rewritten to the effective time (the **date** is preserved). Explicit UTC ↔ user-timezone conversion.
- `default_get` proposes the slot closest to the current local time (wrap-around handled for *Off hours*) — saves a click on the common case.
- `time_of_day_color` (related, store=True) and `time_of_day_icon` (related) fields for kanban decoration.

### Application on `mail.activity`
- Same `time_of_day_id` field, **purely informational**: `mail.activity.date_deadline` is a `Date` (no time), so nothing is mutated on the data side — the slot is for filtering and display only.
- If the activity is scheduled from a `project.task` that carries a slot, the slot is **inherited** by default (Quick win D).

### Per-user override (flex time)
- Model `bf.time.of.day.user_pref` (`user_id`, `time_of_day_id`, `override_time`) with a `(user_id, time_of_day_id)` SQL unique constraint.
- *Time slots* tab on the user form (`res.users`) — each user manages their own rows.
- Helper `res.users._tod_effective_time(time_of_day)`: returns `override_time` if defined, otherwise admin `default_time`, otherwise `False` (no mutation).
- Admin presets are **suggestions**; the personal override wins.

### Kanban visibility ("like task state")
- Inheritance of `project.view_task_kanban`: colored badge `o_tag_color_<n>` after the tags, prefixed with the slot's Font Awesome icon.
- Inheritance of `project.view_task_search_form`: 5 filters (`Morning`, `Noon`, `End of day`, `Off hours`, `No slot`) + group-by *Time slot*.
- Saved search `My day by slot` (Quick win C): user's tasks whose deadline falls today, grouped by slot — one click to see your day.
- The model display name is prefixed with an emoji (☕ Morning, 🌞 Noon, …) — the m2o dropdown is readable with no custom widget.

### Security
| Model | Read | Write / create / unlink |
| --- | --- | --- |
| `bf.time.of.day` (presets) | all internal users (`base.group_user`) | admins only (`base.group_system`) |
| `bf.time.of.day.user_pref` | own user via `ir.rule` (`user_id == user.id`) | own user via the same rule |
| `bf.time.of.day.user_pref` | admins see everything via a 2nd rule | admins can modify everything |

No `ir.rule` on `project.task` / `mail.activity` — the stock ACL stays in place. No `sudo()` escalation outside the override lookup (read-only on the user's own preferences).

## Architecture

```
bf.time.of.day (preset, admin)
   ├── used by ──> project.task.time_of_day_id   (mutates date_deadline.time, user TZ)
   ├── used by ──> mail.activity.time_of_day_id  (display + filter, no mutation)
   └── overridden per-user ──> bf.time.of.day.user_pref (user_id, time_of_day_id, override_time)

res.users
   ├── one2many bf_time_of_day_pref_ids
   └── _tod_effective_time(tod) → override_time | default_time | False
```

## Dependencies

- `project` — extension of `project.task` (kanban, form, list, search).
- `mail` — extension of `mail.activity` (form popup, tree).

## Configuration

- **Seeded presets**: Morning 09:00, Noon 12:00, End of day 16:00, Off hours 19:00 (`noupdate=1` — admin changes survive upgrades).
- **Colors**: standard Odoo palette (1-11). Seeds use 10 / 3 / 4 / 9.
- **Icons**: Font Awesome 4 class (`fa-coffee`, `fa-sun-o`, etc.). Emoji mapping wired for `fa-coffee`, `fa-sun-o`, `fa-clock-o`, `fa-moon-o`, `fa-cutlery`, `fa-bed`, `fa-bolt`, `fa-leaf`, `fa-fire`, `fa-star`. If the icon is not mapped, the display name omits the emoji and just keeps the name.

## Deadline behavior

| Case | Effect on `date_deadline` |
| --- | --- |
| `time_of_day_id` not set | unchanged |
| `time_of_day_id` set, `date_deadline` not set | unchanged |
| `time_of_day_id` set, `date_deadline` set, `default_time` blank and no override | unchanged |
| `time_of_day_id` set, `date_deadline` set, `default_time` or override set | deadline **time** rewritten, **date** preserved, user timezone respected |

## File Structure

```
bf_time_of_day/
├── __init__.py
├── __manifest__.py
├── README.md
├── LICENSE
├── data/
│   ├── bf_time_of_day_data.xml         # 4 seeded presets (noupdate=1)
│   └── bf_time_of_day_filters.xml      # ir.filters "My day by slot"
├── models/
│   ├── __init__.py
│   ├── bf_time_of_day.py               # preset model + emoji display_name
│   ├── bf_time_of_day_user_pref.py     # per-user override
│   ├── res_users.py                    # one2many + helper _tod_effective_time
│   ├── project_task.py                 # field + smart default + deadline mutation
│   └── mail_activity.py                # field + slot inheritance from parent task
├── security/
│   ├── ir.model.access.csv
│   └── bf_time_of_day_security.xml     # ir.rule on user_pref
├── static/src/scss/
│   └── kanban_badge.scss               # kanban chip styling
└── views/
    ├── bf_time_of_day_views.xml        # list + form + action
    ├── res_users_views.xml             # "Time slots" tab on the user form
    ├── project_task_views.xml          # form + kanban + tree + search inheritance
    ├── mail_activity_views.xml         # form popup + tree inheritance
    └── menu.xml                        # Settings → Technical → Time slots (admin)
```

## Changelog

### 18.0.1.0.0 (2026-05-07)
- Initial release: preset model (admin) + per-user override + extension of `project.task` (deadline mutation with timezone handling, smart default, group_expand) + extension of `mail.activity` (inherit slot from parent task, display only) + kanban / form / tree / search inheritance with colored badge and Font Awesome icon + saved search "My day by slot".

## Credits

Blue Fox Inc — https://bluefoxconsultant.com

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
