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
- **Rule engine (2.0+)** — `bf.email.rule` lets you encode "if sender matches X / subject contains Y / List-Unsubscribe present" → set category/priority/partner/handled. Rules fire on create after the auto-compute, with a Replay action for backfill.
- **Direction badges** — inbound (`←`) vs outbound (`→`), inferred from author membership and IMAP folder.
- **Four-state workflow (2.0+)** — `status` = New → Read → Replied (orthogonal to handled). `is_handled` = the Inbox-Zero "out of inbox" boolean. Archiving sets `is_handled=True` only — the read/replied status is preserved. The legacy `archived` value in `status` is kept as a tombstone for historical rows.
  - **new** — nobody has seen it yet.
  - **read** — the user (or chatter) opened it. Auto-flips on bf.email form open AND when the underlying mail.message is read in any chatter (via `mail.notification` override).
  - **replied** — an outbound message with matching `In-Reply-To` was sent.
  - **handled** — `is_handled=True`. Removed from the Inbox view, but `status` (and history) preserved.
- **Heuristic signals (2.0+)** — 8 stored booleans/floats per row, evidence-based. See §Research.
- **Response time** — automatically computed delta between an inbound row and the first outbound reply matching its Message-ID.

### RFC 2822 Thread Tracking
- **`thread_root_id`** — root Message-ID of the conversation, resolved from the `References` header (or `In-Reply-To` / parent chain). Indexed for fast grouping.
- **Conversation smart button** — opens the full thread filtered by `thread_root_id` directly from any row.
- **Group-by-thread** in the search view.

### Smart Actions
- **Reply / Forward — always available (2.0+)**. Single dispatcher with 4 branches:
  | direction | res_model | composer target               |
  |-----------|-----------|-------------------------------|
  | in        | yes       | source record (chatter)       |
  | in        | no        | own res.partner (orphan IMAP) |
  | out       | yes       | source record (chatter)       |
  | out       | no        | own res.partner (orphan IMAP) |
  Forward attaches original RFC 2822 attachments for orphan rows.
- **Snooze (2.0+)** — defer rows out of inbox until a chosen datetime. The IMAP mirror cron flips them back automatically.
- **Bilateral IMAP archive (2.0+, opt-in)** — flip ICP `bf_email.imap_writeback_archive=True` and Archive in the UI also `UID COPY` + `EXPUNGE` from Migadu INBOX.
- **Auto mark-as-read** — opening an email in the form automatically transitions the row. Reading the underlying `mail.message` in any chatter also flips status (via `mail.notification` override).
- **Auto mark-as-replied** — when an outbound row is created with `in_reply_to` matching an inbound row's Message-ID, the inbound is flipped to `replied` automatically (no manual click).
- **Bulk actions** — Mark read, Mark replied, Traiter, Remettre en boîte, Reporter, Re-router — all available as server actions on the list view.

### Interactive Dashboard (OWL)
- Date range filters: 7d / 30d / 90d / year / all / custom — **all charts including daily volume now respect the selection** (preset "Tout" derives the range from the actual data).
- Inbox-Zero actionable cards: Boîte de réception active, En attente > 24h, IMAP orphelins à router, VIP en attente.
- "Tout traité ?" handled-rate badge — handled / total ratio for the selected period.
- KPI cards: received, sent, unread, average response time.
- Category breakdown, top contacts, daily volume chart.

## Research grounding

The 8 heuristic signals are based on empirical email-overload research:

- **Dabbish & Kraut (2006)** — *Email Overload at Work: An Analysis of Factors Associated with Email Strain.* CSCW '06. Source for `is_question` (questions ~4× more likely to be replied to), `is_to_me` (direct-To ~3× higher response than CC), `is_action_request` (modal-verb cues correlate with perceived priority).
- **Whittaker & Sidner (1996)** — *Email Overload: Exploring Personal Information Management of Email.* CHI '96. Source for `is_short` (short emails answered fast = batch-able).
- **Whittaker (2011)** — *Personal Information Management.* Source for `is_likely_thread` (active threads benefit from batched handling).
- **Kooti et al. (2015)** — *Evolution of Conversations in the Age of Email Overload.* WWW '15. Source for `is_late_night` (off-hours skew low-urgency), `external_age_hours` (median reply <47 min, tail >24h is the real backlog), `expected_reply_minutes` (per-correspondent baseline beats global thresholds).
- **Grbovic et al. (2014)** — *How Many Folders Do You Really Need?* CIKM '14. Source for `is_bulk` (List-Unsubscribe is the strongest bulk signal in the Yahoo email taxonomy).

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

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
