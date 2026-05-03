# BF Bloc-notes

Notes rapides riches pour Odoo 18, avec multi-liens vers les fiches, conversion en activité en un clic, raccourcis clavier et icône systray.

## License

LGPL-3 — voir `LICENSE`.

## Features

### Capture rapide
- **Icône systray 📝** : clic gauche = nouvelle note, clic droit = liste filtrée sur tes notes.
- **Raccourcis clavier** : `Alt+N` ouvre le dialog de capture, `Alt+Shift+N` ouvre la liste.
- **Auto-link** : si tu es sur une fiche partner / task / project / lead, le dialog pré-remplit le lien.
- **Drop-zone images** : colle (`Ctrl+V`) ou glisse une image dans l'éditeur, l'attachment est créé automatiquement et l'image insérée dans le corps de la note.
- **Ctrl+Entrée** dans le dialog enregistre la note.

### Multi-lien (m2m)
Une note peut être attachée à plusieurs fiches en même temps. Modèle `bf.note.link` (`note_id`, `res_model`, `res_id`) ; le champ `res_ref` reste comme « lien primaire » pour compat ascendante. Smart button « Notes (N) » sur partner / task / project / lead via la mixin batch.

### Conversion en activité
Depuis le form d'une note, boutons rapides dans le header :
- **Aujourd'hui** (J)
- **Demain** (J+1)
- **+2 jours** / **+1 semaine**
- **Personnaliser…** (wizard avec date, type d'activité, assignation, résumé éditable)

Une activité est créée par fiche liée (ex. note liée à 3 tâches → 3 activités). Type par défaut : **Tâche** (`mail.mail_activity_data_todo`). Smart button « Activités (N) » sur la note pour retrouver toutes les activités créées.

### Visibilité hybride
- Privée par défaut (`is_shared=False`) : seul l'auteur la voit.
- Cocher « Partagée » la rend lisible par tous les internes ; seul l'auteur peut toujours modifier.

### Vues
- **Kanban** : cartes colorées (color picker), pin button intégré, snippet du body, étiquettes, lien primaire, échéance.
- **Liste** : toggle pin direct, filtres « Mes notes / Épinglées / Partagées / Liées / Échéance dépassée ».
- **Calendar** : si tu mets un `deadline_date`, la note apparaît sur ton calendrier (non confondue avec une activité).
- **Form** : éditeur HTML, onglet « Liens » avec sequence handle pour réordonner.

### Sécurité
| Risque | Mitigation |
| --- | --- |
| RPC injection sur `quick_create_from_context` | Whitelist explicite des clés (`name`, `body`, `tag_ids`, `pinned`, `color`, `deadline_date`, `is_shared`, `res_model`, `res_id`, `link_ids`). `user_id` est forcé à `env.user.id` indépendamment du payload. |
| Énumération de modèles via `Reference` | `_selection_target_model` filtre par `ir.config_parameter` `bf_bloc_notes.reference_models` (10 modèles par défaut). |
| AccessError sur fiche cible | `bf.note.link._compute_res_name` utilise `sudo()` + `try/except` pour le `display_name` ; le check d'accès se fait au clic « Voir la fiche ». |
| Visibilité notes | 2 ir.rule séparées : lecture (auteur OU `is_shared`), écriture/unlink (auteur seul). |
| Smart button N+1 | `bf.note.link.mixin` utilise `read_group` batch — 1 query pour 200 records. |

### Performance
- `bf_note_count` calculé en une seule requête via `read_group`, pas de N+1 sur listviews / kanban.
- `res_name` stocké (compute store=True) sur `bf.note.link`, pas relu à chaque affichage.
- Pas de `mail.activity.mixin` sur `bf.note` (overhead évité).

## Architecture

```
bf.note ──┬── link_ids ──> bf.note.link ──(res_model, res_id)──> {res.partner, project.task, …}
          ├── tag_ids ──> bf.note.tag
          └── activity_ids (m2m) ──> mail.activity (sur la fiche cible)

bf.note.link.mixin (AbstractModel)
   └─ inherited by: res.partner, project.task, project.project, crm.lead
        └─ adds: bf_note_count (batch), action_open_bf_notes
```

## Dépendances

- `web`, `mail` (toujours présents)
- `project` (smart button + form heritage de `project.task`, `project.project`)
- `crm` (smart button + form heritage de `crm.lead`) — Odoo Community
- `contacts` (smart button + form heritage de `res.partner`)

## Configuration

- **Modèles disponibles dans `Reference`** : `ir.config_parameter` clé `bf_bloc_notes.reference_models` (CSV). Défaut : `res.partner,project.project,project.task,crm.lead,helpdesk.ticket,calendar.event,account.move,sale.order,purchase.order,hr.employee`.
- **Étiquettes seed** : Idée, À faire, Référence, Brouillon (créées une fois, `noupdate=1`).

## Tests

```bash
odoo -d <db> -u bf_bloc_notes --test-enable --test-tags /bf_bloc_notes --stop-after-init --http-port=0
```

9 tests couvrent : auto-titre, multi-lien, batch count, RPC whitelist, visibilité privée/partagée (read + write), création d'activité par lien, garde-fou note non-liée.

## Changelog

### 18.0.2.0.0 (2026-05-02)
- Ajout : multi-liens via `bf.note.link` (m2m vers fiches).
- Ajout : conversion en activité (boutons rapides + wizard).
- Ajout : visibilité hybride (`is_shared`).
- Ajout : `deadline_date` + vue calendar.
- Ajout : drop-zone images dans l'éditeur quick-create.
- Ajout : pin/unpin direct depuis le kanban.
- Sécurité : RPC `quick_create_from_context` whitelisté, `user_id` forcé.
- Perf : mixin `bf.note.link.mixin` avec batch `read_group` (élimine N+1 sur smart buttons).
- Stack : retiré `mail.activity.mixin` (overhead) et `tracking=True` (bruit chatter).

### 18.0.1.0.0 (2026-05-02)
- Initial release : `bf.note` + `bf.note.tag`, systray, hotkeys Alt+N / Alt+Shift+N, smart buttons sur 4 modèles.

## Credits

Blue Fox Inc — https://bluefoxconsultant.com
