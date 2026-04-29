# Changelog

All notable changes to `bf_email_management` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This module follows Odoo's `MAJOR.MINOR.PATCH` convention prefixed with the Odoo series (`18.0.X.Y.Z`).

## [18.0.1.5.1] — 2026-04-28

### Fixed
- **Empty body on IMAP-orphan rows** — `body_html` was a related field on `mail.message.body`, which returned empty for IMAP-direct rows that have no linked `mail.message`. Converted to a stored compute that parses `raw_rfc822` for `source='imap'` rows and reads `mail.message.body` for chatter/gateway rows. Plain-text bodies are wrapped in `<pre>` for chatter-style rendering.
- **Internal Odoo wins on dedup** — the IMAP cron previously created orphan rows even when a `mail.message` with the same Message-ID already existed (because the chatter projection had run earlier and the IMAP UID was new). It now checks `mail.message` proactively and creates the row already linked to the chatter (annotated with IMAP UID for traceability) instead of as an orphan.
- **NUL byte stripping** — PostgreSQL `TEXT` columns reject `0x00` bytes; some clients embed them via inline images or quoted-printable artifacts. Bodies are now scrubbed before storage to prevent `A string literal cannot contain NUL` errors during compute persistence.

### Migration
- `migrations/18.0.1.5.1/post-migrate.py`:
  1. Retroactively promotes IMAP orphans whose Message-ID already exists in `mail.message` (link `mail_message_id`, copy `res_model`/`res_id`, switch `source` to `gateway`/`chatter`).
  2. Backfills `body_html` from `mail.message.body` for chatter/gateway rows (fast SQL path).
  3. Backfills `record_name` for newly-promoted rows.
  4. Recomputes `body_html` for remaining IMAP orphans by parsing `raw_rfc822`.

## [18.0.1.5.0] — 2026-04-28

### Added
- **Direct IMAP ingestion** — new cron `_cron_sync_imap` (5-minute interval) connects via IMAP4_SSL to a configured mailbox, polls `INBOX` and `Sent`, and creates `bf.email` rows with `source='imap'`. Per-folder UID watermarks (`bf_email.imap_last_uid_inbox`, `imap_last_uid_sent`).
- **Re-routing wizard** (`bf.email.reroute`) — single-record button on every IMAP-orphan row, plus list-view bulk server action. Posts the email to any `mail.thread` model (project task, helpdesk ticket, contact, lead, calendar event, invoice, sale order, etc.) via `record.message_post(...)`, preserving Message-ID, original date, author, and attachments.
- **Archives backfill wizard** (`bf.email.imap.backfill`) — one-shot scan of any IMAP folder (e.g. `Archives/2025`) with optional `SINCE`/`BEFORE` date filters. Idempotent — UNIQUE Message-ID constraint plus existence checks prevent duplicates on re-runs.
- **RFC 2822 thread tracking** — new `thread_root_id` field, indexed, computed from the `References` header (or `In-Reply-To` / `mail.message.parent_id` chain). Smart button "Conversation" on the form view filters `bf.email` by thread root.
- **Auto-replied** — when an outbound row is created with `in_reply_to` matching an inbound row's Message-ID, the inbound is flipped to `replied` automatically.
- **New fields on `bf.email`**: `imap_uid`, `imap_folder`, `raw_rfc822` (Binary attachment), `thread_root_id`, `thread_count` (compute).
- **`source` selection** extended with `imap`.
- **`in_reply_to`** is now indexed.
- **List view enhancements**: warning decoration on rows without a linked record, inline "Import to chatter" button, badges for `imap` source.
- **Search filters**: `À répondre`, `Sans réponse > 7 jours`, `Dernières 24h`, `Dernières 48h`, `Sans dossier (à router)`, `Avec dossier`, `IMAP orphelin`.
- **Group-by-thread** in search view.
- **`models/bf_email_imap.py`** — reusable RFC 2822 helpers (IMAP4_SSL connection, UID search, body extraction, attachment parsing, thread header parsing, NUL-byte scrubbing).

### Changed
- **Default action context** — `bf_email_action` (action 1785) no longer applies `search_default_filter_new=1`. Default view is now the unified inbox sorted by date desc, including read and replied (excludes archived only).
- **`_should_sync(msg)` extended** — no longer just dedup; now actively promotes existing IMAP-orphan rows when a chatter `mail.message` with the same Message-ID arrives, instead of skipping or creating a duplicate.

### Migration
- `migrations/18.0.1.5.0/post-migrate.py` — recursive CTE backfill of `thread_root_id` for existing rows by walking `mail.message.parent_id` chains. Seeds `thread_root_id` from `in_reply_to` or `message_id_header` for rows without a linked `mail.message`.

### Configuration (`ir.config_parameter`)
- `bf_email.imap_host`, `bf_email.imap_port` (default `993`), `bf_email.imap_user`, `bf_email.imap_password` — IMAP server credentials. Empty by default; cron skips silently when unset.
- `bf_email.imap_batch_size` (default `100`) — UIDs fetched per cron tick.
- `bf_email.imap_last_uid_inbox`, `bf_email.imap_last_uid_sent` — per-folder UID watermarks (managed automatically).

### Notes
- Container restart required after the upgrade — Odoo's registry signaling reloads model definitions but does NOT reload Python bytecode for already-running workers.
- Re-routing preserves the original Message-ID, so subsequent gateway projections of the same email won't duplicate the row (UNIQUE constraint enforces this).

## [18.0.1.4.1] — 2026-04-27

### Fixed
- **`_compute_category` AttributeError on tenants without `sale_team`/`purchase`** — `customer_rank`/`supplier_rank` are not always present on `res.partner`. Replaced direct attribute access with `getattr(partner, 'customer_rank', 0)`.
- **FK violation on deleted partners** — `mail.message.author_id` is a raw int FK that Odoo doesn't auto-null when a partner is deleted. Added `partner.exists()` check in `_prepare_email_vals` to prevent `bf_email_partner_id_fkey` errors.

### Migration
- `migrations/18.0.1.4.1/post-migrate.py` re-runs the 1.4.0 backfill so rows that failed under the earlier hardening get a second pass.

## [18.0.1.4.0] — 2026-04-27

### Fixed
- **Watermark uses `create_date`, not `mail.message.date`** — the previous filter `("date", ">", last_sync)` advanced past back-dated imports (manual scripts, forwarded threads with original `Date:` headers, cross-tenant imports), permanently hiding them. Caught when an inbound reply imported retroactively never appeared in the module. Now uses insertion time (`create_date`).

### Migration
- `migrations/18.0.1.4.0/post-migrate.py` — backfills missing rows by sweeping `mail.message` records that were skipped by the buggy watermark.

## [18.0.1.3.x and earlier]

Initial chatter projection (`mail.message` → `bf.email`), enrichment fields, OWL dashboard, scheduled-drafts cross-record list, security groups, multi-company isolation. See git history for details.
