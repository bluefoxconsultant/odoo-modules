# Changelog

All notable changes to `bf_email_management` are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This module follows Odoo's `MAJOR.MINOR.PATCH` convention prefixed with the Odoo series (`18.0.X.Y.Z`).

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
- **Barre d'actions sous le sujet** : *Répondre* (auto-ingestion + composer pointé sur la ligne bf.email), *Transférer* (idem mode forward), *Traité* (auto-ingestion + `action_archive` qui COPY+EXPUNGE vers `Archives/{YYYY}`), *Router* (uniquement si pas encore ingéré), et *Supprimer* à droite (déplace vers `Trash` côté Migadu via COPY+EXPUNGE, sans toucher à bf.email). Après *Traité* ou *Supprimer*, le message est retiré de la liste en mémoire.

### Added
- 4 nouvelles méthodes RPC sur `bf.email` consommées par le client OWL :
  - `imap_browser_reply(folder, uid)` — ingestion conditionnelle + `action_reply()`
  - `imap_browser_forward(folder, uid)` — ingestion conditionnelle + `action_forward()`
  - `imap_browser_mark_handled(folder, uid)` — ingestion conditionnelle + `action_archive()` (writeback bilatéral)
  - `imap_browser_move_to_trash(folder, uid)` — IMAP `COPY uid Trash` + `EXPUNGE` dans le dossier source

### Notes
- *Supprimer* refuse explicitement si le dossier source est déjà `Trash/*` — pas de suppression définitive depuis ce navigateur, passer par Migadu webmail.
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
- Le navigateur IMAP n'écrit jamais côté Migadu (toutes les sélections sont `readonly=True`). Aucun risque d'ingestion accidentelle de Trash / Junk : il faut un clic explicite par message.
- « Deviner et importer » et le wizard Reroute existant cohabitent : le Reroute classique reste utile quand toutes les lignes sélectionnées vont à la *même* cible. Le nouveau wizard est pour N→N indépendant.
- Aucune migration nécessaire — les deux nouveaux modèles sont des `TransientModel`. Les tables sont créées automatiquement à l'install / upgrade.

## [18.0.3.3.0] — 2026-05-10

### Fixed
- **Rule-driven auto-handle never archived on IMAP** — `_apply_rules` wrote `is_handled=True` directly via `rec.write(vals)` and never invoked `_imap_writeback_archive`. Rules like *"List-Unsubscribe → Marketing + Traité"* and *"Expéditeurs noreply → Notification + Traité"* therefore left every matching message in Migadu INBOX while marking it Traité in Odoo. The 18.0.2.4.0 backfill caught the chatter/gateway race cohort but not this one — they were two distinct root causes. `_apply_rules` now collects records that transitioned to handled and calls `_imap_writeback_archive` on the batch (gated on the same ICP `bf_email.imap_writeback_archive`, exception caught + warned).

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
