# BF Bureau

Tableaux de bord (« bureaux ») configurables par l'utilisateur pour Odoo 18 : juxtapose plusieurs actions Odoo dans une seule vue, avec changement de type de vue par panneau, raccourcis clavier par bureau, créneaux horaires automatiques et barre latérale de bureaux sauvegardés.

## License

LGPL-3 — voir `LICENSE`.

## Concepts

Un **bureau** (`bf.bureau.desk`) est une mise en page nommée combinant plusieurs **panneaux** (`bf.bureau.pane`). Chaque panneau pointe vers une `ir.actions.act_window` existante (Mes activités, Toutes les tâches, Boîte de réception, etc.) et la rend en place via le composant `<View>` d'Odoo, avec ses propres barres de filtre, vue switcher, recherche favoris, et clic-pour-ouvrir.

Six mises en page disponibles :

| Layout | Slots | Usage typique |
| --- | --- | --- |
| `single` | `full` | Un seul panneau plein écran (focus) |
| `two_columns` | `left_full`, `right_full` | Deux côte-à-côte pleine hauteur |
| `two_top_one_bottom` | `top_left`, `top_right`, `bottom_full` | 2 en haut + 1 large en bas (défaut) |
| `two_bottom_one_top` | `top_full`, `bottom_left`, `bottom_right` | Inverse : 1 en haut + 2 en bas |
| `four_quadrant` | `top_left`, `top_right`, `bottom_left`, `bottom_right` | Grille 2×2 |
| `stacked_three` | `row_1`, `row_2`, `row_3` | Trois rangées empilées |

## Features

### Mise en page
- **Six layouts prédéfinis** sélectionnables depuis le formulaire de bureau ; une contrainte `_check_slot_layout` valide que le slot d'un panneau est compatible avec le layout du bureau parent.
- **Poids 1–4** par panneau (`bf.bureau.pane.weight`) → ratios `fr` calculés JS-side pour `grid-template-rows / -columns`. Permet d'agrandir un panneau sans changer de layout.
- **Domaine et contexte par panneau** (`domain_override`, `context_override`) : expressions Python (validées server-side via `ast.literal_eval`) appliquées en `AND` / `merge` par-dessus celles de l'action. Même action, plusieurs angles dans différents bureaux.

### Navigation
- **View switcher par panneau** : kanban / liste / fiche / tableau croisé / graphique / calendrier / activité (selon `view_mode` de l'action). État persisté dans `bf.bureau.pane.view_type` au clic sur « 💾 Enregistrer la disposition ».
- **Clic sur un enregistrement** ouvre le formulaire plein écran via le service action standard d'Odoo (préserve fil d'Ariane et contexte de recherche).
- **Bouton « Nouveau »** lance le formulaire blanc de l'action.
- **Bouton 🔄 par panneau** force un rechargement complet (re-mount du `<View>` via `t-key`).
- **Filtres favoris** scoped à l'action embarquée (pas au bureau client) : un wrapper `BfBureauPaneView` fait `useSubEnv({ config: { actionId, getDisplayName } })` pour que `ir.filters.create_or_replace` enregistre sous le bon `action_id`. `loadIrFilters: true` charge les favoris au montage.

### Multi-bureaux
- **Barre latérale** (`bf-bureau-sidebar`) listant tous les bureaux de l'utilisateur, avec étoile « par défaut », chip raccourci clavier, surbrillance du bureau actif. Visibilité persistée dans `localStorage` (clé `bf_bureau.sidebar.visible`).
- **Raccourcis clavier par bureau** (`bf.bureau.desk.shortcut_key`, ex. `alt+1`) — enregistrés via le service `hotkey` d'Odoo en mode `global` pour fonctionner depuis n'importe quelle vue. Les fermetures retournées par `hotkey.add()` sont stockées et appelées dans `onWillUnmount`.
- **Créneau horaire** (`bf.bureau.desk.active_when` ∈ {`always`, `morning` 5–12, `afternoon` 12–18, `evening` 18–24, `night` 0–5}). `get_default_desk_id` ouvre prioritairement le bureau dont le créneau couvre l'heure courante, puis tombe sur le `is_default`, puis le premier bureau.
- **Dupliquer** (`action_duplicate_for_me`) clone le bureau et ses panneaux pour l'utilisateur courant — utile pour A/B-tester un layout sans perdre l'original.

### Sécurité
| Risque | Mitigation |
| --- | --- |
| Voir les bureaux d'un autre utilisateur | `ir.rule` `[('user_id', '=', user.id)]` sur `bf.bureau.desk`, cascade via `desk_id.user_id` sur `bf.bureau.pane`. Admins (`base.group_system`) bypass pour support. |
| Bureau-par-défaut multiple | SQL exclusion constraint : `EXCLUDE (user_id WITH =) WHERE (is_default AND active)`. |
| Raccourci clavier en collision | SQL exclusion : `EXCLUDE (user_id, shortcut_key)` quand non vide. |
| Slot incompatible avec layout | `@api.constrains("slot", "desk_id")` ⇒ `_check_slot_layout`. |
| `view_type` non supporté par l'action | `@api.constrains("view_type", "action_id")` ⇒ `_check_view_type_in_action`. |
| `domain_override` / `context_override` malicieux | `ast.literal_eval` côté serveur (pas d'`eval`/`exec`), validation `isinstance(list)` / `isinstance(dict)`. |
| Lecture d'action côté client | `read_desk_for_render` fait `pane.action_id.sudo().read([...])` mais seulement après `desk.check_access_rights("read")` + `check_access_rule("read")` sur le bureau. |

### Performance
- `read_desk_for_render` retourne tout en un seul appel ORM (1 round-trip vs N+1).
- `actionService.loadAction()` en parallèle pour tous les panneaux via `Promise.all`.
- `Object.assign(env.config, ...)` mute la config locale du sub-env, pas celle du parent — pas de fuite entre panneaux.

## Architecture

```
bf.bureau.desk ─┬─ pane_ids ──> bf.bureau.pane ──> ir.actions.act_window
                ├─ user_id ──> res.users  (record rule scope)
                ├─ shortcut_key (Char, unique per user)
                ├─ active_when (Selection: always / morning / afternoon / evening / night)
                ├─ layout (Selection: 6 valeurs)
                └─ is_default (Boolean, exclusion par user)

bf.bureau.pane ─┬─ slot (Selection : 12 valeurs, validé contre layout)
                ├─ view_type (kanban / list / form / pivot / graph / calendar / activity)
                ├─ weight (1–4 → grid-template fr ratio)
                ├─ name_override (Char optionnel)
                ├─ domain_override (Char, ast.literal_eval list)
                └─ context_override (Char, ast.literal_eval dict)
```

Côté client (`static/src/js/bf_bureau_desk.js`) :

```
BfBureauDesk (registry "actions" → tag "bf_bureau_desk")
├── _load() : ORM call read_desk_for_render + list_user_desks en parallèle
├── _registerHotkeys() : hotkey.add() pour chaque desk.shortcut_key
├── BfBureauPaneView (wrapper par panneau)
│   └── useSubEnv({ config: { actionId, actionName, getDisplayName, ... }})
│       └── <View>  (Odoo natif, type=kanban/list/...)
└── gridStyle() : compute grid-template-rows/columns from pane weights
```

## Installation

Ajouter le module aux `addons_path` Odoo et l'installer depuis le menu Apps. Sur première installation, un bureau par défaut « Mon bureau » est seedé pour `base.user_admin` avec trois panneaux (Mes activités, Toutes les tâches, Boîte de réception). `noupdate="1"` ⇒ les modifications utilisateur ne sont pas écrasées aux upgrades subséquents.

## Dépendances

- `web`, `base`, `mail`, `project` (core Odoo)
- `bf_email_management` (pour le panneau Boîte de réception du bureau seed)

## Configuration

- **Mes bureaux** (sous-menu de Mon bureau) : créer / archiver / dupliquer / définir par défaut.
- **Édition d'un bureau** : layout dropdown + tableau inline des panneaux (slot, action, view type, poids, overrides).
- **Sidebar** : icône ☰ dans la barre du bureau pour basculer.
