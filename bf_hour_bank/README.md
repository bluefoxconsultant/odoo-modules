# Hour Bank (`bf_hour_bank`)

Odoo 18 module for automated tracking of client hour banks.

## Features

- **Per-client configuration**: included projects, company / partner / product filters, report recipients
- **Automatic balance calculation**: debits (timesheets) + credits (invoices) + manual adjustments
- **Manual adjustments**: credits or debits outside invoices/timesheets (re-billing, corrections, journal entries)
- **PDF report**: branded report with banner, entry table (credits in green), per-project summary, monthly summary
- **Excel report**: 4 tabs (Timesheets, Per-project summary, Monthly summary, To bill)
- **Email send**: wizard with PDF + Excel attachments, branded email
- **Preview**: PDF preview directly from the send wizard
- **Automatic dispatch**: configurable cron (weekly, biweekly, monthly) sending the branded report to recipients
- **Client portal**: `/my/hour-banks` page available to portal users with self-service PDF/Excel downloads

## Dependencies

- `project`, `account`, `hr_timesheet`, `mail`, `portal`
- `openpyxl` (Python, for Excel generation)
- `bf_lexend` (Lexend font in PDFs)

## Calculation logic

```
Debits      = timesheets on configured projects (account.analytic.line)
Credits     = posted customer invoice lines (account.move.line)
              filtered by company + partner + product (optional)
Adjustments = manual entries (positive = credit, negative = debit)

Balance = Σ credits + Σ adjustments − Σ debits
```

Entries are listed in descending date order (most recent first) in the PDF, Excel, and portal.

### Invoicing filters

Three independent filter levels are available in the Invoicing tab:

#### Company filter

| Mode | Behavior |
|------|----------|
| **All companies** (default) | No company filtering |
| **Include only** | Only invoices from selected companies count |
| **Exclude** | All invoices except those from selected companies |

#### Billing partner filter

Optional field to target specific partners instead of the automatic `commercial_partner_id`. Useful when the same commercial customer has several billing contacts (e.g. internal company change). If empty, default behavior (all invoices for the commercial partner) is preserved.

#### Product filter

| Mode | Behavior |
|------|----------|
| **All lines** (default) | All customer invoice lines are included |
| **Include only** | Only lines with the listed products count |
| **Exclude** | All lines except those with the listed products |

### Report columns

| Column | Description |
|--------|-------------|
| Date | Operation date |
| Hours | Hours (negative = debit, positive = credit) |
| Cumulative balance | Running balance at this date |
| Description | Timesheet line name or invoice number |
| Project | Project name or "Billed hours" / "Adjustment" |
| Task | Task name (timesheets only) |

## Structure

```
bf_hour_bank/
├── models/
│   ├── hour_bank_client.py        # Configuration + report generation
│   └── hour_bank_adjustment.py    # Manual adjustments
├── wizard/
│   └── hour_bank_send_wizard.py   # Email send (branded)
├── controllers/
│   └── portal.py                  # Client portal (/my/hour-banks)
├── report/
│   ├── hour_bank_paperformat.xml  # US Letter paper format
│   └── hour_bank_report_templates.xml  # QWeb PDF template
├── views/
│   ├── hour_bank_client_views.xml # Form, list, search
│   ├── hour_bank_portal_templates.xml # Portal pages
│   └── menu_views.xml             # Menu under Project
├── data/
│   ├── hour_bank_mail_template.xml
│   └── hour_bank_cron.xml         # Automatic dispatch cron
├── security/
│   ├── hour_bank_security.xml     # Access rules (internal + portal)
│   └── ir.model.access.csv
└── i18n/
    └── fr_CA.po
```

## Access

### Backend (internal)
- **Project > Hour Bank > Clients**
- Read: `project.group_project_user`
- Full management: `project.group_project_manager`

### Client portal
- **My account > Hour Bank** (`/my/hour-banks`)
- Access: `base.group_portal` (restricted to the client's `commercial_partner_id`)
- Available routes:
  - `/my/hour-banks` — list of hour banks
  - `/my/hour-banks/<id>` — detail with table, balance, per-project summary
  - `/my/hour-banks/<id>/pdf` — PDF download
  - `/my/hour-banks/<id>/xlsx` — Excel download

## Automatic dispatch (cron)

The cron `Hour Bank: Automatic report dispatch` runs daily at 08:00 and sends reports according to the configured frequency:

| Frequency | Trigger |
|-----------|---------|
| Weekly | Every Monday |
| Biweekly | Mondays of even ISO weeks |
| Monthly | 1st of the month |

## Installation

```bash
docker exec <container> odoo -d <db> -i bf_hour_bank --stop-after-init --no-http
```

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
