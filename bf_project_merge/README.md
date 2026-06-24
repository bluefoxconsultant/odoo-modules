# Blue Fox — Regroupement de tâches (`bf_project_merge`)

Un assistant Odoo **« Regrouper les tâches »** qui consolide réellement plusieurs
tâches en une seule : au lieu d'archiver les doublons en y laissant tout leur
contenu, il **déplace** ce contenu vers la tâche conservée, puis archive le reste.

## Le problème

Un regroupement qui se contente de mettre `active = False` sur les tâches
sources laisse derrière lui toute la matière utile — la conversation du chatter,
les activités, les heures, les dépendances. Sur la tâche conservée, on ne voit
plus rien de cet historique. Ce module corrige cela.

## Utilisation

1. Dans une vue **liste** de tâches, cochez deux tâches ou plus.
2. Menu **Actions ⚙️ → Regrouper les tâches**.
3. Choisissez la destination :
   - **Vers une tâche existante** — l'une des tâches sélectionnées est conservée ;
   - **Vers une nouvelle tâche** — une tâche neuve est créée (titre + projet).
4. **Regrouper**. Le contenu est déplacé vers la tâche conservée et les autres
   tâches sont archivées.

## Ce qui est déplacé vers la tâche conservée

| Élément | Modèle | Comportement |
|---|---|---|
| Messages, notes, courriels | `mail.message` | Déplacés — **sauf** les messages système `notification` (changements d'étape, suivi de champs), laissés sur la tâche d'origine comme trace. |
| Activités planifiées | `mail.activity` | Déplacées. |
| Suiveurs | `mail.followers` | Ré-abonnés via `message_subscribe` (sans doublon). |
| Pièces jointes de la tâche | `ir.attachment` (`res_model='project.task'`) | Re-pointées vers la tâche conservée. |
| Pièces jointes du chatter | `ir.attachment` liées à un message | Suivent leur message déplacé (aucune action distincte). |
| Évaluations | `rating.rating` | Re-pointées. |
| Événements de calendrier reliés | `calendar.event` | Re-pointés. |
| Feuilles de temps | `account.analytic.line` | Re-pointées (`task_id`, et `project_id` aligné sur la destination). |
| Dépendances | `project.task` (`depend_on_ids` / `dependent_ids`) | La tâche conservée hérite des prédécesseurs ; les successeurs pointent désormais sur elle (les liens vers la tâche archivée sont retirés). |
| Sous-tâches | `project.task` (`parent_id`) | Rattachées à la tâche conservée. |

Les éléments rattachés à un `mail.message` (valeurs de suivi, notifications,
réactions, mises en favori) suivent automatiquement le message déplacé.

## Sécurité

L'assistant est réservé aux **utilisateurs du module Projet**
(`project.group_project_user`). Avant tout déplacement, le module vérifie que
l'utilisateur a le droit de **modifier** chacune des tâches sélectionnées
(`check_access('write')`) ; les déplacements de sous-enregistrements s'effectuent
ensuite en `sudo`, la tâche servant de frontière de confiance.

## Dépendances

`project` uniquement. `hr_timesheet`, les dépendances de tâches, `rating` et
`calendar` sont exploités **s'ils sont présents**, jamais requis.

## Antériorité

Ce module remplit le même besoin que le module communautaire OCA
[`project_merge`](https://github.com/OCA/project) (Onestein), mais il est écrit
de façon indépendante par Blue Fox et ajoute la réattribution complète du
contenu (conversation, heures, dépendances, etc.).

## Licence

LGPL-3 — © Blue Fox Inc.
