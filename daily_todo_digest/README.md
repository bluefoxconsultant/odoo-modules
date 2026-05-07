# Daily To-Do Digest

Odoo 18 module for sending an automatic daily email digest containing the user's activities and tasks, the local weather, and an inspirational quote.

## Features

### Digest content

| Section | Description |
|---------|-------------|
| **Weather** | Current temperature with emoji, min/max, precipitation for the configured city (default: Montreal) |
| **Overdue activities** | `mail.activity` with a past due date |
| **Today's activities** | `mail.activity` due today |
| **Overdue tasks** | `project.task` with a past due date |
| **Today's tasks** | `project.task` due today |
| **7-day preview** | Clickable visual grid of the next 7 days with color-coded counters (green/yellow/red) |
| **Hidden tasks** | Summary of tasks with `display_in_project=False` (clickable link) |
| **Inspirational quote** | Random quote from a pool of 120 quotes by artists, poets, and thinkers |

### Technical features

- **Timezone**: automatic UTC → America/Montreal conversion for date comparisons
- **Visibility filter**: excludes tasks with `display_in_project=False` from the detailed listing
- **Styled template**: HTML template with custom colors and fonts
- **Clickable links**: each task/activity contains a direct link to the Odoo record
- **Configurable cron**: hourly check, dispatch at the configured time
- **Email preheader**: quick preview in mail clients (e.g. "3 overdue | 5 today | ☀️ -8°C")
- **Weather emojis**: visual icons for conditions (☀️🌧️❄️⛈️ etc.)

## Installation

1. Copy the module into your `addons` directory
2. Update the module list in Odoo
3. Install "Daily To-Do Digest"

```bash
# Update and install
docker exec <container> odoo -d <database> -i daily_todo_digest --stop-after-init
```

## Configuration

### Access

**Settings → Technical → Daily Digest → Configuration**

### Available parameters

| Field | Description | Default |
|-------|-------------|---------|
| Name | Digest name | "My daily digest" |
| Send hour | Send hour (0–23, America/Montreal timezone) | 4 |
| Recipients | Users who receive the digest | - |
| Company | Optional company filter (not used currently) | Current company |

### Toggleable widgets

| Widget | Description |
|--------|-------------|
| Overdue activities | Include past activities |
| Today's activities | Include today's activities |
| Overdue tasks | Include past tasks |
| Today's tasks | Include today's tasks |
| Weather | Include local weather |
| Inspirational quote | Include a random quote |

### Weather configuration

| Field | Description | Default |
|-------|-------------|---------|
| Weather city | City display name | Montréal |
| Latitude | Latitude coordinate | 45.5017 |
| Longitude | Longitude coordinate | -73.5673 |

**Common coordinates:**
- Montréal: 45.5017, -73.5673
- Québec: 46.8139, -71.2080
- Toronto: 43.6532, -79.3832
- Ottawa: 45.4215, -75.6972

## Quotes

The module ships with **120 quotes** from artists, revolutionaries, poets, and dreamers, organized by themes:

- **Mutualism and anarchism**: Proudhon, Kropotkin, Emma Goldman, Bakunin
- **Poets and writers**: Rimbaud, Hugo, Neruda, García Lorca, Camus, Beauvoir, Galeano
- **Artists**: Frida Kahlo, Picasso, Oscar Wilde, Van Gogh
- **Civil rights**: Martin Luther King Jr., Nelson Mandela, Gandhi, Audre Lorde
- **Feminists**: Maya Angelou, bell hooks, Virginia Woolf
- **Thinkers**: Einstein, Seneca, Socrates, Aristotle
- **Contemporary activists**: Greta Thunberg, Paulo Freire, Aaron Swartz
- **Decolonial thinkers**: Frantz Fanon, Aimé Césaire
- **World proverbs**: African, Chinese, Japanese, Indigenous, Persian

### Managing quotes

**Settings → Technical → Daily Digest → Quotes**

Quotes can be added, edited, or deactivated through the UI.

## Module structure

```
daily_todo_digest/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── daily_digest.py          # Main model and dispatch logic
│   └── inspirational_quote.py   # Quote model
├── data/
│   ├── daily_digest_cron.xml    # Scheduled job (cron)
│   └── inspirational_quotes.xml # 120 pre-loaded quotes
├── security/
│   └── ir.model.access.csv      # Access rights
└── views/
    └── daily_digest_views.xml   # Views and menus
```

## Models

### `daily.digest.config`

Daily digest configuration.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Digest name |
| `active` | Boolean | Active/Inactive |
| `user_ids` | Many2many | Recipients |
| `send_hour` | Integer | Send hour (0–23) |
| `include_overdue_activities` | Boolean | Include overdue activities |
| `include_today_activities` | Boolean | Include today's activities |
| `include_overdue_tasks` | Boolean | Include overdue tasks |
| `include_today_tasks` | Boolean | Include today's tasks |
| `include_weather` | Boolean | Include weather |
| `weather_city` | Char | City name |
| `weather_latitude` | Float | Latitude |
| `weather_longitude` | Float | Longitude |
| `include_quote` | Boolean | Include quote |
| `company_id` | Many2one | Company (optional) |
| `last_sent` | Datetime | Last send timestamp |

### `daily.digest.quote`

Inspirational quotes.

| Field | Type | Description |
|-------|------|-------------|
| `quote` | Text | Quote text |
| `author` | Char | Author |
| `active` | Boolean | Active/Inactive |

## Weather API

The module uses the **Open-Meteo** API (free, no API key required).

- **URL**: `https://api.open-meteo.com/v1/forecast`
- **Data fetched**: current temperature, min/max, precipitation, precipitation probability, weather code
- **Timezone**: America/Montreal

## Email format

### Subject
```
🌄 Your day | Thursday, February 5, 2026
```

### HTML structure
- Header with logo and title
- Cyan accent bar (#29ABE2)
- Content sections with styled tables
- Footer with contact details
- Two-tone accent bars at the bottom

### Theme colors

| Element | Color |
|---------|-------|
| Outer background | #2E3132 |
| Header | #22303B |
| Accent | #29ABE2 |
| Light text | #E6EDF3 |
| Gray text | #6B7280 |
| Red (overdue) | #dc3545 |
| Green (success) | #198754 |

### Font
`'Lexend', 'Segoe UI', Arial, sans-serif`

## Manual send

### Through the UI
- **Send now**: sends the digest to all configured recipients
- **Test (me only)**: sends a test only to the connected user

### Through the Odoo shell
```python
config = env['daily.digest.config'].search([('name', '=', 'My digest')], limit=1)
config._send_digest()
env.cr.commit()
```

## Dependencies

- `base`
- `mail`
- `project`

### Python libraries
- `pytz` (bundled with Odoo)
- `requests` (bundled with Odoo)

## License

LGPL-3

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
