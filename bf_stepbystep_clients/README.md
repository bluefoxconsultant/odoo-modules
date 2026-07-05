# bf_stepbystep_clients — Suivi d'accompagnement client (Step-by-Step)

Module Odoo 18 (CE) qui visualise la **progression linéaire** de tout mandat
d'accompagnement client. Il transforme les étapes (`project.task.type`) d'un
projet en une barre de progression « étape par étape » et fournit un tableau de
bord interne qui, d'un coup d'œil, montre où en est chaque client (étape
courante, budget d'heures consommé, échéancier).

Le module est **agnostique au domaine** : il fonctionne pour n'importe quel type
de mandat séquentiel (implantation, conformité, onboarding, etc.). Les étapes
sont définies par vos propres stages de projet.

## Fonctionnalités

- **Tableau de bord OWL** (`bf.stepbystep.dashboard`) listant tous les mandats
  actifs avec, pour chacun : l'étape courante, la progression en pourcentage, le
  budget d'heures consommé et l'avancement dans l'échéancier.
- **Vue détaillée par client** : la séquence complète des étapes, l'étape
  atteinte, les tâches et les heures.
- **Progression configurable par stage** via quatre champs ajoutés sur
  `project.task.type` (voir ci-dessous) : numéro d'étape, libellé court,
  visibilité client et consigne au client.
- **Classification sectorielle** automatique du mandat d'après le nom du projet
  (CPE/garderie, OBNL, scolaire, entreprise…) pour le regroupement à l'affichage.
- **Post-install hook idempotent** qui pré-remplit les numéros/libellés d'étape
  sur les stages existants à partir d'une table de mots-clés (réexécutable sans
  effet de bord).

## Champs ajoutés sur `project.task.type`

| Champ | Type | Description |
|-------|------|-------------|
| `progression_step_number` | Integer | Rang de l'étape dans la progression linéaire. `0` (défaut) = stage exclu de la visualisation. |
| `progression_step_name` | Char (traduit) | Libellé court affiché (ex. « Démarrage »). Si vide, le nom du stage est utilisé. |
| `progression_client_visible` | Boolean | Étape affichable côté client (à décocher pour les étapes internes : revue, facturation…). |
| `progression_client_action_hint` | Text (traduit) | Consigne à présenter au client lorsque le mandat atteint cette étape. |

## Configuration

1. Sur chaque stage de projet (`Projet › Configuration › Étapes`), renseigner le
   **numéro d'étape de progression** (1, 2, 3…) et un **libellé court**. Laisser
   à `0` les stages à exclure.
2. Décocher **Visible portail client** pour les étapes purement internes.
3. Ouvrir le menu **Suivi d'accompagnement** pour visualiser le tableau de bord.

À l'installation, le *post-install hook* tente de mapper automatiquement les
stages existants ; ajustez au besoin.

## Installation

```bash
# Installer / mettre à jour via votre procédure habituelle de déploiement Odoo, p. ex. :
odoo -d <database> -i bf_stepbystep_clients --stop-after-init
```

Dépendances Odoo : `base`, `project`, `hr_timesheet`.

## Licence

LGPL-3
