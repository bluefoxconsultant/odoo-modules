# Email Management for Odoo 18

A centralized email management module for Odoo 18 that aggregates all sent and received emails from `mail.message` into a single, enriched view with categorization, response time tracking, and an interactive OWL dashboard.

## Features

### Centralized Email View
- **Unified Inbox**: All emails (inbound and outbound) in one list with direction badges
- **Auto-Categorization**: Emails are automatically categorized as Client, Internal, Vendor, Notification, or Marketing based on partner data
- **Status Tracking**: New, Read, Replied, Archived statuses with automatic transitions
- **Response Time**: Automatic calculation of response time between received and replied emails

### Smart Actions
- **Reply Integration**: Reply button opens Odoo's mail composer pre-filled with recipient, subject, and quoted original body (requires `mail_quoted_reply` addon)
- **Auto Mark-as-Read**: Opening an email automatically marks it as read
- **Auto Mark-as-Replied**: Clicking Reply automatically updates the status
- **Mass Actions**: Mark as read, replied, or archived from the list view
- **Source Navigation**: Jump to the related chatter or source record directly

### Interactive Dashboard (OWL)
- **Date Range Filtering**: Preset periods (7d, 30d, 90d, year, all) or custom date range
- **KPI Cards**: Received, Sent, Unread count, Average response time
- **Category Breakdown**: Clickable category distribution table
- **Top Contacts**: Most active contacts with received/sent breakdown
- **Daily Volume Chart**: Visual bar chart of email volume over the selected period

### Synchronization
- **Incremental Cron**: Syncs new emails from `mail.message` every 5 minutes
- **Manual Trigger**: "Synchroniser maintenant" button on the list view header and under *Configuration* runs the sync on demand and reports how many records were imported
- **Dual Source Coverage**: Captures both mail-gateway emails (`message_type='email'`) and chatter comments that generated an email notification to external partners (`message_type='comment'` with an `email` notification) — so replies posted from an Odoo chatter form are no longer missed
- **Source Field**: Each record is tagged `Passerelle courriel` or `Chatter` with search filters and group-by
- **Initial Import Wizard**: Batch import of historical emails with date range selection, covers both sources
- **Deduplication**: RFC 2822 Message-ID based deduplication prevents duplicates; scoped across active and archived rows, savepoint-isolated per record so a single constraint error never aborts the batch

### Views
- **List**: Inbox-style with contact link, subject, category badges, status badges
- **Form**: Full email detail with HTML body, technical headers, action buttons
- **Kanban**: Grouped by status for visual workflow
- **Search**: Filters by direction, source (gateway vs chatter), status, date range, attachments; group by category, source, partner, model
- **Graph & Pivot**: Email volume analysis and cross-tabulation

## Requirements

- Odoo 18 Community or Enterprise
- `mail` module (included in Odoo)
- Optional: `mail_quoted_reply` for quoted reply body in composer

## Installation

Copy the `bf_email_management` directory to your Odoo addons path and install via the Apps menu.

## Security

- **Two security groups**: User (read/write) and Manager (full CRUD + initial sync)
- **Multi-company**: Users see only their company's emails; managers see all
- **Menu badge**: Unread email count displayed on the menu icon
- All SQL queries use parameterized placeholders (no injection risk)
- `sudo()` calls are limited to cron sync and system config access

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

## Support

For support, please contact Blue Fox Inc. or open an issue in the repository.

---

Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.
