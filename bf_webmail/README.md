# Courriel Blue Fox (bf_webmail)

Odoo 18 module that embeds SnappyMail webmail access directly in the Odoo backend via a systray icon.

## Features

- Systray icon for one-click webmail access
- Configurable SnappyMail URL and IMAP settings
- Encrypted credential storage
- Seamless integration with Odoo backend

## Configuration

Go to **Settings > Technical > Parameters > System Parameters** and set:

| Parameter | Description |
|-----------|-------------|
| `bf_webmail.webmail_url` | URL of your SnappyMail instance |
| `bf_webmail.imap_host` | IMAP server hostname |
| `bf_webmail.imap_port` | IMAP port (default: 993) |

## Installation

```bash
docker exec <container> odoo -d <db> -i bf_webmail --stop-after-init --no-http
```

## License

MIT

---

*Developed with AI assistance (Claude, Anthropic).*
