# Lexend Typeface

Adds the Lexend typeface as a font option across the Odoo backend, frontend
and PDF reports, and exposes per-company brand color settings.

## What it adds

### Fields on `res.company`

- `font` — extends the standard Odoo selection with `Lexend`
- `report_brand_primary` (Char, default `#714B67`) — accent color used
  by PDF reports and (when `bluefox_branding` is also installed)
  backend chrome and emails
- `report_brand_dark` (Char, default `#212529`) — dark surface color
  for the same surfaces

Settings page shows both as `widget="color"` pickers, so admins can
preview the color while editing.

### Asset bundles

- `web.assets_backend` + `web.assets_frontend` — `lexend.css` adds the
  Lexend `@font-face` declaration and a body-level font-family override
  when `res.company.font = 'Lexend'`
- `web.report_assets_common` + `web.report_assets_pdf` — same for PDF reports

## Standalone use

This module is useful on its own if you want a tenant-configurable
brand color stored on `res.company` for use by your own templates. The
companion `bluefox_branding` module consumes these fields to re-skin
the backend UI and rewrite standard Odoo email templates.

## Dependencies

- `web` (Odoo core)
