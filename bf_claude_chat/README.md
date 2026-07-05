# TentaClaude - Module Odoo 18

Module Odoo permettant de clavarder avec Claude AI directement dans l'interface Odoo, via un panneau lateral integre et une page plein ecran.

## Architecture

```
bf_claude_chat/
├── controllers/
│   └── main.py              # Endpoints JSON-RPC (/claude-chat/*)
├── models/
│   ├── claude_chat_session.py   # Modele claude.chat.session
│   ├── claude_chat_message.py   # Modele claude.chat.message
│   └── res_config_settings.py   # Parametres (Settings > TentaClaude)
├── security/
│   ├── security.xml             # Regles d'acces (own sessions, admin all)
│   └── ir.model.access.csv      # ACL modeles
├── static/src/
│   ├── js/
│   │   ├── claude_chat.js       # Composant OWL - page plein ecran
│   │   └── claude_systray.js    # Composant OWL - panneau lateral systray
│   ├── scss/
│   │   └── claude_chat.scss     # Styles (side panel, bulles, animations)
│   └── xml/
│       └── claude_chat.xml      # Templates OWL (ChatAction + SystrayItem)
├── views/
│   ├── menu.xml                 # Menu principal + admin (All Sessions)
│   └── res_config_settings.xml  # Page Settings
└── migrations/
    ├── 18.0.1.0.0/
    │   └── pre-migrate.py
    └── 18.0.1.4.0/
        └── pre-migrate.py       # Ajout res_model/res_id + index
```

## Composants principaux

### Panneau lateral (systray)

- Bouton "Claude" dans la barre de navigation Odoo
- S'ouvre en panneau lateral droit (50% largeur ecran, min 420px, max 800px)
- Overlay semi-transparent, fermeture par Escape / clic overlay / bouton X
- **Portal pattern** : l'overlay est deplace vers `<body>` via JS pour echapper au stacking context de la navbar et s'afficher au-dessus de tous les elements Odoo (chatter, statusbar, modals)
- Animation slide-in depuis la droite
- Liste des sessions a gauche, zone de chat a droite
- Badge de contexte affichant la page courante avec nom "pretty" (ex: "Tache #1234 - Nom")
- **Filtrage par enregistrement** : le systray montre uniquement les conversations liees a la fiche courante (res_model + res_id). La page plein ecran continue d'afficher toutes les conversations.

### Page plein ecran

- Accessible via le menu principal "TentaClaude" ou le bouton expand du panneau
- Sidebar de sessions (280px) + zone de chat centree (max 900px)
- Renommage de session par double-clic ou icone crayon
- Archivage de session (soft delete via champ `active`)

### Capture de contexte

Lorsque le panneau s'ouvre ou qu'un nouveau chat est cree, le module capture le contexte de la page Odoo courante via 3 strategies en cascade :

1. **Router state** : `router.current` (model, resModel, resId, res_id, id, view_type)
2. **URL hash** : parsing de `window.location.hash` via URLSearchParams
3. **Action service** : `actionService.currentController.action.res_model`

Le nom d'affichage est extrait depuis :
1. Breadcrumb actif (`.o_breadcrumb .active`)
2. Titre du control panel (`.o_control_panel .breadcrumb-item.active`)
3. Titre du document (moins le suffixe " - Odoo")

Le contexte est transmis au bridge comme `<page-context>` avec model, res_id, display_name, view_type et url.

### Partage vers tache

- Bouton "Share to task" dans l'en-tete du chat
- Recherche de taches par nom (debounce 300ms)
- Poste la conversation complete dans le chatter de la tache (note interne)
- Formatage HTML avec bulles colorees reproduisant le style du chat

## Modeles Odoo

### claude.chat.session

| Champ | Type | Description |
|-------|------|-------------|
| name | Char | Titre de la session (auto-genere par le bridge) |
| claude_session_id | Char | ID de session Claude Code (multi-turn) |
| res_model | Char (indexed) | Modele Odoo lie (ex: project.task) |
| res_id | Integer (indexed) | ID de l'enregistrement lie |
| user_id | Many2one(res.users) | Proprietaire |
| message_ids | One2many | Messages de la session |
| message_count | Integer (computed) | Nombre de messages |
| active | Boolean | Archivage soft |

### claude.chat.message

| Champ | Type | Description |
|-------|------|-------------|
| session_id | Many2one(claude.chat.session) | Session parente |
| role | Selection (user/assistant) | Role du message |
| content | Text | Contenu (markdown pour assistant, texte brut pour user) |

## Endpoints JSON-RPC

Tous les endpoints sont en `type="json"`, `auth="user"`, `methods=["POST"]`.

| Route | Description |
|-------|-------------|
| `/claude-chat/send` | Envoie un message, retourne la reponse Claude |
| `/claude-chat/sessions` | Liste les sessions (filtrable par res_model/res_id) |
| `/claude-chat/messages` | Messages d'une session |
| `/claude-chat/rename-session` | Renomme une session |
| `/claude-chat/delete-session` | Archive une session |
| `/claude-chat/search-tasks` | Recherche de taches (pour Share) |
| `/claude-chat/share-to-task` | Poste la conversation dans le chatter |

## Communication avec le bridge

Le module communique avec le service bridge TentaClaude via **Unix socket** (`/run/claude-bridge/bridge.sock` par defaut). Le controller construit une requete HTTP brute sur le socket, envoie le message avec le contexte utilisateur et page, et recoit la reponse Claude.

Le titre intelligent est genere en arriere-plan via un thread daemon qui appelle `/generate-title` sur le bridge apres le premier echange.

## Configuration (Settings > TentaClaude)

| Parametre | Defaut | Description |
|-----------|--------|-------------|
| Enable Claude AI | True | Active/desactive le chatbot |
| Model | sonnet | Modele Claude (sonnet/opus/haiku) |
| Max Turns | 25 | Cycles d'outils max par message |
| Response Timeout | 660s | Delai max pour une reponse (bridge 600s + 60s buffer) |
| API Key | (vide) | Cle Anthropic optionnelle (sinon Max plan) |
| Bridge Socket | /run/claude-bridge/bridge.sock | Chemin du socket Unix |

## Securite

- Chaque utilisateur ne voit que ses propres sessions et messages (ir.rule)
- Les administrateurs (`base.group_system`) voient toutes les sessions
- Les utilisateurs ne peuvent pas supprimer les messages (perm_unlink=0)
- Le contenu des sessions de renommage est sanitise (HTML strip, max 120 chars)
- Le contexte de page est limite en taille (model 64, display_name 200, url 500)

## Note technique : Overlay Portal Pattern

### Probleme

Le composant systray est rendu a l'interieur de `.o_main_navbar`, qui possede `position: fixed` et un `z-index` (via Bootstrap). En CSS, un element positionne avec un z-index cree un **stacking context** : tous ses descendants sont confines a ce contexte pour le z-ordering, meme s'ils ont `position: fixed` et un z-index maximal.

Consequence : le panneau lateral et son overlay, bien qu'ayant `z-index: 2147483647`, ne pouvaient pas s'afficher au-dessus d'elements situes en dehors de la navbar (comme la barre chatter "Envoyer un message" / "Note" / "Activites", ou le statusbar du formulaire), car ceux-ci participent a un stacking context different (celui de `.o_action_manager` ou du root).

### Approches ecartees

1. **Booster le z-index de la navbar** (`z-index: 2147483646 !important`) : ne resout pas le probleme fondamental. Le stacking context de la navbar est au-dessus de tout le reste, mais l'overlay est DANS ce contexte, pas au-dessus.

2. **`z-index: auto` sur la navbar** : supprimerait le stacking context, mais `position: fixed` + z-index est requis par Bootstrap/Odoo pour que la navbar reste visible au-dessus du contenu lors du scroll.

3. **CSS `body:has(.bf-panel-overlay)` pour abaisser les z-index** des barres problematiques : fragile, depend de la structure CSS interne d'Odoo qui change entre versions.

### Solution : portal vers `<body>`

Le pattern portal deplace le noeud DOM de l'overlay de son emplacement OWL (dans la navbar) vers `document.body` (root du document). Dans le root stacking context, le `z-index: 2147483647` s'applique directement et l'overlay se positionne au-dessus de tous les autres elements.

**Implementation avec les hooks de cycle de vie OWL :**

```
DOM apres rendu OWL :            DOM apres portal :

<nav .o_main_navbar>              <nav .o_main_navbar>
  <div .o_menu_systray>             <div .o_menu_systray>
    <button>Claude</button>           <button>Claude</button>
    <div .bf-panel-overlay>  ---->    <!-- bf-overlay-anchor -->
      <div .bf-side-panel/>         </div>
    </div>                        </nav>
  </div>                          ...
</nav>                            <div .bf-panel-overlay>  <-- direct child of <body>
                                    <div .bf-side-panel/>
                                  </div>
```

Le defi est de concilier ce deplacement avec le DOM virtuel d'OWL, qui s'attend a trouver les elements la ou il les a rendus. Le pattern utilise 4 hooks :

| Hook | Action | Raison |
|------|--------|--------|
| `onMounted` | Portal vers `<body>` | Apres le premier rendu, deplacer l'overlay |
| `onWillPatch` | Restaurer dans la navbar | Avant que OWL patche le DOM, remettre l'element a sa place d'origine pour que le diff fonctionne |
| `onPatched` | Portal vers `<body>` | Apres le patch, re-deplacer l'overlay |
| `onWillUnmount` | Restaurer dans la navbar | Avant la destruction du composant, remettre l'element pour qu'OWL puisse le supprimer proprement |

Un `Comment` node (`<!-- bf-overlay-anchor -->`) sert de placeholder pour marquer la position originale dans le DOM OWL, permettant la restauration precise avant chaque patch.

```javascript
// Hooks OWL dans setup()
const _portalToBody = () => {
    const el = this.overlayRef.el;
    if (el && el.parentNode !== document.body) {
        this._overlayPlaceholder = document.createComment("bf-overlay-anchor");
        el.parentNode.insertBefore(this._overlayPlaceholder, el);
        document.body.appendChild(el);
    }
};
const _restoreFromPortal = () => {
    if (this._overlayPlaceholder && this._overlayPlaceholder.parentNode) {
        const el = document.body.querySelector(".bf-panel-overlay");
        if (el) {
            this._overlayPlaceholder.parentNode.insertBefore(el, this._overlayPlaceholder);
        }
        this._overlayPlaceholder.remove();
        this._overlayPlaceholder = null;
    }
};

onMounted(_portalToBody);
onWillPatch(_restoreFromPortal);
onPatched(_portalToBody);
onWillUnmount(_restoreFromPortal);
```

### Pourquoi pas un composant Dialog/Popover d'Odoo ?

Les composants `Dialog` et `Popover` d'Odoo 18 utilisent un mecanisme de portal similaire (rendu dans `.o_dialog_container` au niveau du body). Cependant :
- `Dialog` impose une structure modale (header/body/footer) inadaptee a un panneau lateral
- `Popover` est concu pour des elements ancres a un bouton, pas pour un panneau plein hauteur
- Les deux ajoutent des dependances a des composants internes d'Odoo dont l'API peut changer

Le portal manuel est plus leger et ne depend que de l'API OWL stable (`useRef`, `onMounted`, `onPatched`, `onWillPatch`, `onWillUnmount`).

## Deploiement

Mise a jour :
```bash
# Via XML-RPC (button_immediate_upgrade sur ir.module.module)
# Ou via restart container avec flag -u :
docker exec <container> odoo -c /etc/odoo/odoo.conf -d <db> -u bf_claude_chat --stop-after-init
```

Apres mise a jour, forcer le rechargement des assets navigateur : `Ctrl+Shift+R`.
