# Email Management for Odoo 18

A centralized email management module for Odoo 18 that provides a single, deduplicated inbox combining **direct IMAP ingestion** with **chatter projection** from `mail.message`. Includes UI re-routing of orphan IMAP emails into any Odoo record's chatter, RFC 2822 thread tracking, and an interactive OWL dashboard.

## Features

### Unified Inbox (1.5+)
- **Two ingestion sources, one row per Message-ID**:
  - **IMAP direct** — polls `INBOX` and `Sent` every 5 minutes via IMAP4_SSL, stores raw RFC 2822 for later re-use.
  - **Chatter / mail gateway** — projects `mail.message` rows that originated from Odoo chatter or were routed by the mail gateway.
- **Deduplication by Message-ID** — `UNIQUE(message_id_header, company_id)` constraint plus active promotion: when a chatter `mail.message` arrives for an IMAP-orphan row, the row is upgraded in place (`source` switches from `imap` to `gateway`/`chatter`, `res_model`/`res_id` populated). Internal Odoo always wins.
- **Re-routing wizard** — single button on every IMAP-orphan row opens a wizard that posts the email to any model with `mail.thread` (project task, helpdesk ticket, contact, lead, calendar event, invoice, sale order, etc.). Preserves the original Message-ID and date so the RFC 2822 thread stays intact. Bulk action available from the list view.
- **Archives backfill wizard** — one-shot scan of any IMAP folder (e.g. `Archives/2025`) with optional date filters. Idempotent — re-running it never creates duplicates.

### Email Enrichment
- **Auto-categorization** — Client / Internal / Vendor / Notification / Marketing, computed from `res.partner` rank fields and sender pattern matching. Defensive against tenants without `sale_team`/`purchase` modules.
- **Direction badges** — inbound (`←`) vs outbound (`→`), inferred from author membership and IMAP folder.
- **Status workflow** — New → Read (auto on form open) → Replied (auto when an outbound row references the row's Message-ID via `In-Reply-To`) → Archived.
- **Response time** — automatically computed delta between an inbound row and the first outbound reply matching its Message-ID.

### RFC 2822 Thread Tracking
- **`thread_root_id`** — root Message-ID of the conversation, resolved from the `References` header (or `In-Reply-To` / parent chain). Indexed for fast grouping.
- **Conversation smart button** — opens the full thread filtered by `thread_root_id` directly from any row.
- **Group-by-thread** in the search view.

### Smart Actions
- **Reply integration** — opens Odoo's mail composer pre-filled with recipient, subject, and quoted original body (requires `mail_quoted_reply` addon).
- **Auto mark-as-read** — opening an email in the form automatically transitions the row.
- **Auto mark-as-replied** — when an outbound row is created with `in_reply_to` matching an inbound row's Message-ID, the inbound is flipped to `replied` automatically (no manual click).
- **Bulk actions** — Mark read, Mark replied, Archive, Re-route to chatter — all available as server actions on the list view.

### Interactive Dashboard (OWL)
- Date range filters: 7d / 30d / 90d / year / all / custom.
- KPI cards: received, sent, unread, average response time.
- Category breakdown, top contacts, daily volume chart.

### Scheduled Drafts
- Cross-record list of every `mail.scheduled.message` the user can send.
- `scheduled_date` column with ascending default sort.
- Inline send-now and open-source actions.
- Editable form for subject, body, recipients, attachments.
- Inherits Odoo core's per-record post-access ACL.

### Views
- **List** — inbox-style; rows without a linked Odoo record are highlighted in warning color with an inline "Import to chatter" button.
- **Form** — full email detail with rendered HTML body (parsed from raw RFC 2822 for IMAP-orphan rows), technical headers, smart buttons (Reply, Open chatter, Open record, Conversation thread).
- **Kanban** — grouped by status for visual workflow.
- **Search** — filters: To-reply / Stale > 7 days / Last 24-48h / Today / Week / Month / IMAP-only / With record / Without record / Archived. Group-by: direction, category, source, status, partner, model, thread, date.
- **Graph & Pivot** — volume analysis and cross-tabulation.

## Requirements

- Odoo 18 Community or Enterprise.
- `mail` module (included in Odoo) — provides `mail.message`, `mail.thread`, `mail.scheduled.message`.
- Python 3.10+ (uses standard library `imaplib`, `email.policy.default`, no extra pip deps).
- Optional: `mail_quoted_reply` for quoted-reply composer body.

## Installation

1. Copy the `bf_email_management` directory to your Odoo addons path.
2. Install via the Apps menu.
3. **Configure IMAP credentials** (Settings → Technical → Parameters):
   - `bf_email.imap_host` — your IMAP server hostname
   - `bf_email.imap_port` — typically `993` (IMAPS)
   - `bf_email.imap_user` — IMAP username (usually the email address)
   - `bf_email.imap_password` — IMAP password or app password
4. The cron `Courriels : ingestion IMAP directe` runs every 5 minutes and silently skips when credentials are unset, so the module is safe to install before configuring IMAP.
5. To backfill historical emails from an archive folder, open *Courriels → Configuration → Rattrapage IMAP (Archives)*.

## Architecture Notes

### Watermarking
- **Chatter projection cron** advances a `create_date` watermark on `mail.message` (not the sender's `Date:` header) so back-dated imports — manual scripts, forwarded threads — never fall below the watermark.
- **IMAP cron** advances a per-folder UID watermark (`bf_email.imap_last_uid_inbox`, `imap_last_uid_sent`). Migadu UIDs are monotonic per folder.
- **Backfill wizard** does NOT touch the live UID watermarks, so re-running it on an archive folder is safe.

### Deduplication Order of Operations
- IMAP cron creates an `imap` row IF no `mail.message` with the same Message-ID exists. Otherwise it creates a `gateway`/`chatter` row directly linked to the existing `mail.message` (annotated with the IMAP UID for traceability).
- Chatter cron promotes any pre-existing `imap` orphan to `gateway`/`chatter` instead of creating a duplicate (UNIQUE constraint would reject otherwise).
- Migration `18.0.1.5.1` retroactively promoted historical orphans whose Message-IDs already existed in `mail.message`.

### Re-routing
- The wizard reads the stored RFC 2822 (kept in `raw_rfc822` Binary attachment), parses it, and posts to the target via `record.message_post(...)` preserving Message-ID, original date, author, and attachments.
- After posting, the `bf.email` row is promoted (linked to the new `mail.message`, `source` becomes `gateway`).

## Security

- **Two security groups**: User (read/write) and Manager (full CRUD + sync wizards).
- **Multi-company**: Users see only their company's rows; managers see all.
- **Menu badge** for unread count.
- IMAP credentials are stored in `ir.config_parameter` (system-only access). Passwords are not exposed in views or logs.
- Re-routing wizard validates `check_access_rights("write")` and `check_access_rule("write")` on the target record before posting.
- All SQL uses parameterized placeholders.
- `sudo()` calls are scoped to system-config reads, cross-model display-name lookups, and partner resolution by email.

## License

MIT License

Copyright (c) 2026 Blue Fox Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Support

For support, please contact Blue Fox Inc. or open an issue in the repository.

---

Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.
