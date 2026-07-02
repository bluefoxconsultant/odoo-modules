# Changelog

All notable changes to `bf_email_management` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This module follows Odoo's `MAJOR.MINOR.PATCH` convention prefixed with the Odoo series (`18.0.X.Y.Z`).

## [18.0.6.0.0] — 2026-07-01

### Added

- **Boutons chatter « Traité » / « Reporter » / « Remettre en boîte ».** Trois nouvelles actions au survol de chaque message de chatter (registre `mail.message/actions`, même mécanisme que « Télécharger en .eml ») : plus besoin de retourner dans l'app Courriels pour sortir un courriel de sa boîte une fois le dossier réglé. Résolution du miroir `bf.email` par Message-ID + `user_id` courant (`mail.message.action_bf_mark_handled` / `action_bf_snooze` / `action_bf_unhandle`) ; si aucun miroir n'existe encore et que le message est projetable (courriel entrant, ou commentaire ayant notifié par courriel), il est ingéré à la volée puis traité — même contrat que `imap_browser_mark_handled`. Boutons visibles sur les messages de type `email` et les commentaires non-notes, usagers internes seulement.
- **« Traité » ferme les rappels du courriel.** `action_archive` marque désormais « fait » (avec feedback) les activités ouvertes portées par la ligne `bf.email` elle-même — un courriel traité ne relance plus. Les activités des tâches/tickets liés ne sont jamais touchées.
- **Règles par défaut pour chaque nouvel usager.** Les 4 règles de tri d'usine (noreply, List-Unsubscribe, client_rank, supplier_rank) n'existaient que pour l'usager ayant installé le module (records XML). Elles sont maintenant semées automatiquement (via `bf.email.rule._seed_defaults_for_user`) à la création du premier `bf.email.account` d'un usager qui n'a encore aucune règle.

### Changed

- **Projection chatter/gateway multi-usager (fan-out par destinataire).** `_cron_sync_emails` attribuait chaque courriel Odoo (chatter + passerelle) à l'usager du cron (`base.user_admin`) — un 2ᵉ usager ne voyait jamais les courriels internes à Odoo, seulement son IMAP. Le cron projette désormais chaque message **une fois par usager interne impliqué** (auteur + destinataires notifiés, via `_route_target_users`), chaque ligne créée dans l'environnement de son propriétaire (`with_user`, même patron que `_sync_account`) : dédup, direction et règles s'appliquent par propriétaire. Repli sur l'usager du cron quand aucun usager interne n'est impliqué (rien n'est perdu). Les comptes de service sont exclus via l'ICP `bf_email.route_exclude_user_ids` (même nom de paramètre que la variante PMEC ; sur BF : meeting-api + Client.e). La contrainte UNIQUE `(message_id_header, company_id, user_id)` porte déjà le fan-out.
- **`_detect_direction` relative à l'usager.** « Sortant » = *j'en suis l'auteur* (`env.user`), plus « l'auteur est un usager interne quelconque ». Nécessaire au fan-out : le courriel d'un collègue est entrant pour moi. Aucun changement pour les données existantes mono-usager.
- **Tableau de bord cohérent pour le groupe admin.** Les KPI ORM (`_date_domain`) et toutes les actions de navigation portent maintenant une borne `user_id = uid` explicite, alignées sur les KPI SQL : un membre de `group_email_admin` voit son propre tableau de bord, pas un mélange global.
- **Compteur « Courriels » des fiches contact borné par usager.** `res.partner.bf_email_count` (SQL brut, qui contourne les règles d'enregistrement) compte désormais seulement les lignes de l'usager courant — cohérent avec le drill-through.

### Security

- **Le groupe admin ne voit plus les comptes IMAP des autres (mots de passe en clair).** La règle `bf_email_account_rule_admin_all` (lecture globale) exposait le champ `password` de tous les usagers via RPC/export — `password="True"` dans la vue ne masque que le widget. Règle supprimée : les membres de `group_email_admin` voient tous les courriels et toutes les règles, jamais les comptes des autres.
- **« Import initial » réservé au groupe admin.** Le wizard lisait TOUS les `mail.message` de la base en `sudo` (sujets + noms d'enregistrements au-delà des règles d'accès) et copiait ces métadonnées dans des lignes appartenant à l'exécutant — accessible à tout usager interne. Menu restreint à `group_email_admin`/`base.group_system` + vérification `has_group` explicite dans `action_run` (le gating de menu ne protège pas l'endpoint RPC).
- **Cohérence anti-injection IMAP.** `imap_browser_get_folders` citait le nom de dossier du `STATUS` à la main (`f'"{name}"'`) au lieu de `imap_quote_mailbox` — aligné sur le reste du module (défense en profondeur ; la valeur vient du `LIST` du serveur, pas de l'utilisateur).

### Notes

- Résidu mono-usager connu et assumé : `_cron_recompute_expected_reply` agrège les médianes de temps de réponse par partenaire sur l'ensemble des usagers (analytique, aucune fuite de visibilité). Le relais ntfy des rappels calendrier reste un point de terminaison global (`bf_email.ntfy_reminder_url`).
- Les lignes chatter/gateway historiques restent la propriété de l'usager admin ; le fan-out s'applique aux messages postérieurs au déploiement.

## [18.0.5.8.0] — 2026-06-25

*(entrée reconstituée a posteriori le 2026-07-01 — la version avait été déployée sans note de changelog)*

### Fixed

- **Badge du menu, action « Boîte de réception » et filtre `filter_inbox` scopés `('user_id', '=', uid)`.** Avant, un membre du groupe « tous les courriels » voyait la boîte de réception de TOUS les usagers (et le badge comptait tout). Déployé conjointement avec `bf_email_systray` v18.0.1.1.0 (compteur systray scoped par usager).

## [18.0.5.7.0] — 2026-06-17

### Security

- **Durcissement contre l'injection de commandes IMAP (CRLF).** `imaplib` ne valide pas ses arguments : une valeur contrôlée par l'expéditeur ou l'utilisateur (Message-ID, nom de dossier, UID) contenant un `CR`/`LF` pouvait injecter une 2ᵉ commande dans la session authentifiée. Nouveaux garde-fous centralisés dans `bf_email_imap` — `imap_quote_mailbox` (échappe `\`/`"`, refuse `CR`/`LF`), `imap_reject_crlf`, `imap_uid_token` (chiffres + `, : *` seulement) — appliqués à : `select_folder` (couvre tous les `SELECT`, y compris les assistants navigateur/backfill qui contournaient la validation OWL), le `SEARCH HEADER Message-ID` et le `COPY` cible de `_imap_writeback_archive`, et les `COPY`/`STORE` de `imap_browser_move` / `imap_browser_move_to_trash` (UID auparavant en `str(uid)` brut).
- **XSS stocké — le HTML brut d'un courriel entrant n'est plus rendu tel quel.** Le champ `body_html` est volontairement non assaini (préservation de la source + assainissement au moment de la réponse). Il était toutefois affiché brut dans le formulaire et dans l'aperçu de l'assistant navigateur, exécutant un `<img onerror=…>` dans la session de l'utilisateur. Nouveau champ calculé non stocké `body_html_display` (= `html_sanitize(body_html)`) rendu dans le formulaire ; `bf.email.browser.preview_body_html` passe en `sanitize=True`. `body_html` reste brut pour les constructeurs de réponse/transfert. (L'aperçu du navigateur OWL était déjà sûr — `iframe sandbox` sans `allow-scripts`.)
- **Contrôle d'accès — assistant « deviner la destination ».** `bf.email.guess.route.action_confirm` postait le courriel dans le chatter de la cible via un proxy `sudo`, sans vérifier les droits de l'utilisateur sur cette cible (champ `Reference` librement éditable). Ajout de `check_access_rights('write')` + `check_access_rule('write')` par cible avant publication, aligné sur l'assistant de re-routage.

### Fixed

- **Trou de capture permanent dans le dossier `Sent`.** Les chemins de capture IMAP avancent des filigranes (« watermarks ») **unidirectionnels** : `_cron_sync_imap` par UID (`last_uid_inbox` / `last_uid_sent`). Tout message sauté ou en échec transitoire lors d'un cycle est dépassé **définitivement** — jamais re-tenté — car le filigrane progresse au-delà. Réconciliation du dossier `Sent` vivant d'Olivier contre les lignes `bf.email` : **492 des 493 messages déjà captés ; 1 manquant** — un courriel envoyé depuis un client de messagerie (UID 7426, « RE: FW: Compte rendu — Johanne Picard », 2026-05-04), jamais importé dans Odoo, que la passe IMAP aurait dû transformer en orphelin mais que `last_uid_sent` avait déjà dépassé sans créer de ligne. Récupéré via la nouvelle passe de réconciliation. *(Note : 3 autres messages d'un fil filé dans une tâche apparaissaient « manquants » à une requête `active=True` — ils étaient en fait captés puis archivés par le classement; aucun bug.)*
  - **Passe de réconciliation IMAP** (`_cron_imap_reconcile`, cron toutes les 6 h, `data/imap_reconcile_cron.xml`). Indépendante des filigranes : re-balaie les N derniers jours (ICP `bf_email.reconcile_days`, défaut 30) des dossiers vivants (`INBOX` + `Sent`) et ingère tout `Message-ID` sans ligne `bf.email` pour le propriétaire. **Côté capture uniquement — IMAP en lecture seule (EXAMINE), aucun COPY/EXPUNGE/écriture.** Idempotente (dédup par `message_id_header` + `user_id`). `_cron_imap_reconcile(days=60)` ou `folders=['Sent']` pour un rattrapage ponctuel ciblé.

### Changed

- **Borne du cron de projection chatter durcie (latent).** `_cron_sync_emails` filtrait par `create_date > last_sync` **strict**. `create_date` n'étant pas unique (un import en lot insère un fil entier au même horodatage à la seconde près), si le filigrane atterrit pile sur cette seconde, les messages partageant cet instant peuvent être sautés sans retour. Passé à `create_date >= last_sync` ; `_should_sync` dédoublonne déjà par `(message_id, user_id)`, donc aucun doublon n'est créé. *Durcissement préventif — aucun incident observé attribué à cette borne, mais le risque était réel pour les courriels envoyés via Odoo (SMTP) absents des dossiers IMAP, que la réconciliation ne couvre pas.*

## [18.0.5.6.0] — 2026-06-16

### Added

- **« Nouveau ▾ › Piste » (crm.lead).** Nouvelle entrée du menu qui crée une piste/opportunité CRM depuis le courriel, avec le courriel importé dans son chatter. Champ calculé non stocké `has_crm` (via `_compute_optional_apps`) : l'entrée n'apparaît que si le module `crm` est installé (aucune nouvelle dépendance dure). `crm.lead.type` se défaute seul (piste/opportunité selon la fonctionnalité « pistes »).
- **Paramètres anti-duplication des pièces jointes.** `bf_email.import_attach_originals` et `bf_email.import_attach_eml` (les deux par défaut activés) permettent de désactiver soit les pièces jointes en clair, soit le `.eml` (qui les recontient déjà) lors de l'import dans un chatter — pour les locataires sensibles au stockage.

### Changed

- **Mutualisation reroute ↔ « Nouveau ▾ ».** `bf.email.reroute._reroute_one` délègue désormais à `bf.email._import_into_chatter(target, force_file=True)` : une seule implémentation de « importer un courriel dans un chatter » (corps + pièces jointes + `.eml`), au lieu de deux copies divergentes. Effet de bord bénéfique : « Lier à un dossier » attache maintenant aussi le `.eml`. Imports `base64` / `bf_email_imap` devenus inutiles retirés du wizard.
- **« Nouveau ▾ » marque le courriel « Traité ».** Après création réussie d'un dossier, `is_handled=True` est posé sur la ligne `bf.email` (drapeau « Traité » déjà utilisé par le filtre Boîte de réception, indépendant du statut read/replied, réversible via « Remettre en boîte ») : le courriel quitte la file de tri une fois transformé en tâche/piste/facture.

## [18.0.5.5.0] — 2026-06-16

### Changed

- **« Nouveau ▾ » importe le courriel dans le chatter, plus dans la description.** Les cinq actions (`action_create_task` / `action_create_helpdesk_ticket` / `action_create_expense` / `action_create_vendor_bill` / `action_create_customer_invoice`) créaient l'enregistrement via un formulaire vierge pré-rempli où **le corps du courriel était versé dans `description` / `narration`** — un champ texte libre qui n'a pas vocation à recevoir un courriel. Désormais l'enregistrement est créé immédiatement et **le courriel est importé dans son chatter** (corps rendu + pièces jointes d'origine + le `.eml` complet, reconstruit au besoin), puis la ligne `bf.email` est classée sous le nouvel enregistrement (orphelins IMAP promus, Message-ID préservé pour le ré-attachement futur des réponses). C'est exactement l'artefact que produit déjà « Lier à un dossier ». Les champs `description` / `narration` restent vides.
  - `helpdesk.ticket.description` étant `required`, il reçoit un court pointeur vers le fil de discussion (le courriel complet vit dans le chatter).
  - Nouveaux helpers `bf.email._import_into_chatter` (même logique que `bf.email.reroute._reroute_one`), `_materialize_email_attachments` et `_spawn_from_email`.
  - **Filet de sécurité :** create + import s'exécutent dans un `savepoint` ; toute exception (champ requis manquant — p. ex. employé absent pour une dépense — ou échec d'import) déclenche un repli sur l'ancien formulaire vierge `default_*`, donc le bouton n'est jamais bloqué sur un enregistrement de production.

## [18.0.5.4.0] — 2026-05-25

### Fixed

- **Réponse aux courriels orphelins : éditeur corrompu (curseur coincé dans la citation, signature avalée).** Le corps cité des lignes IMAP sans chatter injectait le HTML brut du courriel d'origine (`body_html` n'est que dé-NUL-isé, jamais assaini) : documents complets, blocs `<style>`, résidus Outlook/`mso`, balises non fermées. Chargé tel quel dans l'éditeur OWL, ce HTML réorganisait le DOM et avalait la ligne éditable + la signature placées au-dessus de la citation. `_build_reply_quote_body` (branche orpheline) et `_build_forward_body` passent désormais `tools.html_sanitize` sur le corps, comme le fait déjà la branche chatter via `_prep_quoted_reply_body`.
- **« Re: » en double sur le sujet.** Le bouton de réponse standard du chatter (`mail_quoted_reply.reply_message`) préfixait `Re:` sans condition → « Re: Re: … ». Côté `bf.email`, `_open_composer` ne vérifiait qu'un en-tête `Re:` exact et laissait passer « Re: Re: » et le « Re : » français (espace avant les deux-points). Nouveau helper `subject_utils.dedup_subject_prefix` qui réduit toute pile de préfixes (`Re`/`Ré`/`Rép`/`Fwd`/`Fw`/`Tr`, avec ou sans espace) à un seul préfixe canonique ; appliqué dans `_open_composer` **et** dans une surcharge `mail.message.reply_message`. Dépendance `mail_quoted_reply` désormais déclarée explicitement au manifeste (ordre de MRO déterministe).

## [18.0.5.3.0] — 2026-05-20

### Added

- **Bouton « Nouveau ▾ » sur la fiche courriel.** Nouveau widget OWL d'en-tête (`bf_email_new_record_dropdown`) qui crée un dossier à partir du courriel : **Tâche** (`project.task`), **Ticket** (`helpdesk.ticket`), **Dépense** (`hr.expense`), **Facture fournisseur** et **Facture client** (`account.move`, `in_invoice`/`out_invoice`). Chaque entrée ouvre le formulaire de création **pré-rempli** (sujet → nom/réf, contact → partenaire, corps → description) via le `context` `default_*` ; comportement « créer seulement » — le courriel n'est ni rattaché au chatter ni marqué « Traité » (utiliser « Lier à un dossier » pour cela). Backend : méthodes `bf.email.action_create_task` / `action_create_helpdesk_ticket` / `action_create_expense` / `action_create_vendor_bill` / `action_create_customer_invoice` + helper `_open_create_form`.
- **Détection optionnelle Helpdesk / Notes de frais.** Champs calculés non stockés `has_helpdesk` / `has_expense` (`_compute_optional_apps`) : les entrées *Ticket* / *Dépense* du menu n'apparaissent que si `helpdesk_mgmt` / `hr_expense` sont installés. Aucune nouvelle dépendance dure au manifest — le module reste portable.

## [18.0.5.2.0] — 2026-05-20

### Fixed

- **Réponse aux courriels orphelins : signature absente et « mode citation ».** Pour les lignes IMAP sans chatter associé (`mail_message_id` vide), le corps de réponse ne contenait qu'un `<blockquote>` — pas de ligne éditable au-dessus, pas de signature. Le corps reproduit désormais la structure de `mail.message._prep_quoted_reply_body` (ligne éditable + signature de l'utilisateur + citation), comme pour les réponses sur chatter. Nouveau helper `bf.email._compose_signature_block`.
- **Transfert : corps vidé.** Les transferts passaient `is_quoted_reply=False`, or `mail_quoted_reply._compute_body` n'injecte `quote_body` que lorsque ce flag est vrai — le corps transféré était donc silencieusement perdu et le compositeur s'ouvrait vide. `_open_composer` force maintenant `is_quoted_reply=True` pour réponse **et** transfert, et `_build_forward_body` inclut la ligne éditable + la signature.

### Added

- **Zone admin (lecture seule) sur les courriels.** Nouveau groupe `group_email_admin` (catégorie « Gestion des courriels ») avec des `ir.rule` `[(1, '=', 1)]` en lecture seule sur `bf.email`, `bf.email.account` et `bf.email.rule`. Combinées par OU avec les règles propriétaire existantes, elles donnent à un admin la visibilité sur tous les courriels tout en laissant les utilisateurs normaux ne voir que les leurs ; aucune écriture sur les lignes d'autrui. L'appartenance au groupe n'est PAS livrée en données — à attribuer manuellement aux humains seulement.
- **Menu admin dédié + bannière rouge.** Nouvelle action/menu « Tous les courriels — admin » (gardé par `group_email_admin`, contexte `bf_admin_zone`) ; bannière rouge permanente dans le formulaire et coloration `decoration-danger` des lignes appartenant à un autre utilisateur, via le champ calculé non stocké `is_foreign_owner`.

## [18.0.5.0.0] — 2026-05-12

### Added

- **Navigateur IMAP — quick-target reroute.** Le bouton **Router…** du pane d'aperçu et de la barre d'action bulk expose désormais un menu déroulant avec trois cibles fréquentes (Tâche, Ticket, Contact) plus *Autre cible…*. La cible choisie pré-remplit `target_reference` dans le wizard `bf.email.reroute` : pour `res.partner`, le partner du courriel est sélectionné directement ; pour `project.task`/`helpdesk.ticket`, la suggestion existante est conservée mais bornée au modèle demandé. Backend : nouvelle RPC `bf.email.imap_browser_quick_reroute(folder, uids, target_model=None)` qui accepte un seul UID ou une liste.
- **Sélection multiple + bulk reroute.** Chaque ligne du navigateur affiche une case à cocher. Quand au moins une case est cochée, une barre d'action bleue apparaît au-dessus de la liste : *N sélectionné(s)*, dropdown **Router…**, **Traité**, **Effacer la sélection**. Le wizard `bf.email.reroute` poste un `mail.message` par courriel sur la cible commune. La sélection est vidée au changement de dossier ou après une action destructive.
- **Bouton « Reporter » (snooze).** Le wizard `bf.email.snooze` (existant mais non câblé dans la vue OWL) est maintenant accessible depuis le pane d'aperçu et la hotkey `h`. Backend : `imap_browser_snooze(folder, uid)`.
- **Bouton « Activité » (créer activité depuis courriel).** Ouvre `mail.activity` en `target="new"` avec `default_res_model=bf.email`, `default_res_id`, `default_summary` (sujet tronqué), `default_note` (De/Sujet en HTML). Hotkey `t`. Backend : `imap_browser_create_activity(folder, uid)`.
- **Colonne « État ».** Nouvelle colonne dans la liste de messages qui affiche, sous forme d'icônes Font Awesome avec tooltips : `fa-check-circle` (déjà routé), `fa-moon-o` (reporté, `snoozed_until > now`), `fa-reply` (status=`replied`). Remplace l'ancien badge ✓ qui était empilé dans la colonne d'action.

### Changed

- **Bouton « Router » toujours visible.** Le bouton du pane d'aperçu n'est plus caché quand le courriel est déjà ingéré dans `bf.email` ; il permet désormais de re-router vers un autre dossier (toujours bloqué par le wizard avec un `UserError` explicite si la ligne est déjà attachée à un chatter — comportement inchangé du wizard).
- **`imap_browser_get_messages` enrichi.** Chaque dict de message inclut maintenant `is_snoozed` et `is_replied` (calculés depuis `bf.email.snoozed_until` et `status='replied'` respectivement) pour alimenter la colonne État sans round-trip supplémentaire.
- **`bf.email.reroute._suggest_target_reference`** accepte un nouveau kwarg `model_hint` (`project.task` / `helpdesk.ticket` / `res.partner`) qui borne la suggestion au modèle demandé. Sans hint, comportement inchangé.
- **Hotkey `escape`** efface la sélection multiple si elle est non-vide, sinon la recherche (comportement précédent).

### Notes

- Aucune migration de schéma — `bf.email.reroute.target_model_hint` est un Char transient sur un `TransientModel`.

## [18.0.4.0.0] — 2026-05-10

### Breaking

- **Per-user pivot.** The module no longer manages a single shared IMAP mailbox. Each internal user now owns one or more `bf.email.account` rows and only sees their own `bf.email`, `bf.email.account`, and `bf.email.rule` records via a record-rule on `user_id`.
- **Security groups removed.** `group_email_user` and `group_email_manager` (and the module category) are unlinked by `migrations/18.0.4.0.0/post-migrate.py`. ACLs target `base.group_user` directly; the per-row `ir.rule` does the isolation. No admin bypass.
- **IMAP credentials moved.** The `ir.config_parameter` keys `bf_email.imap_host`, `imap_port`, `imap_user`, `imap_password`, `imap_archive_folder`, `imap_writeback_archive`, `imap_batch_size`, `imap_last_uid_inbox`, `imap_last_uid_sent`, `sync_batch_size`, and `auto_link_threshold_days` are migrated to per-account fields and then deleted. `bf_email.last_sync_date` is kept (chatter projection still uses it).
- **`_ingest_rfc822(raw, uid, folder, account)`** — signature changed: the last positional argument is now a `bf.email.account` row instead of the `configured_user` string. Same for `_sync_imap_folder(conn, folder, account)`.

### Added

- **`bf.email.account`** model — per-user IMAP credentials (host, port, login, password), per-folder UID watermarks (`last_uid_inbox`, `last_uid_sent`), per-account archive folder template, batch size, writeback toggle, auto-link threshold, plus a `state` (draft/connected/error) and `last_error` for diagnostics. Actions: **Tester la connexion** and **Synchroniser maintenant**.
- **Menu** `Courriels → Configuration → Mes comptes IMAP` (replaces the legacy Settings panel) listing only the current user's accounts.
- **`bf.email.user_id` + `account_id`** fields. New SQL constraint `UNIQUE(message_id_header, company_id, user_id)` lets two users ingest the same Message-ID without collision.
- **`bf.email.rule.user_id`** — required Many2one on `res.users`. `_apply_rules()` only evaluates rules whose `user_id` matches the row owner; `action_replay_rules()` operates only on the current user's own rows.
- **Migration ICP override** — set `bf_email_management.legacy_owner_uid` on `ir.config_parameter` before upgrading to override the legacy-owner auto-resolution (defaults to the lowest active non-share user with `id > 1`).

### Changed

- **Crons refactored** — `_cron_sync_imap` and `_cron_imap_mirror` now iterate over `bf.email.account.search([('active', '=', True)])` and run each sync via `with_user(account.user_id)`, so new rows inherit `user_id` and `company_id` from the account owner.
- **Dashboard SQL** — every raw `cr.execute` in `bf_email_dashboard.py` now appends `AND be.user_id = %s` so direct-SQL aggregates respect per-user isolation (record rules don't fire on `cr.execute`).
- **`mail.notification` propagation** — read-state propagation no longer reads the legacy single IMAP user from ICP; it derives the recipient internal user from `res_partner_id` and only flips rows owned by that user.
- **`mail.message.action_download_eml`** — adds `('user_id', '=', self.env.uid)` to the bf.email mirror lookup to prevent cross-user raw-RFC2822 access via a shared chatter message.
- **Wizards** — `bf.email.browser` and `bf.email.imap.backfill` gain an `account_id` selector (default = current user's first active account; domain `[('user_id', '=', uid)]`). The IMAP browser RPC surface (`imap_browser_*`) accepts an optional `account_id` and validates ownership.

### Removed

- `res.config.settings` IMAP fields (`bf_email_imap_host`, `bf_email_imap_port`, `bf_email_imap_user`, `bf_email_imap_password`, `bf_email_imap_writeback_archive`, `bf_email_imap_archive_folder`, `bf_email_imap_batch_size`, `bf_email_auto_link_threshold_days`) and `action_bf_email_test_imap`. The functionality lives on `bf.email.account` now.
- Tenant-specific default rule `rule_internal_bluefox`. Users define their own internal-domain rules.

### Migration notes

The 18.0.4.0.0 migration:

1. Resolves the **legacy owner uid** (from `bf_email_management.legacy_owner_uid` ICP, or the lowest active non-share user id `> 1`, falling back to `SUPERUSER_ID`).
2. Adds `bf_email.user_id`, `bf_email.account_id`, and `bf_email_rule.user_id` columns via raw SQL in **pre-migrate** to satisfy the new `required=True` constraints during Odoo model setup.
3. Cleans up FK references that point to the legacy `group_email_user` / `group_email_manager` (`ir_model_access`, `res_groups_users_rel`, `rule_group_rel`, `res_groups_implied_rel`) so `unlink()` succeeds in post-migrate.
4. Drops the legacy `UNIQUE(message_id_header, company_id)` constraint so the new three-column constraint can take its place during the registry rebuild.
5. In **post-migrate**, creates a single `bf.email.account` row from the legacy ICP credentials (owned by the resolved owner), links the existing IMAP `bf.email` rows to it via `account_id`, deletes the legacy `bf_email.imap_*` ICP rows, and unlinks the legacy groups + the module category record.

## [18.0.3.8.0] — 2026-05-10

### Added
- **Préférences du Navigateur IMAP** — bouton engrenage à côté de la barre de recherche, ouvre un panneau avec 5 réglages persistés dans `localStorage` (clé `bf_email_browser_settings_v1`, schéma versionné) :
  - **Format de date** : relatif (« aujourd'hui 14:35 », défaut) vs absolu (« 2026-05-10 14:35 »).
  - **Affichage de l'expéditeur** : nom seul (défaut), adresse seule, ou « Nom &lt;adresse&gt; ».
  - **Messages par page** : 50 / 100 (défaut) / 200 / 500 — recharge le dossier courant à la modification.
  - **Densité d'affichage** : confortable (défaut) ou compacte (`table-sm`).
  - **Mettre les non-lus en gras** : on (défaut) / off.

### Notes
- Le panneau est purement client : aucun aller-retour serveur, aucune table Odoo. Multi-navigateur = pas synchronisé (volontaire — chaque poste règle son confort). Sync per-user via `res.users` viendra si le besoin se manifeste.

## [18.0.3.7.0] — 2026-05-10

### Added
- **Navigateur IMAP — round UX 2** : 10 améliorations façon Apple Mail / Thunderbird, un seul commit.
  - **Arbre de dossiers** dans la barre latérale : `Archives` se déplie en `2024 / 2025 / 2026` (parsed sur `/`). Toggle `▸ / ▾`, parents auto-dépliés au premier chargement.
  - **Compteurs non lus + total** par dossier : `imap_browser_get_folders` appelle `STATUS folder (MESSAGES UNSEEN)` après le `LIST`. Badge bleu quand non-lus > 0, gris muted sinon.
  - **Lignes en gras quand non lues** : `fetch_headers_bulk` récupère désormais les `FLAGS` IMAP en plus des en-têtes ; absence de `\Seen` → `fw-bold`.
  - **Nom d'expéditeur parsé** : `email.utils.parseaddr` côté serveur ; la colonne *Expéditeur* affiche « Blue Fox » au lieu de « Blue Fox &lt;notifications@github.com&gt; ». Adresse complète en tooltip.
  - **Dates relatives** style Apple Mail : `aujourd'hui 14:35` / `hier 09:12` / `lun. 14:35` / `5 mai` / `2024-12-05` selon l'ancienneté.
  - **Raccourcis clavier** via `useHotkey` (Odoo core) : `J/K` ou `↓/↑` naviguer · `R` répondre · `Shift+R` répondre à tous · `F` transférer · `E` Traité · `Suppr`/`Retour` Trash · `Y` router · `/` focus recherche · `Échap` effacer recherche.
  - **Recherche dans la page chargée** : `<input type="search">` au-dessus de la liste, filtre `subject` + `sender_name` + `from` côté client en temps réel.
  - **Bouton « Traité » par ligne** : icône `✓` à droite de chaque ligne. Pas besoin de cliquer la ligne avant — un seul clic ingère + archive + saut à la ligne suivante.
  - **Saut automatique vers le message suivant** après Traité / Supprimer / drag-and-drop. Plus de panneau d'aperçu vide en plein triage.
  - **Défilement infini** : disparition des boutons Précédent / Suivant, remplacés par un `IntersectionObserver` qui charge la page suivante quand on scrolle vers le bas (rootMargin 200 px). Les pages déjà chargées restent visibles.
  - **Drag-and-drop entre dossiers** : tirer une ligne sur un dossier dans la barre latérale = `imap_browser_move` côté serveur (COPY + EXPUNGE).

### Added (server)
- `bf_email_imap.fetch_headers_bulk` retourne désormais `{uid: (msg, seen)}` au lieu de `{uid: msg}`. Deux call sites mis à jour (`bf.email.imap_browser_get_messages` et `bf.email.browser.action_load_page`).
- `bf.email.imap_browser_reply_all(folder, uid)` pour le raccourci Shift+R, mirroir d'`imap_browser_reply`.
- `bf.email.imap_browser_move(folder, uid, dst_folder)` pour le drag-and-drop. Refuse cible vide ou égale à la source.

## [18.0.3.6.0] — 2026-05-10

### Changed
- **Navigateur IMAP : aperçu en iframe + actions complètes** — le corps des courriels est désormais rendu dans une `<iframe sandbox="allow-same-origin" srcdoc="…">` avec un mini HTML conteneur (Lexend / system fallback, marges 12 px, `img { max-width: 100% }`, `pre { white-space: pre-wrap }`, citations gris-bleu). Plus de fuite de CSS entre l'email et l'interface Odoo, plus de débordement horizontal sur les courriels avec tableaux 800 px de large.
- **Barre d'actions sous le sujet** : *Répondre* (auto-ingestion + composer pointé sur la ligne bf.email), *Transférer* (idem mode forward), *Traité* (auto-ingestion + `action_archive` qui COPY+EXPUNGE vers `Archives/{YYYY}`), *Router* (uniquement si pas encore ingéré), et *Supprimer* à droite (déplace vers `Trash` côté serveur IMAP via COPY+EXPUNGE, sans toucher à bf.email). Après *Traité* ou *Supprimer*, le message est retiré de la liste en mémoire.

### Added
- 4 nouvelles méthodes RPC sur `bf.email` consommées par le client OWL :
  - `imap_browser_reply(folder, uid)` — ingestion conditionnelle + `action_reply()`
  - `imap_browser_forward(folder, uid)` — ingestion conditionnelle + `action_forward()`
  - `imap_browser_mark_handled(folder, uid)` — ingestion conditionnelle + `action_archive()` (writeback bilatéral)
  - `imap_browser_move_to_trash(folder, uid)` — IMAP `COPY uid Trash` + `EXPUNGE` dans le dossier source

### Notes
- *Supprimer* refuse explicitement si le dossier source est déjà `Trash/*` — pas de suppression définitive depuis ce navigateur, passer par le webmail IMAP.
- L'iframe a `allow-same-origin` mais aucun `allow-scripts` : les scripts dans les emails sont neutralisés.

## [18.0.3.5.0] — 2026-05-10

### Changed
- **Navigateur IMAP refait en deux-panneaux façon Apple Mail / Thunderbird** — l'action passe d'une vue formulaire `bf.email.browser` à un client action OWL (`bf_email_browser`). Layout : barre latérale gauche (240 px) avec la liste des dossiers IMAP en LIST, panneau droit divisé verticalement (50/50) entre la liste des messages en haut et le corps en bas. Clic sur un dossier → charge la première page (newest-first, 100 messages). Clic sur un message → charge le corps via FETCH RFC822 et l'affiche dans le panneau bas avec les boutons *Ingérer* / *Ingérer + router*. Toute l'I/O IMAP passe par 5 nouvelles méthodes RPC `imap_browser_*` sur `bf.email` ; la TransientModel `bf.email.browser` reste comme action diagnostique non liée à un menu.
- Pagination réelle (Précédent / Suivant 100 messages) avec compteur « 1–100 / 7219 » dans l'en-tête de la liste.

### Notes
- L'action `action_bf_email_browser` est désormais `ir.actions.client` (tag `bf_email_browser`) — le menu pointe au même endroit, mais ouvre la vue OWL au lieu du formulaire transient.
- La version 18.0.3.4.0 ajoutait la TransientModel + son formulaire ; 18.0.3.5.0 garde cette base comme fallback et fait du OWL le chemin par défaut.

## [18.0.3.4.0] — 2026-05-10

### Added
- **Navigateur IMAP** — wizard `bf.email.browser` (menu : Courriels → Navigateur IMAP) qui ouvre n'importe quel dossier IMAP (Archives/2024, Trash, Junk, Drafts, Brouillons, Templates, Snoozed, …) en lecture seule, sans ingestion automatique. Affiche jusqu'à 500 messages par page (newest-first), avec un aperçu plein écran (sujet / expéditeur / corps HTML), une indication « Déjà ingéré » par ligne, et trois actions par row : *Aperçu*, *Ingérer* (crée la ligne `bf.email`), *Ingérer + router* (ouvre le wizard Reroute pré-rempli). Réutilise les helpers existants de `bf_email_imap` (`open_connection`, `select_folder`, `search_uids_in_range`, `fetch_rfc822`, `parse_rfc822`, `extract_body`) et l'ingestion de `bf.email._ingest_rfc822`.
- **`bf_email_imap.fetch_headers_bulk(conn, uids)`** — nouveau helper qui fait un seul `FETCH (BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT MESSAGE-ID)])` sur N UIDs et retourne `{uid: email.message.EmailMessage}`. Évite N round-trips IMAP pour peupler le tableau du navigateur.
- **« Deviner et importer »** — server action de masse sur la liste `bf.email` (Action → Deviner et importer). Pour chaque ligne IMAP-orpheline sélectionnée, exécute `bf.email.reroute._suggest_target_reference` *par ligne* (et non globalement) afin de pré-remplir une cible distincte par courriel quand le contact a exactement une tâche / un ticket ouvert. Affiche une liste éditable avec badge de confiance (élevée / aucune) que l'utilisateur peut corriger avant de confirmer. Une seule confirmation route N lignes vers N cibles indépendantes via `bf.email.reroute._reroute_one`, en propageant les flags `mark_replied` / `archive_after`.

### Notes
- Le navigateur n'écrit jamais côté serveur IMAP (toutes les sélections sont `readonly=True`). Aucun risque d'ingestion accidentelle de Trash / Junk : il faut un clic explicite par message.
- « Deviner et importer » et le wizard Reroute existant cohabitent : le Reroute classique reste utile quand toutes les lignes sélectionnées vont à la *même* cible. Le nouveau wizard est pour N→N indépendant.
- Aucune migration nécessaire — les deux nouveaux modèles sont des `TransientModel`. Les tables sont créées automatiquement à l'install / upgrade.

## [18.0.3.3.0] — 2026-05-10

### Fixed
- **Rule-driven auto-handle never archived on IMAP** — `_apply_rules` wrote `is_handled=True` directly via `rec.write(vals)` and never invoked `_imap_writeback_archive`. Rules like *"List-Unsubscribe → Marketing + Traité"* and *"Expéditeurs noreply → Notification + Traité"* therefore left every matching message in the IMAP INBOX while marking it Traité in Odoo. The 18.0.2.4.0 backfill caught the chatter/gateway race cohort but not this one — they were two distinct root causes. `_apply_rules` now collects records that transitioned to handled and calls `_imap_writeback_archive` on the batch (gated on the same ICP `bf_email.imap_writeback_archive`, exception caught + warned).

### Migration
- `migrations/18.0.3.3.0/post-migrate.py` — same 180-day handled-but-still-in-inbox replay as 18.0.2.4.0, in 50-row IMAP chunks. Catches up rows accumulated between the 2.4.0 deployment and the 3.3.0 fix.

## [18.0.3.2.0] — 2026-05-10

### Changed
- **Reuse `mail_composer_cc_bcc` for Cc / Bcc** — 18.0.3.0.0 introduced its own `bf_to_partner_ids` / `bf_cc_partner_ids` / `bf_bcc_partner_ids` fields with a parallel composer view, but BF prod already had `mail_composer_cc_bcc` (Camptocamp / OCA-style) installed since 2026-03 with `partner_cc_ids` / `partner_bcc_ids` always-visible on the composer. Result: when the BF Reply-All flag was on, the user saw two Cc fields and two Bcc fields stacked. The split fields and view override are now removed; the BF Reply-All dispatcher feeds the existing `mail_composer_cc_bcc` plumbing via `default_partner_cc_ids` in context. To make the context defaults survive the inherited `_compute_partner_cc_bcc_ids` recompute (which otherwise resets to the company default on every fresh wizard), this module now overrides that compute and honors the context defaults when present.
- **Manifest now hard-depends on `mail_composer_cc_bcc`** — previously bf_email_management worked standalone; now we rely on its fields, so it's listed in `depends`.

### Added
- **Settings page « Inbox unifiée »** — Settings → Inbox unifiée surfaces the IMAP credentials (host / port / user / password), the bilateral archive toggle + folder template, the IMAP batch size and the auto-link threshold. All four params previously required Technical → Parameters → System Parameters editing. A "Tester la connexion" button opens an IMAP4_SSL session with the saved credentials and reports the INBOX count + the list of folders detected (capped at 25). Menu shortcut: Courriels → Configuration → Paramètres (compte IMAP).

### Migration
- `migrations/18.0.3.2.0/post-migrate.py` drops the three legacy m2m tables (`bf_compose_to_partner_rel`, `bf_compose_cc_partner_rel`, `bf_compose_bcc_partner_rel`), the dangling `ir.model.fields` rows for the four dropped fields, and the orphan view `bf_email_management.bf_email_compose_message_wizard_form`. No persistent data — these were all transient wizard fields.

## [18.0.3.1.0] — 2026-05-09

### Changed
- **Calendar reminder popup re-shows on page load** — the OWL `calendarNotification` service replacement now calls `getNextCalendarNotif()` on `start()`, in addition to subscribing to the `calendar.alarm` bus channel. Previously, an alarm that fired while the tab was closed would silently disappear: bus.bus only re-emits when `_notify_next_alarm` is called server-side, never on client connect, so a refresh after a missed alarm dropped it. Now, on every page load, the service polls `/calendar/notify` to surface any pending alarm whose `notify_at > calendar_last_notif_ack`.
- **Snooze button labels shortened + non-breaking spaces** — Odoo's notification toast renders 7+ buttons in a narrow strip and was wrapping French labels mid-word (e.g. `"Demain 8 h"` → `"De\nma\nin\n8\nh"`, `"Détails"` → `"D\nét\nail\ns"`). New labels: `5 min` / `15 min` / `1 h` (with U+00A0 NBSP between the number and unit) / `Demain` / `Autre…` / `Ignorer` / `Ouvrir`. Behavior unchanged — only display strings.

## [18.0.3.0.0] — 2026-05-07

### Added
- **Composer enrichi À / C.c. / C.c.i.** — l'override `mail.compose.message` ajoute trois Many2many distincts (`bf_to_partner_ids`, `bf_cc_partner_ids`, `bf_bcc_partner_ids`) activés par le flag `bf_email_split_recipients`. Quand le composer est ouvert depuis l'inbox unifiée (`bf.email.action_reply`, `action_reply_all`, `action_forward`), les trois champs apparaissent à la place de la liste `partner_ids` monolithique. Les trois listes sont fusionnées dans `partner_ids` à l'envoi pour respecter le flux standard de notifications, et `email_to`/`email_cc` sont injectés dans `_prepare_mail_values_*` pour que les en-têtes To et Cc sortants reflètent la séparation. Les destinataires C.c.i. reçoivent le courriel via `partner_ids` mais n'apparaissent ni dans To ni dans Cc (style Gmail). Sur tout composer ouvert ailleurs dans Odoo, le flag reste `False` et le comportement standard est intact.
- **Bouton « Répondre à tous »** dans l'en-tête de la fiche `bf.email` pour les courriels entrants. Pré-remplit À avec l'expéditeur original et C.c. avec les autres destinataires du fil (To+Cc), en excluant l'utilisateur courant et les alias internes (`mail.bounce.alias`, `mail.catchall.alias`, `mail.default.from`, `bf_email.imap_user`).
- **Recherche unifiée dans le wizard de réacheminement** — `bf.email.reroute` passe désormais le contexte `bf_email_reroute_search=True` au champ `target_reference`. Les overrides `name_search` sur `project.task`, `account.move` et `res.partner` détectent ce flag pour :
  - accepter un entier brut (ex. `22299`) et résoudre à `id = 22299`,
  - accepter le format facture/écriture (`INV/2026/00017`) en correspondance exacte sur `name`,
  - retourner des libellés enrichis `#{id} — {display_name}` (et `… <email@…>` pour les contacts) afin que le menu déroulant affiche le nom complet.
- **Champ « Lien rapide »** dans le wizard. Accepte une URL Odoo (`https://.../all-tasks/22299`, `/odoo/project/N/22299`), un préfixe (`task:22299`, `ticket:42`, `partner:1234`, `invoice:NNN`), un entier brut, ou un nom de facture. Résout `target_reference` automatiquement via onchange.
- **Pré-remplissage `target_reference`** — quand toutes les rangées sélectionnées partagent un seul `partner_id`, le wizard cherche une seule tâche ouverte (`state in [01_in_progress, 02_changes_requested]`) ou un seul ticket helpdesk ouvert pour ce partenaire, et la pré-suggère.
- **Colonne « Réveil »** (optionnelle, masquée par défaut) dans la liste `bf.email` — affiche `snoozed_until` avec le widget `remaining_days` pour visualiser quand les courriels remis à plus tard reviennent.
- **Cron `_cron_auto_link_orphans`** (désactivé par défaut, intervalle 6 h) — auto-lie les rangées IMAP orphelines (`source='imap'`, `res_model=False`) à la seule tâche ou ticket ouvert du contact. Conservateur : un seul match exact, partenaire client ou fournisseur, fenêtre paramétrable via `bf_email.auto_link_threshold_days` (défaut 14 jours). Aucune publication sur le chatter — c'est un lien doux, le réacheminement reste à la discrétion de l'utilisateur.

### Notes
- Aucune migration nécessaire : les nouveaux Many2many sur `mail.compose.message` sont des champs de wizard transient (jamais persistés). Les nouveaux paramètres sont ajoutés via `noupdate="1"`.
- Le cron auto-link reste `active=False` pour un déploiement prudent. Activer manuellement via Settings → Technical → Scheduled Actions une fois validé en review.
- Le module ne dépend pas d'Helpdesk (`helpdesk_mgmt`) : la branche helpdesk dans le pré-remplissage et l'auto-link est gardée par `'helpdesk.ticket' in self.env`.

## [18.0.2.4.0] — 2026-05-06

### Fixed
- **IMAP writeback never archived gateway/chatter rows server-side** — when the chatter cron created the `bf.email` row before the IMAP cron saw the UID (a 5-minute race that played out for ~24% of inbound gateway rows), `_ingest_rfc822` skipped backfilling `imap_uid` because it only touched rows whose `source` was already `imap`. Without a UID, `_imap_writeback_archive` filtered those rows out and silently no-op'd. Two changes:
  - `_ingest_rfc822` now backfills `imap_uid`/`imap_folder`/`imap_in_inbox` on any existing row that lacks them, regardless of source.
  - `_imap_writeback_archive` falls back to `IMAP SEARCH HEADER Message-ID` against INBOX when the UID is missing or stale, so gateway/chatter rows still get archived even if they never picked up a UID via the cron path.

### Migration
- `migrations/18.0.2.4.0/post-migrate.py` — replays the IMAP writeback for `is_handled=True AND imap_in_inbox=True` rows from the last 180 days, in 50-row IMAP chunks. Catches up the historical backlog (~2.6k handled rows that never moved server-side).

## [18.0.2.1.0] — 2026-05-05

### Added
- **Téléchargement .eml** — bouton « Télécharger .eml » dans l'en-tête du formulaire `bf.email`, et entrée « Télécharger en .eml » dans le menu kebab de chaque message de chatter (visible aux utilisateurs internes, sur les messages de type `email`). Pour les rangées avec `raw_rfc822` (ingestion IMAP directe), les bytes RFC 2822 originaux sont servis tels quels — `Received:`, `DKIM-Signature:`, etc. sont préservés. Pour les rangées chatter/gateway, le `.eml` est reconstruit à partir de `mail.message` (From/To/Cc/Subject/Date/Message-ID/In-Reply-To, corps multipart text+HTML, pièces jointes).
- Nouvelle inheritance `mail.message` avec méthode `action_download_eml` qui délègue à un éventuel mirror `bf.email` (lookup par `Message-ID`) avant reconstruction.
- Helpers sur `bf.email` : `_build_eml_bytes`, `_build_eml_from_mail_message` (classe), `_build_eml_from_self`, `_eml_filename`, `_eml_slug`.
- Asset OWL `static/src/js/bf_email_chatter_action.js` enregistré dans le registry `mail.message/actions` (`sequence: 80`).

## [18.0.1.5.1] — 2026-04-28

### Fixed
- **Empty body on IMAP-orphan rows** — `body_html` was a related field on `mail.message.body`, which returned empty for IMAP-direct rows that have no linked `mail.message`. Converted to a stored compute that parses `raw_rfc822` for `source='imap'` rows and reads `mail.message.body` for chatter/gateway rows. Plain-text bodies are wrapped in `<pre>` for chatter-style rendering.
- **Internal Odoo wins on dedup** — the IMAP cron previously created orphan rows even when a `mail.message` with the same Message-ID already existed (because the chatter projection had run earlier and the IMAP UID was new). It now checks `mail.message` proactively and creates the row already linked to the chatter (annotated with IMAP UID for traceability) instead of as an orphan.
- **NUL byte stripping** — PostgreSQL `TEXT` columns reject `0x00` bytes; some clients embed them via inline images or quoted-printable artifacts. Bodies are now scrubbed before storage to prevent `A string literal cannot contain NUL` errors during compute persistence.

### Migration
- `migrations/18.0.1.5.1/post-migrate.py`:
  1. Retroactively promotes IMAP orphans whose Message-ID already exists in `mail.message` (link `mail_message_id`, copy `res_model`/`res_id`, switch `source` to `gateway`/`chatter`).
  2. Backfills `body_html` from `mail.message.body` for chatter/gateway rows (fast SQL path).
  3. Backfills `record_name` for newly-promoted rows.
  4. Recomputes `body_html` for remaining IMAP orphans by parsing `raw_rfc822`.

## [18.0.1.5.0] — 2026-04-28

### Added
- **Direct IMAP ingestion** — new cron `_cron_sync_imap` (5-minute interval) connects via IMAP4_SSL to a configured mailbox, polls `INBOX` and `Sent`, and creates `bf.email` rows with `source='imap'`. Per-folder UID watermarks (`bf_email.imap_last_uid_inbox`, `imap_last_uid_sent`).
- **Re-routing wizard** (`bf.email.reroute`) — single-record button on every IMAP-orphan row, plus list-view bulk server action. Posts the email to any `mail.thread` model (project task, helpdesk ticket, contact, lead, calendar event, invoice, sale order, etc.) via `record.message_post(...)`, preserving Message-ID, original date, author, and attachments.
- **Archives backfill wizard** (`bf.email.imap.backfill`) — one-shot scan of any IMAP folder (e.g. `Archives/2025`) with optional `SINCE`/`BEFORE` date filters. Idempotent — UNIQUE Message-ID constraint plus existence checks prevent duplicates on re-runs.
- **RFC 2822 thread tracking** — new `thread_root_id` field, indexed, computed from the `References` header (or `In-Reply-To` / `mail.message.parent_id` chain). Smart button "Conversation" on the form view filters `bf.email` by thread root.
- **Auto-replied** — when an outbound row is created with `in_reply_to` matching an inbound row's Message-ID, the inbound is flipped to `replied` automatically.
- **New fields on `bf.email`**: `imap_uid`, `imap_folder`, `raw_rfc822` (Binary attachment), `thread_root_id`, `thread_count` (compute).
- **`source` selection** extended with `imap`.
- **`in_reply_to`** is now indexed.
- **List view enhancements**: warning decoration on rows without a linked record, inline "Import to chatter" button, badges for `imap` source.
- **Search filters**: `À répondre`, `Sans réponse > 7 jours`, `Dernières 24h`, `Dernières 48h`, `Sans dossier (à router)`, `Avec dossier`, `IMAP orphelin`.
- **Group-by-thread** in search view.
- **`models/bf_email_imap.py`** — reusable RFC 2822 helpers (IMAP4_SSL connection, UID search, body extraction, attachment parsing, thread header parsing, NUL-byte scrubbing).

### Changed
- **Default action context** — `bf_email_action` (action 1785) no longer applies `search_default_filter_new=1`. Default view is now the unified inbox sorted by date desc, including read and replied (excludes archived only).
- **`_should_sync(msg)` extended** — no longer just dedup; now actively promotes existing IMAP-orphan rows when a chatter `mail.message` with the same Message-ID arrives, instead of skipping or creating a duplicate.

### Migration
- `migrations/18.0.1.5.0/post-migrate.py` — recursive CTE backfill of `thread_root_id` for existing rows by walking `mail.message.parent_id` chains. Seeds `thread_root_id` from `in_reply_to` or `message_id_header` for rows without a linked `mail.message`.

### Configuration (`ir.config_parameter`)
- `bf_email.imap_host`, `bf_email.imap_port` (default `993`), `bf_email.imap_user`, `bf_email.imap_password` — IMAP server credentials. Empty by default; cron skips silently when unset.
- `bf_email.imap_batch_size` (default `100`) — UIDs fetched per cron tick.
- `bf_email.imap_last_uid_inbox`, `bf_email.imap_last_uid_sent` — per-folder UID watermarks (managed automatically).

### Notes
- Container restart required after the upgrade — Odoo's registry signaling reloads model definitions but does NOT reload Python bytecode for already-running workers.
- Re-routing preserves the original Message-ID, so subsequent gateway projections of the same email won't duplicate the row (UNIQUE constraint enforces this).

## [18.0.1.4.1] — 2026-04-27

### Fixed
- **`_compute_category` AttributeError on tenants without `sale_team`/`purchase`** — `customer_rank`/`supplier_rank` are not always present on `res.partner`. Replaced direct attribute access with `getattr(partner, 'customer_rank', 0)`.
- **FK violation on deleted partners** — `mail.message.author_id` is a raw int FK that Odoo doesn't auto-null when a partner is deleted. Added `partner.exists()` check in `_prepare_email_vals` to prevent `bf_email_partner_id_fkey` errors.

### Migration
- `migrations/18.0.1.4.1/post-migrate.py` re-runs the 1.4.0 backfill so rows that failed under the earlier hardening get a second pass.

## [18.0.1.4.0] — 2026-04-27

### Fixed
- **Watermark uses `create_date`, not `mail.message.date`** — the previous filter `("date", ">", last_sync)` advanced past back-dated imports (manual scripts, forwarded threads with original `Date:` headers, cross-tenant imports), permanently hiding them. Caught when an inbound reply imported retroactively never appeared in the module. Now uses insertion time (`create_date`).

### Migration
- `migrations/18.0.1.4.0/post-migrate.py` — backfills missing rows by sweeping `mail.message` records that were skipped by the buggy watermark.

## [18.0.1.3.x and earlier]

Initial chatter projection (`mail.message` → `bf.email`), enrichment fields, OWL dashboard, scheduled-drafts cross-record list, security groups, multi-company isolation. See git history for details.
