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
- **Smart buttons** — prochaine rencontre sur la tâche, comptes rendus et OdJ sur le projet et sur l'événement calendrier, tâches à discuter sur l'OdJ
- **Courriels** — modèles pour l'envoi de l'ordre du jour et du compte rendu, avec section dédiée aux tâches à discuter
- **Rapport PDF** — rendu brandé de l'ordre du jour avec section « Éléments d'action à discuter »
- **Unification OdJ ↔ compte rendu ↔ événement calendrier** — un même `calendar.event` peut porter un OdJ et un compte rendu ; la création d'un compte rendu depuis un événement ayant déjà un OdJ rattache automatiquement les deux (`meeting.agenda.meeting_record_id`) et propage le projet
- **Drapeau « Besoin d'un OdJ »** — sur `calendar.event`, champ calculé `bf_needs_agenda` (vrai si la rencontre est à venir, sans OdJ et non dispensée) ; bannière d'alerte sur le formulaire et filtre dédié dans la vue de recherche
- **Opt-out par rencontre** — case à cocher `bf_skip_agenda` sur `calendar.event` pour les rencontres internes courtes ou récurrentes
- **Rappel automatique avant rencontre** — cron quotidien `_cron_remind_unsent_agenda` qui crée une activité « À faire » due aujourd'hui sur l'organisateur (utilisateur interne uniquement) si la rencontre arrive dans les 7 prochains jours et que l'OdJ n'a pas encore été envoyé ; idempotent via le `summary` de l'activité
- **Contributions publiques des destinataires** — après l'**envoi** d'un OdJ encore en brouillon et **jusqu'à sa confirmation**, le courriel inclut un lien public tokenisé (`/meeting/agenda/<token>`) permettant aux destinataires (même sans compte Odoo) de **proposer des sujets** et de **laisser des commentaires/notes**. La fenêtre s'ouvre et se ferme automatiquement (`contributions_open ≡ envoyé ET état brouillon`) ; la confirmation referme le lien. Les sujets proposés arrivent en **modération** (`source='contributed'`, `moderation_state='pending'`) et n'entrent ni dans le PDF ni dans le courriel tant que le gestionnaire ne les a pas acceptés ; les commentaires sont postés au chatter et l'organisateur reçoit une activité de relecture
- **Fenêtre de visibilité des pièces jointes** — une pièce jointe à un OdJ ou à un compte rendu peut n'être visible qu'avant, pendant (± 2 h) ou après la rencontre, ou sur une plage personnalisée (`bf_visibility_window`, `bf_visible_from`, `bf_visible_until`). Le choix d'une fenêtre relative calcule les bornes à partir de la date de la rencontre liée ; une `ir.rule` filtre la lecture pour `group_meeting_user`, alors que `group_meeting_manager` voit toujours tout. Les pièces jointes des autres modèles ne sont pas touchées. ⚠️ **Limite connue** : à traiter comme un confort d'affichage, pas comme un contrôle d'accès. La règle compare à `time.strftime(...)`, or `ir.rule._compute_domain` est mis en cache par `ormcache` sur `(uid, su, model, mode, allowed_company_ids)`, sans composante temporelle : l'horodatage est évalué une fois puis figé jusqu'à invalidation du cache, si bien qu'une pièce jointe peut rester lisible après son `bf_visible_until`. L'implémentation exacte au moment de l'appel existe (`ir_attachment._bf_visibility_domain`) mais n'est pas encore branchée
- **Tableau de bord** — vue OWL agrégeant les OdJ et comptes rendus à suivre en tuiles KPI et en taux de complétion sur 30 jours, avec horizons réglables par utilisateur (`bf_meeting_dashboard_lookahead_days` / `lookback_days`, plafonnés à +90 / -180 jours) et exclusion possible par contact (`bf_skip_dashboard`)

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
| `calendar.event` (hérité) | Smart buttons « Comptes rendus » et « Ordre du jour », champs `meeting_agenda_ids/id/count`, `bf_skip_agenda` (opt-out), `bf_needs_agenda` (calculé), création d'un OdJ ou d'un compte rendu depuis l'événement |
| `project.knowledge.item` (hérité) | Lien Many2many vers les comptes rendus qui référencent l'item |
| `ir.attachment` (hérité) | Fenêtre de visibilité des pièces jointes de rencontre (`bf_visibility_window`, `bf_visible_from`, `bf_visible_until`, `bf_is_visible_now`) |
| `res.company` (hérité) | `meeting_logo` — logo affiché sur la bannière sombre des PDF et courriels (repli sur le logo standard de la société) |
| `res.partner` (hérité) | `bf_skip_dashboard` — exclut les rencontres de ce contact du tableau de bord |
| `res.users` (hérité) | Horizons personnels du tableau de bord (`bf_meeting_dashboard_lookahead_days`, `bf_meeting_dashboard_lookback_days`) |
| `meeting.dashboard` / `meeting.dashboard.line` | Tableau de bord des rencontres (vue OWL agrégeant OdJ/comptes rendus à suivre) |

### Dépendances

| Module | Rôle |
|---|---|
| `project` | Projets, tâches, rattachement des rencontres |
| `mail` | Chatter, activités, modèles de courriel |
| `calendar` | Lien avec les événements calendrier Odoo |
| `project_knowledge_matrix` | Matrices de connaissances alimentées par les décisions |
| `bf_onboarding_base` | Panneau d'accueil guidé (étape de configuration) et champs de marque `report_brand_{primary,dark,logo}` sur `res.company` (palette des rapports PDF et des courriels) |
| `bf_timezone` | Affichage des dates/heures dans le fuseau du destinataire |

Le module de marque blanche `bluefox_branding` n'est **pas** requis : il ne fait qu'exposer et styler les champs `report_brand_*`, qui appartiennent à `bf_onboarding_base` depuis la v18.0.2.0.0 de ce dernier. Sans lui, les rapports et courriels se rendent avec la palette de la société, ou avec les couleurs Odoo par défaut (`#714B67` / `#212529`) si elle n'est pas configurée.

### Sécurité

- Groupe `group_meeting_user` — consulter et modifier les rencontres des projets auxquels l'utilisateur a accès (via `project.message_partner_ids`)
- Groupe `group_meeting_manager` — accès complet à tous les comptes rendus, ordres du jour, décisions et présences
- Règles `ir.rule` sur `meeting.record`, `meeting.agenda`, `meeting.topic`, `meeting.decision`, `meeting.agenda.topic`, `meeting.attendance` (une paire utilisateur/gestionnaire par modèle)
- Règles `ir.rule` sur `ir.attachment` — appliquent la fenêtre de visibilité aux seules pièces jointes de `meeting.record` / `meeting.agenda`, sans toucher aux autres (voir la limite connue de la fenêtre, plus haut)
- Règles `ir.rule` sur `meeting.dashboard.line` — une règle globale multi-société, plus la paire utilisateur/gestionnaire calquée sur `meeting.record`. ⚠️ La vue SQL agrège **toutes** les rencontres de la base : `get_dashboard_data()` lit en SQL brut, hors ORM, donc ni les ACL ni ces règles ne s'y appliquent et il **réimplémente les mêmes garde-fous à la main**. Toute évolution de l'un doit être répercutée dans l'autre
- ACL standard déclarées dans `security/ir.model.access.csv`

### Tâche planifiée

| Cron | Modèle | Fréquence | Rôle |
|---|---|---|---|
| `ir_cron_remind_unsent_agenda` | `meeting.agenda` | quotidien | Crée une activité « À faire » sur l'OdJ vers l'organisateur si la rencontre arrive dans 7 jours et que l'OdJ n'est pas envoyé |
| `cron_meeting_dashboard_daily_digest` | `meeting.dashboard` | quotidien | Digest quotidien des rencontres (legacy, livré **désactivé** ; méthode `_cron_send_daily_digest()` conservée pour déclenchement ad hoc) |

### Rendu HTML sécurisé

Les notes structurées JSON (titre de sujet, points, questions ouvertes) sont rendues en HTML via `markupsafe.escape()` avant concaténation, pour éviter toute injection lorsque le contenu provient d'une source externe (transcription IA, collage utilisateur).

### Contributions publiques — sécurité

Le contrôleur public (`controllers/main.py`, routes `type="http", auth="public", csrf=False`) suit le modèle de `bf_sign` :

- **Jeton = capacité** — `secrets.token_urlsafe(32)` (256 bits), `copy=False`, `readonly`, `index=True`, restreint au groupe `group_meeting_user`, donc jamais sérialisé vers une lecture portail/publique. Frappé à l'**envoi**, pas à la création (surface d'exposition minimale).
- **Aucun IDOR** — l'URL ne porte que le jeton (pas d'`id` d'enregistrement) ; la résolution se fait par jeton via `hmac.compare_digest` (temps constant). Un jeton forgé/expiré renvoie un `404` indiscernable.
- **Fenêtre re-vérifiée côté serveur** — chaque GET et POST revalide `contributions_open` après résolution : un onglet resté ouvert ne peut pas écrire après la confirmation.
- **Assainissement** — tout texte libre passe par `markupsafe.escape` avec plafonds stricts (titre ≤ 200, description/commentaire ≤ 4000, nom ≤ 120, courriel ≤ 254). Création de sujet par dictionnaire explicite (`source`/`moderation_state` non pilotables depuis le POST).
- **Limitation de débit** — deux limiteurs par IP : échecs de jeton (10 / 300 s) et volume de POST (5 / 60 s). L'IP retenue est **celle du pair de la socket**, jamais `X-Real-IP` / `X-Forwarded-For` : ces en-têtes sont forgeables si l'endpoint est joignable en direct, et les lire soi-même rendrait le limiteur contournable. Sous `proxy_mode = True`, werkzeug (ProxyFix) a déjà réécrit `remote_addr` à partir d'un nombre de sauts de confiance.
- **Liste blanche de lecture** — la page publique ne reçoit que le titre, la date formatée, les objectifs (texte) et les **noms des sujets acceptés**. Aucun contexte, préparation, note, tâche, pièce jointe, participant, chatter ou proposition d'un autre contributeur.
- **Écritures sous `sudo()`** — l'utilisateur public n'a aucun droit ORM ; toutes les écritures sont explicites avec des dictionnaires sûrs. Les notes sont postées avec `author_id=False` (l'identité du contributeur vit dans le corps, jamais forgée en `res.partner`).

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_meeting --stop-after-init --no-http
```

Après installation, un groupe « Gestionnaire » est attribué par défaut à `base.user_admin` ; les autres utilisateurs reçoivent le groupe « Utilisateur » via les paramètres du profil.

## Licence

LGPL-3

## Remerciements

Créé et maintenu par Blue Fox Inc. Des assistants de codage IA ont été utilisés comme outils de productivité durant le développement.
