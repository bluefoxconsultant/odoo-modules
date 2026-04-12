# Courriel Blue Fox

Module Odoo 18 Community ajoutant un accès direct à une instance SnappyMail (ou tout autre webmail) depuis la barre systray d'Odoo, sans quitter l'interface.

## Cas d'usage

Les équipes utilisant Odoo comme environnement de travail principal doivent souvent basculer entre Odoo et leur webmail pour gérer leurs courriels. Ce module fournit un accès un-clic au webmail dans une fenêtre modale, préservant le contexte Odoo.

## Fonctionnalités

- **Icône courriel dans la systray** — bouton permanent en haut à droite d'Odoo
- **Ouverture en modal** — le webmail s'affiche dans une fenêtre intégrée, pas un nouvel onglet
- **URL configurable** — paramètre système pour pointer vers n'importe quel webmail (SnappyMail, Roundcube, etc.)
- **Zéro persistance** — aucun modèle de données, configuration uniquement via `res.config.settings`

## Architecture technique

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

### Dépendances

| Module | Rôle |
|---|---|
| `base` | Seule dépendance — framework Odoo |

### Configuration

L'URL du webmail est stockée dans `ir.config_parameter` sous la clé `bf_webmail.url`. Modifiable via **Paramètres → Paramètres généraux → Blue Fox Webmail**.

### Sécurité

Pas de modèle persistant, donc pas d'ACL spécifiques. La configuration est restreinte à `base.group_system` (administrateurs) via le pattern standard `res.config.settings`.

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_webmail --stop-after-init
```

Puis définir l'URL du webmail dans les paramètres généraux.

## Licence

LGPL-3

## Remerciements

Créé et maintenu par Blue Fox Inc. Des assistants de codage IA ont été utilisés comme outils de productivité durant le développement.
