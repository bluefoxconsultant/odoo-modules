# Blue Fox Webmail

Odoo 18 Community module that adds a one-click access to a SnappyMail instance (or any other webmail) from the Odoo systray, without leaving the interface.

## Use case

Teams using Odoo as their primary work environment often have to switch between Odoo and their webmail to handle email. This module provides one-click access to webmail in a modal window, preserving the Odoo context.

## Features

- **Email icon in the systray** — permanent button at the top right of Odoo
- **Opens in a modal** — webmail displays in an embedded window, not a new tab
- **Configurable URL** — system parameter pointing to any webmail (SnappyMail, Roundcube, etc.)
- **Zero persistence** — no data model, configuration only via `res.config.settings`

## Technical architecture

### Structure

```
bf_webmail/
├── __init__.py
├── __manifest__.py
├── controllers/
│   └── main.py
├── data/
│   └── ir_config_parameter.xml
├── models/
│   └── res_config_settings.py
└── static/src/
    ├── js/bf_webmail_systray.js
    ├── js/bf_webmail_dialog.js
    ├── scss/bf_webmail.scss
    └── xml/bf_webmail.xml
```

### Dependencies

| Module | Role |
|---|---|
| `base` | Sole dependency — Odoo framework |

### Configuration

The webmail URL is stored in `ir.config_parameter` under the key `bf_webmail.url`. Editable via **Settings → General Settings → Blue Fox Webmail**.

### Security

No persistent model, so no specific ACLs. Configuration is restricted to `base.group_system` (administrators) via the standard `res.config.settings` pattern.

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_webmail --stop-after-init
```

Then set the webmail URL in the general settings.

## License

LGPL-3

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
