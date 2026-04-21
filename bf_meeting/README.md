# Rencontres (bf_meeting)

Module Odoo 18 Community couvrant le cycle complet d'une rencontre : ordre du jour, événement calendrier, compte rendu structuré, décisions, présences, et liaison bidirectionnelle avec les tâches et les matrices de connaissances.

## Cas d'usage

Permettre à une équipe de projet de planifier, tenir et documenter ses rencontres à partir d'Odoo, sans outil externe : préparation de l'ordre du jour à partir des tâches en cours, envoi par courriel aux participants, prise de notes structurées, production d'un compte rendu PDF brandé, et suivi des décisions comme lignes de matrice de connaissances.

## Fonctionnalités

- **Ordres du jour (`meeting.agenda`)** — titre, date, projet, participants, sujets planifiés, envoi par courriel aux destinataires
- **Comptes rendus (`meeting.record`)** — sujets abordés, décisions, notes structurées JSON rendues en HTML sécurisé, rapport PDF, suivi de l'envoi
- **Décisions (`meeting.decision`)** — décisionnaires, contexte, transfert optionnel vers les matrices de connaissances
- **Présences (`meeting.attendance`)** — statut (présent / absent / excusé) et rôle par participant
- **Tâches à discuter** — quatre modes de rattachement d'une `project.task` à une rencontre à venir :
  - *Épinglée* : lien explicite vers un ordre du jour précis
  - *Prochaine rencontre client* : apparaît au prochain OdJ admissible du client
  - *Prochaine rencontre projet* : apparaît au prochain OdJ admissible du projet
  - *Toutes les rencontres client/projet* : apparaît à chaque OdJ admissible tant que la tâche est ouverte
- **Résolution dynamique** — les tâches taguées sont calculées à chaque ouverture de l'OdJ (formulaire, PDF, courriel) et disparaissent dès qu'elles sont fermées
- **Annulation d'un OdJ** — les tâches hard-linkées sans tag soft reçoivent une activité « À faire » due aujourd'hui pour être réassignées ; les tâches taguées basculent automatiquement vers le prochain OdJ admissible
- **Transfert vers compte rendu** — `action_create_meeting_record` transfère les tâches hard-linkées vers `meeting.record.task_ids` et efface le tag soft
- **Smart buttons** — prochaine rencontre sur la tâche, comptes rendus sur le projet et sur l'événement calendrier, tâches à discuter sur l'OdJ
- **Courriels** — modèles pour l'envoi de l'ordre du jour et du compte rendu, avec section dédiée aux tâches à discuter
- **Rapport PDF** — rendu brandé de l'ordre du jour avec section « Éléments d'action à discuter »

## Architecture technique

### Modèles

| Modèle | Rôle |
|---|---|
| `meeting.agenda` | Ordre du jour (projet, date, sujets, tâches, destinataires, état) |
| `meeting.agenda.topic` | Sujet planifié dans un ordre du jour (séquence, durée, présentateur) |
| `meeting.record` | Compte rendu structuré (projet, date, notes JSON, rapport PDF) |
| `meeting.topic` | Sujet abordé dans un compte rendu (points clés, verbatim) |
| `meeting.decision` | Décision prise lors d'une rencontre (contexte, décisionnaire) |
| `meeting.attendance` | Présence d'un participant (statut, rôle) |
| `project.task` (hérité) | Champs de rattachement à une rencontre (`meeting_id`, `bf_meeting_agenda_id`, `bf_discuss_tag`, `bf_next_agenda_id`) |
| `project.project` (hérité) | Smart button « Comptes rendus » |
| `calendar.event` (hérité) | Smart button « Comptes rendus » et création d'un compte rendu depuis l'événement |
| `project.knowledge.item` (hérité) | Lien Many2many vers les comptes rendus qui référencent l'item |

### Dépendances

| Module | Rôle |
|---|---|
| `project` | Projets, tâches, rattachement des rencontres |
| `mail` | Chatter, activités, modèles de courriel |
| `calendar` | Lien avec les événements calendrier Odoo |
| `project_knowledge_matrix` | Matrices de connaissances alimentées par les décisions |

### Sécurité

- Groupe `group_meeting_user` — consulter et modifier les rencontres des projets auxquels l'utilisateur a accès (via `project.message_partner_ids`)
- Groupe `group_meeting_manager` — accès complet à tous les comptes rendus, ordres du jour, décisions et présences
- Règles `ir.rule` sur `meeting.record`, `meeting.agenda`, `meeting.topic`, `meeting.decision`, `meeting.agenda.topic`, `meeting.attendance`
- ACL standard déclarées dans `security/ir.model.access.csv`

### Rendu HTML sécurisé

Les notes structurées JSON (titre de sujet, points, questions ouvertes) sont rendues en HTML via `markupsafe.escape()` avant concaténation, pour éviter toute injection lorsque le contenu provient d'une source externe (transcription IA, collage utilisateur).

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_meeting --stop-after-init --no-http
```

Après installation, un groupe « Gestionnaire » est attribué par défaut à `base.user_admin` ; les autres utilisateurs reçoivent le groupe « Utilisateur » via les paramètres du profil.

## Mise à jour des modèles de courriel

Les deux modèles de courriel (ordre du jour, compte rendu) sont déclarés dans des blocs `<data noupdate="1">`, ce qui est le comportement Odoo attendu pour préserver les modifications manuelles — mais qui bloque également la propagation des changements de template lors d'un `-u bf_meeting`. Pour forcer la mise à jour depuis la source XML :

```bash
docker compose exec odoo odoo shell -d <database> --no-http \
    < /mnt/extra-addons/bf_meeting/tools/force_update_mail_templates.py
```

## Licence

LGPL-3

## Remerciements

Créé et maintenu par Blue Fox Inc. Des assistants de codage IA ont été utilisés comme outils de productivité durant le développement.
