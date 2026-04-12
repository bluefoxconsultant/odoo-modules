# Daily To-Do Digest

Module Odoo 18 pour l'envoi automatique d'un digest quotidien par courriel contenant les activités et tâches de l'utilisateur, la météo locale et une citation inspirante.

## Fonctionnalités

### Contenu du digest

| Section | Description |
|---------|-------------|
| **Météo** | Température actuelle avec emoji, min/max, précipitations pour la ville configurée (défaut: Montréal) |
| **Activités en retard** | Activités `mail.activity` avec date d'échéance passée |
| **Activités du jour** | Activités `mail.activity` avec date d'échéance aujourd'hui |
| **Tâches en retard** | Tâches `project.task` avec date d'échéance passée |
| **Tâches du jour** | Tâches `project.task` avec date d'échéance aujourd'hui |
| **Aperçu 7 jours** | Grille visuelle cliquable des 7 prochains jours avec compteurs colorés (vert/jaune/rouge) |
| **Tâches non visibles** | Résumé des tâches avec `display_in_project=False` (lien cliquable) |
| **Citation inspirante** | Citation aléatoire parmi 120 citations d'artistes, poètes et penseurs |

### Caractéristiques techniques

- **Fuseau horaire**: Conversion automatique UTC → America/Montreal pour les comparaisons de dates
- **Filtre de visibilité**: Exclut les tâches avec `display_in_project=False` du listing détaillé
- **Template stylise**: Template HTML avec les couleurs et polices personnalisees
- **Liens cliquables**: Chaque tâche/activité contient un lien direct vers l'enregistrement Odoo
- **Cron configurable**: Vérification toutes les heures, envoi à l'heure configurée
- **Preheader email**: Aperçu rapide dans les clients mail (ex: "3 en retard | 5 aujourd'hui | ☀️ -8°C")
- **Emojis météo**: Icônes visuelles selon les conditions (☀️🌧️❄️⛈️ etc.)

## Installation

1. Copier le module dans le répertoire `addons`
2. Mettre à jour la liste des modules dans Odoo
3. Installer "Daily To-Do Digest"

```bash
# Mise à jour et installation
docker exec <container> odoo -d <database> -i daily_todo_digest --stop-after-init
```

## Configuration

### Accès

**Paramètres → Technique → Digest quotidien → Configuration**

### Paramètres disponibles

| Champ | Description | Défaut |
|-------|-------------|--------|
| Nom | Nom du digest | "Mon digest quotidien" |
| Heure d'envoi | Heure d'envoi (0-23, fuseau America/Montreal) | 4 |
| Destinataires | Utilisateurs qui recevront le digest | - |
| Compagnie | Filtre optionnel par compagnie (non utilisé actuellement) | Compagnie courante |

### Widgets activables

| Widget | Description |
|--------|-------------|
| Activités en retard | Inclure les activités passées |
| Activités du jour | Inclure les activités du jour |
| Tâches en retard | Inclure les tâches passées |
| Tâches du jour | Inclure les tâches du jour |
| Météo | Inclure la météo locale |
| Citation inspirante | Inclure une citation aléatoire |

### Configuration météo

| Champ | Description | Défaut |
|-------|-------------|--------|
| Ville météo | Nom affiché de la ville | Montréal |
| Latitude | Coordonnée latitude | 45.5017 |
| Longitude | Coordonnée longitude | -73.5673 |

**Coordonnées communes:**
- Montréal: 45.5017, -73.5673
- Québec: 46.8139, -71.2080
- Toronto: 43.6532, -79.3832
- Ottawa: 45.4215, -75.6972

## Citations

Le module inclut **120 citations** d'artistes, révolutionnaires, poètes et rêveurs, organisées par thèmes:

- **Mutualisme et anarchisme**: Proudhon, Kropotkine, Emma Goldman, Bakunin
- **Poètes et écrivains**: Rimbaud, Hugo, Neruda, García Lorca, Camus, Beauvoir, Galeano
- **Artistes**: Frida Kahlo, Picasso, Oscar Wilde, Van Gogh
- **Droits civiques**: Martin Luther King Jr., Nelson Mandela, Gandhi, Audre Lorde
- **Féministes**: Maya Angelou, bell hooks, Virginia Woolf
- **Penseurs**: Einstein, Sénèque, Socrate, Aristote
- **Activistes contemporains**: Greta Thunberg, Paulo Freire, Aaron Swartz
- **Penseurs décoloniaux**: Frantz Fanon, Aimé Césaire
- **Proverbes du monde**: africains, chinois, japonais, amérindiens, persans

### Gestion des citations

**Paramètres → Technique → Digest quotidien → Citations**

Les citations peuvent être ajoutées, modifiées ou désactivées via l'interface.

## Structure du module

```
daily_todo_digest/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── daily_digest.py          # Modèle principal et logique d'envoi
│   └── inspirational_quote.py   # Modèle des citations
├── data/
│   ├── daily_digest_cron.xml    # Tâche planifiée (cron)
│   └── inspirational_quotes.xml # 120 citations pré-chargées
├── security/
│   └── ir.model.access.csv      # Droits d'accès
└── views/
    └── daily_digest_views.xml   # Vues et menus
```

## Modèles

### `daily.digest.config`

Configuration du digest quotidien.

| Champ | Type | Description |
|-------|------|-------------|
| `name` | Char | Nom du digest |
| `active` | Boolean | Actif/Inactif |
| `user_ids` | Many2many | Destinataires |
| `send_hour` | Integer | Heure d'envoi (0-23) |
| `include_overdue_activities` | Boolean | Inclure activités en retard |
| `include_today_activities` | Boolean | Inclure activités du jour |
| `include_overdue_tasks` | Boolean | Inclure tâches en retard |
| `include_today_tasks` | Boolean | Inclure tâches du jour |
| `include_weather` | Boolean | Inclure météo |
| `weather_city` | Char | Nom de la ville |
| `weather_latitude` | Float | Latitude |
| `weather_longitude` | Float | Longitude |
| `include_quote` | Boolean | Inclure citation |
| `company_id` | Many2one | Compagnie (optionnel) |
| `last_sent` | Datetime | Dernier envoi |

### `daily.digest.quote`

Citations inspirantes.

| Champ | Type | Description |
|-------|------|-------------|
| `quote` | Text | Texte de la citation |
| `author` | Char | Auteur |
| `active` | Boolean | Actif/Inactif |

## API Météo

Le module utilise l'API **Open-Meteo** (gratuite, sans clé API requise).

- **URL**: `https://api.open-meteo.com/v1/forecast`
- **Données récupérées**: température actuelle, min/max, précipitations, probabilité de précipitations, code météo
- **Fuseau horaire**: America/Montreal

## Format du courriel

### Sujet
```
🌄 Votre journée | Jeudi, le 5 février 2026
```

### Structure HTML
- Header avec logo et titre
- Barre d'accent cyan (#29ABE2)
- Sections de contenu avec tableaux stylisés
- Footer avec coordonnées
- Barres d'accent bicolores en bas

### Couleurs du theme

| Élément | Couleur |
|---------|---------|
| Fond extérieur | #2E3132 |
| Header | #22303B |
| Accent | #29ABE2 |
| Texte clair | #E6EDF3 |
| Texte gris | #6B7280 |
| Rouge (retard) | #dc3545 |
| Vert (succès) | #198754 |

### Police
`'Lexend', 'Segoe UI', Arial, sans-serif`

## Envoi manuel

### Via l'interface
- **Envoyer maintenant**: Envoie le digest à tous les destinataires configurés
- **Test (moi seul)**: Envoie un test uniquement à l'utilisateur connecté

### Via le shell Odoo
```python
config = env['daily.digest.config'].search([('name', '=', 'Mon digest')], limit=1)
config._send_digest()
env.cr.commit()
```

## Dépendances

- `base`
- `mail`
- `project`

### Librairies Python
- `pytz` (inclus dans Odoo)
- `requests` (inclus dans Odoo)

## Licence

LGPL-3

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

## Auteur

Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.
