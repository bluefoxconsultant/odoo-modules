# BF Recherche universelle

A cross-module universal search for Odoo 18 that extends the native command palette (`Ctrl+K`). Type `*` followed by your query to search contacts, projects, tasks, hosting services, documents, tickets, calendar events, and more — all from a single input, on any screen.

## License

MIT License — see [License Text](#license-text) below. Free to use, modify, and redistribute.

## Features

### Command Palette Integration

The module plugs into Odoo 18's built-in command palette rather than reinventing the wheel. This gives you keyboard navigation (`Up`/`Down`/`Enter`), debounced async search, loading states, and the familiar centered modal — for free.

- **Keyboard**: press `Ctrl+K`, then type `*` followed by your search term
- **Mouse**: click the magnifying glass icon in the systray navbar

The palette footer automatically shows `*enregistrements` alongside the native `/menus`, `@users`, and `#channels` hints, so users can discover it organically.

### Cross-Module Results

A single query searches across all configured models simultaneously. Results are grouped by category with section headers:

| Category | Models searched | Fields |
|----------|----------------|--------|
| **Contacts** | `res.partner` | name, email, phone |
| **Projets** | `project.project` | name |
| **Projets** | `project.task` | name |
| **Hébergement** | `hosting.service` | name, code, domain_name |
| **Hébergement** | `hosting.server` | name, hostname |
| **Hébergement** | `hosting.domain` | name |
| **Hébergement** | `hosting.software` | name |
| **Documents** | `project.document` | name, code |
| **Documents** | `project.knowledge.item` | name |
| **Documents** | `project.credential` | name |
| **Autres** | `helpdesk.ticket` | name |
| **Autres** | `calendar.event` | name |

Each result shows the record name and, when available, a secondary detail (email, hostname, document code, etc.). Clicking a result navigates directly to the record's form view.

### Dynamic Module Detection

The module has **no hard dependencies** on hosting_management, project_knowledge_matrix, helpdesk, or any other module. On install, it detects which models are available and creates config entries only for installed ones. Models from uninstalled modules are silently skipped at search time.

### Admin-Configurable

Administrators can manage search configuration through `bf.universal.search.config` records:

- Enable or disable individual models via the **Active** toggle
- Change which fields are searched per model
- Adjust the result limit per model (default: 5)
- Reorder categories via the **Sequence** field
- Add entirely new models without writing code

### Access Control

All searches go through the ORM (`search_read`), which means:

- `ir.model.access` rules are checked before searching any model
- `ir.rule` record-level security is applied automatically
- A user without read access to `hosting.service` will never see hosting results

## Requirements

- Odoo 18.0 (Community or Enterprise)
- No additional Python packages required
- Dependencies: `web`, `base` (always available)

## Installation

1. Copy the `bf_universal_search` directory into your Odoo addons path.

2. Install the module:
   ```bash
   odoo -d YOUR_DATABASE -i bf_universal_search --stop-after-init
   ```

3. Restart Odoo and hard-refresh your browser (`Ctrl+Shift+R`) to load the new JS assets.

The `post_init_hook` will automatically create search config records for all installed models listed in the default configuration. Config records are registered in `ir_model_data` with `noupdate=True` to survive Odoo's module cleanup phase and to preserve any admin customizations across upgrades.

## Usage

### Via Keyboard (Recommended)

1. Press `Ctrl+K` to open the command palette
2. Type `*` — the placeholder changes to "Rechercher partout..."
3. Type your search term (minimum 2 characters)
4. Use `Up`/`Down` arrows to navigate results
5. Press `Enter` to open the selected record

### Via Mouse

1. Click the magnifying glass icon in the systray (top-right navbar)
2. The command palette opens pre-filled with the `*` namespace
3. Type your search term
4. Click any result to navigate to it

## Architecture

### Backend

**`bf.universal.search`** (`_auto = False`)

A virtual model (no database table) exposing a single RPC method:

```python
@api.model
def search_all(self, query, model_filters=None, limit=5):
    """
    Returns:
    [
        {
            "model": "res.partner",
            "model_label": "Contacts",
            "icon": "fa fa-users",
            "category": "search_contacts",
            "results": [
                {"id": 42, "name": "Acme Corp", "detail": "info@example.com"},
                ...
            ],
        },
        ...
    ]
    """
```

For each active config entry, the method:
1. Verifies the model exists in the current registry
2. Checks the user's read access via `ir.model.access`
3. Validates that the configured search fields exist on the model
4. Builds an OR domain across all valid fields with `ilike`
5. Calls `search_read` with the configured limit
6. Extracts a display name and a secondary detail from the results

**`bf.universal.search.config`**

Standard Odoo model storing the search configuration:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display label (e.g. "Contacts") |
| `model_id` | Many2one (`ir.model`) | Target Odoo model |
| `search_fields` | Char | Comma-separated field names (e.g. `name,email,phone`) |
| `icon` | Char | FontAwesome class (e.g. `fa fa-users`) |
| `category` | Char | Grouping key (e.g. `search_contacts`) |
| `sequence` | Integer | Display order |
| `limit` | Integer | Max results per model (default: 5) |
| `active` | Boolean | Toggle to include/exclude from search |

### Frontend

The JavaScript side uses three Odoo 18 registries:

**`command_setup`** — Registers the `*` namespace with a 300ms debounce, French placeholder text, and empty-state message.

**`command_categories`** — Defines five display categories (`search_contacts`, `search_projects`, `search_hosting`, `search_documents`, `search_other`) bound to the `*` namespace, each with a French label and display sequence.

**`command_provider`** — An async provider that calls `bf.universal.search.search_all` via RPC, transforms each result into a `CommandItem` with a `name`, `category`, and `action` that navigates to the record's form view.

**Systray component** — A minimal OWL 2 component rendering a magnifying glass button. On click, it calls `commandService.openMainPalette({ searchValue: "*" })` to open the palette pre-configured for universal search.

## Performance

| Aspect | Strategy |
|--------|----------|
| Debounce | 300ms client-side (via `command_setup`) |
| Min query length | 2 characters (enforced in the provider) |
| Limit per model | 5 results (configurable per config entry) |
| Queries per search | 1 `search_read` per active model (~12 max) |
| Observed latency | 28–56ms total server-side for 12 models |
| Concurrency | Odoo's `KeepLast` ensures only the most recent request is displayed |
| Index support | Compatible with `base_search_fuzzy` and `base_name_search_improved` for faster `ilike` |

## Customization

### Adding a New Model

No code changes required. Create a new `bf.universal.search.config` record:

1. Go to **Settings > Technical > Universal Search Config** (or create via shell/SQL)
2. Set the model, search fields, icon, and category
3. The model will appear in search results immediately

### Changing Categories

Edit the `category` field on config records to regroup models. If you add a category that doesn't exist in the JS registry, results will appear under a generic heading. To add a properly named category, add a line in `universal_search_provider.js`:

```javascript
catReg.add("search_my_category", { namespace: "*", name: _t("Ma catégorie") }, { sequence: 60 });
```

### Adjusting the Debounce

In `universal_search_provider.js`, change the `debounceDelay` value:

```javascript
registry.category("command_setup").add("*", {
    debounceDelay: 500,  // slower typing → fewer requests
    ...
});
```

## Security

| Model | Group | Read | Write | Create | Delete |
|-------|-------|------|-------|--------|--------|
| `bf.universal.search` | Internal User | Yes | No | No | No |
| `bf.universal.search.config` | Internal User | Yes | No | No | No |
| `bf.universal.search.config` | Settings (admin) | Yes | Yes | Yes | Yes |

All searches respect Odoo's standard access control. No `sudo()` calls are used. The `search_all` method catches `AccessError` exceptions per model and skips inaccessible models silently.

## File Structure

```
bf_universal_search/
├── __init__.py
├── __manifest__.py
├── README.md
├── hooks.py                                # post_init_hook: seeds config data
├── migrations/
│   └── 18.0.1.3.0/
│       └── post-migrate.py                 # Creates config records (noupdate=True)
├── models/
│   ├── __init__.py
│   ├── bf_universal_search.py              # Virtual model with search_all()
│   └── bf_universal_search_config.py       # Config model
├── security/
│   └── ir.model.access.csv
├── docs/
│   └── SERVICE_NOTE_2026-02-16.md          # Fix: empty config table
└── static/
    └── src/
        ├── js/
        │   ├── universal_search_provider.js  # Namespace, categories, provider
        │   └── universal_search_systray.js   # Systray magnifying glass
        ├── xml/
        │   └── universal_search.xml          # OWL template
        └── scss/
            └── universal_search.scss         # Minimal styles
```

## Design Rationale

Three approaches were evaluated:

1. **Systray dropdown** — Custom dropdown with search field and grouped results. Rejected: limited width, awkward auto-close behavior, reinvents existing infrastructure.
2. **Command palette extension** (chosen) — Extends Odoo 18's native `Ctrl+K` palette with a `*` namespace. Reuses the dialog, keyboard navigation, debounce, loading states, and footer hints. ~200 lines of JS. Same pattern used by `mail` for `@users` and `#channels`.
3. **Inline navbar search bar** — Permanent search field in the top bar. Rejected: consumes scarce navbar space, responsive issues, requires building dropdown + keyboard navigation from scratch.

## Changelog

### 18.0.1.3.0 (2026-02-16)

- **Fix: search returning no results** — Config records created by `post_init_hook` were immediately deleted by Odoo's `_process_end()` cleanup because they were registered in `ir_model_data` with `noupdate=False` but not defined in any XML data file. Changed to `noupdate=True` and added migration script to recreate the 12 configs.
- Improved error visibility: added `console.error` in the JS provider catch block (previously silent)
- Changed Python search error logging from `debug` to `warning` level for production visibility
- See `docs/SERVICE_NOTE_2026-02-16.md` for the full technical investigation

### 18.0.1.0.0 (2026-02-13)

- Initial release
- `bf.universal.search` virtual model with `search_all()` RPC method
- `bf.universal.search.config` for admin-configurable model inclusion
- Command palette `*` namespace with 5 display categories
- Systray magnifying glass icon
- `post_init_hook` for automatic config seeding
- 12 pre-configured models across contacts, projects, hosting, documents, and more
- Full ACL and record rule enforcement

## Credits

Developed by [Your Company](https://example.com)

Architecture design, code implementation, and documentation were produced with assistance from Claude (Anthropic). All code was reviewed, tested, and validated in a production Odoo 18 environment.

## License Text

```
MIT License

Copyright (c) 2026 Your Company

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
```

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.
