# Changelog - TentaClaude (bf_claude_chat)

## v18.0.1.4.1 - 2026-03-20

### Correction de l'overlay cache derriere le chatter (portal pattern)

**Probleme** : Le panneau lateral TentaClaude s'affichait derriere la barre chatter d'Odoo
("Envoyer un message", "Note", "Activites") et le statusbar du formulaire. Malgre un
`z-index: 2147483647` sur l'overlay, celui-ci etait confine au stacking context de la navbar
(`position: fixed` + z-index cree un stacking context CSS isole).

L'approche precedente (booster le z-index de `.o_main_navbar` a 2147483646 via `:has()`)
ne resolvait pas le probleme fondamental : un descendant `position: fixed` ne peut pas
echapper au stacking context de son ancetre.

**Solution** : Implementation d'un pattern portal OWL qui deplace le noeud DOM de l'overlay
vers `document.body` apres chaque rendu, et le restaure avant chaque patch pour compatibilite
avec le DOM virtuel d'OWL.

- `onMounted` / `onPatched` : deplace `.bf-panel-overlay` vers `<body>`, insere un `Comment`
  node (`<!-- bf-overlay-anchor -->`) comme placeholder
- `onWillPatch` / `onWillUnmount` : restaure l'overlay a sa position originale pour que le
  diff OWL fonctionne correctement
- Suppression du hack CSS `.o_main_navbar:has(.bf-panel-overlay) { z-index: 2147483646 }`

L'overlay participe maintenant au root stacking context, garantissant qu'il s'affiche
au-dessus de tous les elements Odoo sans aucune dependance a la structure CSS interne d'Odoo.

Voir la section "Note technique : Overlay Portal Pattern" du README pour les details.

### Fichiers modifies

| Fichier | Changements |
|---------|-------------|
| `static/src/js/claude_systray.js` | Import hooks OWL (onMounted, onPatched, onWillPatch, onWillUnmount), ajout portal pattern, t-ref overlay |
| `static/src/xml/claude_chat.xml` | Ajout `t-ref="panelOverlay"` sur `.bf-panel-overlay` |
| `static/src/scss/claude_chat.scss` | Suppression hack z-index navbar, commentaire mis a jour |
| `README.md` | Section technique "Overlay Portal Pattern" + mise a jour description panneau |

---

## v18.0.1.4.0 - 2026-03-18

### Sessions filtrees par enregistrement courant

**Probleme** : Cliquer TentaClaude dans la barre de widgets montrait TOUTES les conversations.
On veut voir seulement celles liees a l'enregistrement courant (fiche qu'on regarde).

**Solution** :
- Ajout `res_model` (Char, indexed) et `res_id` (Integer, indexed) au modele `claude.chat.session`
- Migration DB (`pre-migrate.py`) : colonnes + index composite
- Stockage du contexte a la creation de session (model + res_id de la fiche Odoo)
- Filtrage `list_sessions` par `res_model`/`res_id` (backward-compatible : sans params = toutes)
- Le systray recharge les sessions a chaque ouverture (le contexte de page peut changer)
- Rafraichissement post-envoi avec le meme filtre
- Empty state : "No chats for this record" quand filtre actif et 0 resultats
- La page plein ecran reste inchangee (affiche toutes les conversations)

### Correction des timeouts sur requetes complexes

**Probleme** : Les requetes complexes (matrice 95+ items, cross-ref NC, multi-tool) depassaient les limites de temps.

**Causes et corrections** :
1. `max_turns` fallback dans le controller = 10 (vs 25 dans le bridge) -- **corrige a 25**
2. `CLAUDE_TIMEOUT` = 300s -- **augmente a 600s** (bridge) / 660s (controller, +60s buffer socket)
3. MCP per-tool timeout = 30s -- **augmente a 120s** (bf + pme configs)
4. Aucun timeout XML-RPC -- **ajout `TimeoutTransport` (60s)** dans `clients/odoo_client.py`
5. Timeout NC par defaut = 15s -- **augmente a 30s** dans `clients/nextcloud_client.py`

### Correction du rendu HTML dans share_to_task

**Probleme** : Les tags HTML s'affichaient en texte brut dans le chatter Odoo lors du partage.

**Solution** : Ajout de `body_is_html=True` dans `task.message_post()` (share_to_task).

### Amelioration detection HTML dans le bridge

**Probleme** : `_has_html()` ne detectait que les block tags, ratant le HTML inline abondant.

**Solution** : Detection elargie -- block tags OU (>2 occurrences de `<` + au moins un tag HTML).

### Fichiers modifies

| Fichier | Changements |
|---------|-------------|
| `__manifest__.py` | Version 18.0.1.3.0 -> 18.0.1.4.0 |
| `models/claude_chat_session.py` | Ajout res_model + res_id |
| `models/res_config_settings.py` | Timeout defaut 300 -> 660 |
| `controllers/main.py` | Context storage, filtered sessions, max_turns fix, share HTML fix, timeout |
| `static/src/js/claude_systray.js` | Filtrage sessions, reload a chaque ouverture, empty state contexte |
| `static/src/xml/claude_chat.xml` | Empty state "No chats for this record" |
| `migrations/18.0.1.4.0/pre-migrate.py` | Nouveau : colonnes + index |
| `bridge/server.py` | TIMEOUT 600, _has_html() elargi |
| `bridge/claude-chatbot-bridge.service` | CLAUDE_TIMEOUT=600 |
| `bridge/mcp_config_bf.json` | timeout 120 |
| `bridge/mcp_config_pme.json` | timeout 120 |
| `clients/odoo_client.py` | TimeoutTransport (60s) |
| `clients/nextcloud_client.py` | timeout 30s |

---

## v18.0.1.3.0 - 2026-03-05

### Panneau lateral (remplacement du dropdown)

**Probleme** : Le widget systray utilisait le composant `<Dropdown>` d'Odoo, qui ouvrait
un petit popup de 480px. Trop petit pour une utilisation confortable, et le dropdown
se fermait au moindre clic en dehors.

**Solution** : Remplacement complet par un panneau lateral fixe qui glisse depuis la droite.

- Largeur : 50% du viewport (min 420px, max 800px), hauteur 100vh
- Overlay semi-transparent (rgba 0,0,0,0.15) derriere le panneau
- Fermeture par : touche Escape, clic sur l'overlay, bouton X
- Animation CSS `translateX` pour le slide-in (0.2s ease-out)
- Suppression de la dependance au composant `Dropdown` d'Odoo
- Import OWL `useEffect` pour gerer le listener Escape

### Correction du z-index

**Probleme** : La barre du chatter Odoo ("Envoyer Message", "Note", "Activites") se
positionnait par-dessus le panneau TentaClaude, bloquant la vue.

**Solution** : z-index monte a 100000 (vs ~1060 pour les elements Odoo les plus hauts).

### Amelioration de la capture de contexte

**Probleme** : `router.current` ne retourne pas toujours `model` et `resId` dans Odoo 18,
selon le type de vue et la navigation. Le contexte de page n'etait donc pas toujours
detecte, et le badge de contexte n'apparaissait pas.

**Solution** : 3 strategies en cascade pour capturer le contexte :

1. `router.current` - proprietes `model`, `resModel`, `resId`, `res_id`, `id`
2. Parsing du hash URL via `URLSearchParams(window.location.hash)`
3. `actionService.currentController.action.res_model` via le service action d'Odoo

Le display_name est extrait depuis (en ordre de priorite) :
1. `.o_breadcrumb .active`
2. `.o_control_panel .breadcrumb-item.active`
3. `document.title` (moins " - Odoo")

Le contexte est desormais re-capture a chaque ouverture du panneau ET a chaque "New Chat".

### Noms de contexte "pretty"

**Probleme** : Le badge de contexte affichait le nom brut du modele (`project.task`) ou
seulement le display_name, sans indication claire du type d'enregistrement.

**Solution** : Ajout d'un mapping `MODEL_LABELS` pour les modeles courants :

| Modele | Label |
|--------|-------|
| project.task | Tache |
| project.project | Projet |
| helpdesk.ticket | Ticket |
| res.partner | Contact |
| account.move | Facture |
| sale.order | Commande |
| crm.lead | Opportunite |
| knowledge.article | Article |

Le badge affiche maintenant : "Tache #1234 - Nom de la tache"

### URL dans le contexte bridge

**Probleme** : L'URL complete de la page n'etait pas transmise au bridge, ce qui limitait
la capacite de Claude a referencer la page exacte.

**Solution** :
- Le JS capture `window.location.href` et l'inclut dans le payload context
- Le controller Odoo transmet `url` (max 500 chars) au bridge
- Le bridge inclut `url:` dans les tags `<page-context>` du prompt dynamique
- Condition relaxee : le contexte est transmis si `model` OU `displayName` est disponible
  (avant, seul `model` etait requis)

### Fichiers modifies

| Fichier | Changements |
|---------|-------------|
| `static/src/js/claude_systray.js` | Reecrit : side panel, capture contexte multi-strategie, MODEL_LABELS, useEffect |
| `static/src/xml/claude_chat.xml` | Template systray reecrit : side panel au lieu de Dropdown |
| `static/src/scss/claude_chat.scss` | Styles side panel (overlay, animation, z-index 100000), remplacement classes systray |
| `controllers/main.py` | Ajout champ `url` dans le contexte bridge |
| `__manifest__.py` | Version bump 18.0.1.2.0 -> 18.0.1.3.0 |
