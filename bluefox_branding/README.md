# Configurable Branding Pack

Per-company brand-color + email-layout overrides for Odoo Community.

This module is configurable. Colors come from `res.company.report_brand_primary`
and `res.company.report_brand_dark` (fields provided by `bf_lexend`), so each
tenant picks their own palette in **Settings > Companies > _your company_ >
Brand colors**. No SCSS recompile, no per-tenant build.

The fallback hex values match Odoo's stock theme (#714B67 plum, #212529 dark),
so installing this module is a visual no-op until brand colors are configured.

## What this module overrides

### Backend chrome

- Top navbar
- App menu / burger menu (mobile)
- Main-menu module (full-screen home menu)
- Buttons (`.btn-primary`), badges, progress bars, links, focus rings,
  selection color, kanban accents

All of the above re-skin via CSS variables (`var(--brand-primary, fallback)`,
`var(--brand-dark, fallback)`) populated at request time from the current
company's settings. See `static/src/scss/branding.scss`.

### Transactional email layouts

Two new layouts:

- `bluefox_branding.bf_mail_layout` — standalone branded layout (header
  with company logo, accent bar in brand primary, footer with company
  contact info)
- `bluefox_branding.bf_mail_layout_with_signature` — same plus the
  responsible-user signature block

These are not overrides of Odoo's `mail.mail_notification_layout`. They're
only used when the composer wizard explicitly references them via
`email_layout_xmlid` (invoices, quotes, contracts). Chatter notifications
and internal messages stay on Odoo's default.

### Standard mail templates

Templates from `om_account_followup`, `contract`, `helpdesk_mgmt`,
`survey`, and `calendar` ship as `noupdate=1` in their origin module
and cannot be patched declaratively. This module's `post_init_hook`
reads `data/mail_template_overrides.xml` and writes the branded
versions over them at install time, in every active language.

A separate hook also patches the late-invoice template (template 141
in stock Odoo, which has no XML ID).

### Legacy Odoo purple

`mail.mail._send`, `mail.mail.create`, `mail.mail.write` and
`mail.render.mixin._render_template` all run a small regex sweep that
replaces Odoo's legacy `#875A7B` plum (and its `rgb()` / `#714B67`
variants) with the configured brand primary in HTML email bodies.
This catches Odoo's own templates that still ship hardcoded purple.

## Dependencies

| Module | Why |
|--------|-----|
| `web`, `mail`, `account`, `sale`, `calendar`, `portal` | Odoo core |
| `om_account_followup`, `contract`, `helpdesk_mgmt`, `survey` | Templates this module rewrites |
| `bf_lexend` | Defines `res.company.report_brand_primary` / `report_brand_dark` + Lexend font |

## Configuration

1. Install the module.
2. Go to **Settings > Companies > _your company_** (or the multi-company
   settings page from `bf_lexend`).
3. Set **Brand color (primary)** and **Brand color (dark)** to your hex
   values.
4. Save. The backend re-skins on the next page load. Outgoing emails using
   the branded layouts pick up the new colors on their next render.

The module never reads or writes any colors outside the company brand
fields — there's nothing tenant-specific stored anywhere else.
