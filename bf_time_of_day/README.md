# BF Time of Day

Plages horaires admin-configurables (Matinée / Midi / Fin de jour / Hors heures…) pour les tâches Odoo et les activités. Chaque plage porte un nom, un pictogramme, une couleur et une heure suggérée. Choisir une plage sur une tâche réécrit l'heure de l'échéance pour pointer sur la plage. Chaque utilisateur peut surcharger l'heure suggérée par sa propre heure (flex time).

## License

LGPL-3 — voir `LICENSE`.

## Features

### Plages horaires admin-configurables
- Modèle `bf.time.of.day` (`name`, `code`, `sequence`, `color`, `icon`, `default_time`, `active`).
- 4 presets seed (`noupdate=1`) : **Matinée** (09:00, ☕), **Midi** (12:00, 🌞), **Fin de jour** (16:00, 🕓), **Hors heures** (19:00, 🌙). Renommables, recolorables, supplémentables — l'admin peut en ajouter autant qu'il veut.
- Menu admin sous *Paramètres → Technique → Plages horaires*. Liste éditable inline avec `widget="color_picker"` et `widget="float_time"` à la minute près.

### Application sur `project.task`
- Champ `time_of_day_id` (Many2one, indexé, `group_expand` pour afficher les colonnes vides en kanban).
- À la création / modification : si `date_deadline` est défini ET qu'une plage est choisie, **l'heure** de la deadline est réécrite sur l'heure effective (la **date** est préservée). Conversion explicite UTC ↔ fuseau utilisateur.
- `default_get` propose la plage la plus proche de l'heure courante locale (wrap-around géré pour *Hors heures*) — un clic épargné sur le cas commun.
- Champs `time_of_day_color` (related, store=True) et `time_of_day_icon` (related) pour la décoration kanban.
- Champ `time_of_day_code` (Selection, computed, store=True, indexé) : miroir stable de `time_of_day_id.code`, clé de la barre de progression kanban. Limité aux 4 plages livrées — une plage admin ajoutée hors `morning/midday/eod/after_hours` laisse le champ vide (et n'apparaît pas dans la barre).

### Application sur `mail.activity`
- Même champ `time_of_day_id`, **purement informationnel** : `mail.activity.date_deadline` est un `Date` (sans heure), donc rien n'est muté côté donnée — la plage sert au filtrage et à l'affichage.
- Si l'activité est planifiée depuis une `project.task` qui porte une plage, la plage est **héritée** par défaut (Quick win D).

### Override personnel par utilisateur (flex time)
- Modèle `bf.time.of.day.user_pref` (`user_id`, `time_of_day_id`, `override_time`) avec contrainte SQL unique `(user_id, time_of_day_id)`.
- Onglet *Plages horaires* sur la fiche utilisateur (`res.users`) — chacun gère ses propres lignes.
- Helper `res.users._tod_effective_time(time_of_day)` : retourne `override_time` si défini, sinon `default_time` admin, sinon `False` (aucune mutation).
- Les presets admin sont des **suggestions** ; l'override personnel gagne.

### Visibilité kanban (« comme l'état de tâche »)
- Inheritance de `project.view_task_kanban` : badge coloré `o_tag_color_<n>` après les tags, prefixé par l'icône Font Awesome de la plage.
- Inheritance de `project.view_task_search_form` : 5 filtres (`Matinée`, `Midi`, `Fin de jour`, `Hors heures`, `Sans plage`) + group-by *Plage horaire*.
- Saved search `Ma journée par plage` (Quick win C) : tâches de l'utilisateur dont la deadline tombe aujourd'hui, groupées par plage — un click pour voir sa journée.
- Display name du modèle préfixé en émoji (☕ Matinée, 🌞 Midi…) — le menu déroulant m2o est lisible sans widget custom.

### Vue kanban « all-tasks » : jour en X, plage en Y
- Le kanban Odoo n'a qu'un seul axe (colonnes). Approximation native d'une grille 2D sur la page `/odoo/all-tasks` :
  - Inheritance de `project.view_task_kanban_inherit_all_task` (la vue primaire de l'action all-tasks) : la barre de progression stock sur `state` est **remplacée** par une barre sur `time_of_day_code` (segments Matinée / Midi / Fin de jour / Hors heures, cliquables pour filtrer la colonne). Portée limitée à cette vue — les kanbans de projet et « Mes tâches » gardent la barre `state`.
  - Saved search `Tâches par jour` : groupe les colonnes par jour d'échéance (`date_deadline:day`) **et** restreint aux tâches qui portent une plage (`time_of_day_code != False`). Combinée à la barre ci-dessus → colonnes = jours, barre = plages horaires, sans segment « Autre » parasite.
  - Couleurs de la barre en **arc de journée** : aube (`info`) → midi (`warning`) → crépuscule (`danger`) → nuit (`muted`).
  - **Icônes dans la barre** : SCSS scopé (classe `o_bf_tod_progressbar` ajoutée au `<kanban>`) qui injecte une icône Font Awesome en `::before` sur chaque segment (☕ / ☀ / 🕓 / 🌙). Odoo ne rend pas les segments vides ; un segment étroit rogne l'icône proprement — les couleurs prennent le relais. L'infobulle native (`{compte} {plage}`) reste disponible au survol.

### Sécurité
| Modèle | Lecture | Écriture / création / unlink |
| --- | --- | --- |
| `bf.time.of.day` (presets) | tous internes (`base.group_user`) | admins seulement (`base.group_system`) |
| `bf.time.of.day.user_pref` | propre user via `ir.rule` (`user_id == user.id`) | propre user via même règle |
| `bf.time.of.day.user_pref` | admins voient tout via 2e règle | admins peuvent tout modifier |

Aucune `ir.rule` sur `project.task` / `mail.activity` — l'ACL stock reste en place. Aucune escalade `sudo()` en dehors du lookup d'override (read-only sur ses propres préférences).

## Architecture

```
bf.time.of.day (preset, admin)
   ├── used by ──> project.task.time_of_day_id   (mute date_deadline.time, user TZ)
   ├── used by ──> mail.activity.time_of_day_id  (display + filter, no mutation)
   └── overridden per-user ──> bf.time.of.day.user_pref (user_id, time_of_day_id, override_time)

res.users
   ├── one2many bf_time_of_day_pref_ids
   └── _tod_effective_time(tod) → override_time | default_time | False
```

## Dépendances

- `project` — extension de `project.task` (kanban, form, list, search).
- `mail` — extension de `mail.activity` (form popup, tree).

## Configuration

- **Presets seed** : Matinée 09:00, Midi 12:00, Fin de jour 16:00, Hors heures 19:00 (`noupdate=1` — modifications admin survivent les upgrades).
- **Couleurs** : palette Odoo standard (1-11). Les seed utilisent 10 / 3 / 4 / 9.
- **Icônes** : Font Awesome 4 classe (`fa-coffee`, `fa-sun-o`, etc.). Mappage émoji câblé pour `fa-coffee`, `fa-sun-o`, `fa-clock-o`, `fa-moon-o`, `fa-cutlery`, `fa-bed`, `fa-bolt`, `fa-leaf`, `fa-fire`, `fa-star`. Si l'icône n'est pas mappée, le display name omet l'émoji et garde juste le nom.

## Comportement de la deadline

| Cas | Effet sur `date_deadline` |
| --- | --- |
| `time_of_day_id` non défini | inchangé |
| `time_of_day_id` défini, `date_deadline` non défini | inchangé |
| `time_of_day_id` défini, `date_deadline` défini, `default_time` blank et pas d'override | inchangé |
| `time_of_day_id` défini, `date_deadline` défini, `default_time` ou override défini | **heure** de la deadline réécrite, **date** préservée, fuseau utilisateur respecté |

## File Structure

```
bf_time_of_day/
├── __init__.py
├── __manifest__.py
├── README.md
├── LICENSE
├── data/
│   ├── bf_time_of_day_data.xml         # 4 presets seed (noupdate=1)
│   └── bf_time_of_day_filters.xml      # ir.filters "Ma journée par plage" + "Tâches par jour"
├── models/
│   ├── __init__.py
│   ├── bf_time_of_day.py               # le modèle preset + display_name émoji
│   ├── bf_time_of_day_user_pref.py     # override per-user
│   ├── res_users.py                    # one2many + helper _tod_effective_time
│   ├── project_task.py                 # field + smart default + deadline mutation
│   └── mail_activity.py                # field + heritage du slot depuis la tâche parente
├── security/
│   ├── ir.model.access.csv
│   └── bf_time_of_day_security.xml     # ir.rule sur user_pref
├── static/src/scss/
│   └── kanban_badge.scss               # styling du chip kanban
└── views/
    ├── bf_time_of_day_views.xml        # list + form + action
    ├── res_users_views.xml             # onglet "Plages horaires" sur la fiche user
    ├── project_task_views.xml          # form + kanban + tree + search inheritance
    ├── mail_activity_views.xml         # form popup + tree inheritance
    └── menu.xml                        # Settings → Technical → Plages horaires (admin)
```

## Changelog

### 18.0.1.3.1 (2026-05-14)
- Barre de progression `time_of_day_code` recolorée en tons doux (arc de journée pastel), icône des segments passée en anthracite. Piste (`bg-300`) et segment « Autre » (`bg-200`) ramenés à un gris très doux. Changement purement SCSS, scopé à `o_bf_tod_progressbar`.

### 18.0.1.3.0 (2026-05-14)
- Saved search `Tâches par jour` restreinte à `time_of_day_code != False` (et sortie du bloc `noupdate` pour rester alignée aux upgrades) : la barre de progression n'a plus de segment « Autre » et le compteur de colonne ne compte que les tâches planifiées.
- Couleurs de la barre `time_of_day_code` du kanban all-tasks en arc de journée (`info` → `warning` → `danger` → `muted`).
- Icônes Font Awesome dans les segments de la barre via SCSS scopé (`o_bf_tod_progressbar` sur le `<kanban>`).

### 18.0.1.2.0 (2026-05-14)
- Champ `time_of_day_code` (Selection computed, store=True, indexé) sur `project.task`, miroir stable de `time_of_day_id.code`.
- Kanban « all-tasks » : barre de progression `state` remplacée par une barre `time_of_day_code` (portée limitée à `project.view_task_kanban_inherit_all_task`).
- Saved search `Tâches par jour` : colonnes kanban groupées par jour d'échéance. Combinée à la barre de plage horaire → approximation jour-en-X / plage-en-Y demandée (BF #22536).

### 18.0.1.0.0 (2026-05-07)
- Initial release : modèle preset (admin) + override per-user + extension `project.task` (mutation deadline avec fuseau, smart default, group_expand) + extension `mail.activity` (héritage de la plage depuis la tâche parente, display only) + inheritance kanban / form / tree / search avec badge coloré et icône Font Awesome + saved search « Ma journée par plage ».

## Credits

Blue Fox Inc — https://bluefoxconsultant.com
