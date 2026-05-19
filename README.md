# Blue Fox — Odoo 18 CE Modules

Custom Odoo 18 Community Edition modules developed by [Blue Fox Inc.](https://bluefoxconsultant.com)

## Bundles (recommended starting point)

Install one of these meta-modules to pull in a coherent set in a single click:

| Bundle | Includes | Use case |
|---|---|---|
| `bf_loi25_suite` | `audit_ti`, `privacy_consent`, `project_knowledge_matrix` | Quebec Loi 25 compliance stack |
| `bf_ops_pack` | Email management, meeting, persona, helpdesk, hour bank, chatter + mail glue | Consulting/MSP operations cockpit |
| `bf_productivity_pack` | Universal search, bloc-notes, bureau, timesheet timer, daily digest, Lexend, dark mode, branding | Daily-use productivity + UI polish |

## Modules

| Directory | Name | Version | License | Description |
|---|---|---|---|---|
| `audit_ti` | Audit TI - Loi 25 | 18.0.1.17.0 | LGPL-3 | IT security audit management for Quebec's Loi 25 compliance |
| `bf_appointment` | Blue Fox Appointment | 18.0.2.15.7 | LGPL-3 | Self-service public booking pages (extends `resource_booking`) |
| `bf_bloc_notes` | BF Bloc-notes | 18.0.2.1.0 | LGPL-3 | Rich quick notes with multi-record links, one-click activity conversion, keyboard shortcuts, and systray icon (Alt+N) |
| `bf_bureau` | BF Bureau — multi-pane views | 18.0.3.0.0 | LGPL-3 | User-configurable dashboards ("desks") with multi-pane Odoo actions, six layouts, keyboard shortcuts, time slots, and a sidebar |
| `bf_calendar_caldav_snooze` | BF Calendar CalDAV Snooze Bridge | 18.0.1.0.0 | LGPL-3 | RFC 9074 bridge mirroring `calendar.attendee` snooze/dismiss state to Nextcloud `.ics` VALARM (`ACKNOWLEDGED` + `SNOOZE-VALARM`) in both directions |
| `bf_chatter_chronological` | BF Chatter Chronological View | 18.0.4.0.0 | LGPL-3 | Sort the chatter feed by the email's original Date header instead of insertion id (Python `_order` + `_message_fetch` + JS `Thread.fetch*` patch); cogwheel action to re-parse lost Date headers from quoted body content |
| `bf_chatter_send_now_force` | BF Chatter — Force Send on Scheduled Send Now | 18.0.1.0.0 | LGPL-3 | The "Send Now" button on a scheduled chatter message sends immediately instead of waiting up to 5 min for the mail queue cron (restores parity with the daily auto-send cron) |
| `bf_dark_mode` | Blue Fox Dark Mode | 18.0.1.0.0 | LGPL-3 | Dark mode for Odoo using the Blue Fox palette |
| `bf_default_all_companies` | BF Default All Companies | 18.0.1.0.0 | LGPL-3 | Pre-selects every allowed company in the multi-company switcher on first login |
| `bf_document_nextcloud_sync` | Document Nextcloud Sync | 18.0.1.1.0 | LGPL-3 | Document sync between Odoo and Nextcloud via WebDAV |
| `bf_email_management` | Email Management | 18.0.5.1.1 | LGPL-3 | Unified IMAP inbox + Odoo chatter projection, two-pane OWL folder browser (Apple Mail / Thunderbird), bulk per-row target inference |
| `bf_gamification` | Fox Quest | 18.0.2.1.0 | LGPL-3 | Gamification system with XP, levels, badges, and rewards |
| `bf_helpdesk` | Blue Fox — Helpdesk | 18.0.4.0.0 | LGPL-3 | Branded helpdesk extension: per-team public form, hour-bank ribbon, waiting states, ntfy critical hook, persona panel, knowledge-matrix link, ticket→meeting, IA triage via Claude, CSAT on close, branded portal, dashboard tile, IMAP gateway hardening, SLA + macros + auto-tag + auto-ack |
| `bf_hour_bank` | Hour Bank | 18.0.1.11.0 | LGPL-3 | Automated tracking of client hour banks with threshold-based proactive notifications (unbilled hours, % of allocated budget, balance floor) |
| `bf_lexend` | Lexend Typeface | 18.0.2.0.0 | LGPL-3 | Adds Lexend across UI/PDF reports and per-company brand color settings (`report_brand_primary`, `report_brand_dark`) |
| `bf_mail_import` | BF Email Import (.eml) | 18.0.1.2.0 | LGPL-3 | Import .eml files into the Odoo chatter |
| `bf_mail_subject_clean` | BF Email Subject Cleanup | 18.0.1.0.0 | LGPL-3 | Prevents "Re: Re: Re:" stacking on subjects sent through the chatter |
| `bf_mail_vigie` | BF Email Re-router | 18.0.2.0.0 | LGPL-3 | "Re-route" button on `bf.email` to move a misrouted email to the correct chatter |
| `bf_meeting` | Meetings | 18.0.3.10.0 | LGPL-3 | Agendas, meeting records, and discussion items unified around `calendar.event` with automatic reminders |
| `bf_persona` | Persona des contacts | 18.0.2.0.0 | LGPL-3 | Active relationship intelligence: composer hint with auto-cc, monthly auto-seed from email signals, weekly degradation detector with optional ntfy alert, kanban dashboard |
| `bf_sms_archive` | SMS & Call Archive | 18.0.1.3.0 | LGPL-3 | Archive and search Android SMS and call logs |
| `bf_studio_light` | Blue Fox — Studio Light | 18.0.5.1.0 | LGPL-3 | Field builder for Odoo Community: add custom fields (incl. polymorphic reference with model whitelist), smart buttons (count via JSON controller, no compute Python), and inject them in views without writing a module — survives `-u all` upgrades |
| `bf_task_unblock_notify` | BF Task Unblock Notify | 18.0.1.6.1 | LGPL-3 | Notifies assignees when their task becomes unblocked |
| `bf_time_of_day` | BF Time of Day | 18.0.1.0.0 | LGPL-3 | Time-of-day slots (Morning / Noon / End of day / Off hours) for tasks and activities, with per-user overrides |
| `bf_timesheet_timer` | BF Timesheet Timer | 18.0.1.6.0 | LGPL-3 | Global timesheet timer with multi-timer support and an OWL UI |
| `bf_universal_search` | BF Universal Search | 18.0.1.3.0 | LGPL-3 | Cross-module search through the command palette |
| `bluefox_branding` | Configurable Branding Pack | 18.0.2.0.0 | LGPL-3 | Per-company brand color + email layout overrides driven by `bf_lexend` company fields (CSS variables injected via QWeb layout — no SCSS recompile) |
| `contacts_nextcloud_sync` | Contacts Nextcloud Sync | 18.0.1.0.0 | LGPL-3 | Sync Odoo contacts with a Nextcloud address book via CardDAV |
| `daily_todo_digest` | Daily To-Do Digest | 18.0.1.3.0 | LGPL-3 | Daily email digest with activities, overdue tasks, and a week-ahead view |
| `hosting_management` | Hosting Management | 18.0.2.46.0 | LGPL-3 | Manage hosting services, client computer parks (endpoints, BitLocker, Action1 sync) and software license pools |
| `privacy_consent` | Privacy & Consent Tracking (Loi 25) | 18.0.3.1.3 | LGPL-3 | Privacy, consents, and document destruction (Quebec Loi 25) |
| `project_knowledge_matrix` | Project Knowledge Matrix | 18.0.9.10.0 | LGPL-3 | Project knowledge base, policies, and documentation |

## Installation

Add this repository to your Odoo `addons_path`:

```conf
addons_path = /path/to/odoo/addons,/path/to/odoo-modules
```

Then install individual modules from the Odoo Apps menu.

## Compatibility

All modules target **Odoo 18.0 Community Edition**.

## License

All modules in this repository are released under the **GNU LGPL-3** license. See [`LICENSE`](LICENSE) for the full text.

## Credits

Authored and maintained by [Blue Fox Inc.](https://bluefoxconsultant.com)

---

<sub>AI coding assistants were used as productivity tools during development; architectural decisions, code review, and release responsibility rest with Blue Fox Inc.</sub>
