# Transfert sécurisé — Secure Transfer (`bf_securetransfer`)

Transfert de fichiers sécurisé « WeTransfer maison », natif Odoo 18 Community :
téléversement **direct navigateur → S3** (IDrive E2, région `ca-east-1`) par
URLs présignées (PUT simple + multipart), **liens tokenisés** avec expiration,
mot de passe et OTP optionnels, **journal d'accès inaltérable** (chaîne de
hachage, pièce Loi 25), **purge automatique**, **multi-marques** résolues par le
nom d'hôte, **pages de dépôt personnelles** (`/to/<slug>`), **listes
d'autorisation anti-piggyback** et **suspension automatique sur signalement
d'abus**.

- **Version** : `18.0.1.6.0`.
- **Licence** : LGPL-3.
- **Modèle de menaces & non-garanties** : voir [`SECURITY.md`](SECURITY.md).
- **Multi-paliers** : le système multi-marques permet un palier gratuit limité
  (marque par défaut, mention « Propulsé par » optionnelle) et un palier payant
  en marque blanche sur domaine dédié (limites plus élevées). Angle
  différenciateur = **conformité Loi 25 / résidence des données au Canada**.

---

## Fonctionnalités

**Transfert**

- Téléversement **direct navigateur → S3** par URLs présignées : Odoo signe,
  ne proxy jamais les octets. PUT simple (≤ 64 Mo) et **multipart/resumable**
  pour les fichiers de plusieurs Go (parts de 16 Mo, presigns par lots,
  3 parts concurrentes, reprise in-session via `ListParts`).
- **Intégrité** : à la finalisation, chaque objet est vérifié côté serveur
  (existence + taille exacte) et son **ETag est épinglé**, puis **revérifié
  avant chaque téléchargement** — bloque l'attaque « re-PUT d'un maliciel avec
  un presign encore valide ».
- **Téléchargement** = redirection 302 vers un GET présigné (TTL 300 s),
  `attachment` + `octet-stream` forcés (jamais de rendu inline, tue le XSS
  stocké).
- **Deux modes d'envoi, deux onglets** : **Fichiers** (défaut) ou **Message
  seul** (note sécurisée sans fichier — p. ex. transmettre un mot de passe).
  En mode **Message seul**, le contenu n'apparaît **jamais en clair dans le
  courriel** : la notification ne porte que le lien, et le message ne se lit
  que sur la page sécurisée (à durée limitée, journalisée).
- **Message sécurisé à code (OTP destinataire)** : depuis le backend, un envoi
  peut **retenir le contenu derrière un code à usage unique** livré par
  courriel ou par SMS — le message ne s'affiche qu'après preuve d'identité du
  destinataire. Confirmation d'envoi par code côté expéditeur également
  disponible.
- **Ordre des champs pensé anti-friction** : courriel et destinataires **au-
  dessus** de la zone de dépôt ; le courriel expéditeur est **optionnel au
  dépôt, requis à l'envoi** (on peut déposer un fichier avant de saisir son
  courriel sans message d'erreur).

**Marques & pages**

- **Multi-marques** (`secure.transfer.brand`) résolues par le nom d'hôte :
  domaine, visuels, limites, mention « Propulsé par », listes d'autorisation,
  facturation. Alignées **par défaut sur le branding maison**
  (`appointment_brand_*` puis `report_brand_*`, en `getattr` — aucune dépendance
  dure à bf_branding / bf_onboarding_base).
- **Pages de dépôt personnelles** `/to/<slug>` : page « Dropbox » où les
  visiteurs ne peuvent envoyer qu'à **un seul destinataire fixe** (le
  propriétaire de la page). Destinataire **forcé côté serveur** au create ET au
  finalize — impossible de rediriger un dépôt ailleurs.
- **Thème clair/sombre automatique** (`prefers-color-scheme`) ; la marque
  conserve ses couleurs.
- **Tableau de bord** (vues graph + pivot) : volume et téléchargements par
  marque et par état.

**Sécurité & anti-abus**

- **Listes d'autorisation anti-piggyback**, côté expéditeur ET destinataire,
  par marque **ou** par défaut au niveau du tenant (Paramètres) : adresse
  complète, `@domaine` ou domaine nu. Empêche qu'un tiers utilise une instance
  qui n'est pas la sienne, ou relaie des fichiers vers des adresses arbitraires.
- **Deux flux OTP optionnels** (réglages tenant, OFF par défaut) : **OTP
  expéditeur** (confirme un code avant l'envoi — anti-usurpation) et **OTP
  destinataire** (code avant téléchargement — gate Loi 25). Codes 6 chiffres,
  hashés, TTL 15 min.
- **Mot de passe** optionnel (passlib pbkdf2_sha512), **jamais** transmis dans
  le courriel de lien.
- **Destruction après lecture** (`burn_after_download`) et **notification au
  téléchargement** (courriel à l'expéditeur au 1er dl) — par marque.
- **Signalement d'abus → suspension automatique** : le lien s'éteint
  immédiatement (`state = suspended`) et le reste jusqu'à intervention d'un
  administrateur ; un courriel détaillé part vers `abuse_email` (à défaut, le
  courriel de la société), un avis neutre vers les destinataires, une
  activité vers les gestionnaires. Réactivation = `action_reactivate`.
- **Anti-abus de base** : courriel expéditeur requis à l'envoi, honeypot,
  rate-limiting par IP (en mémoire), **quotas quotidiens DB** (transferts/IP,
  octets/IP, transferts/expéditeur — verrous consultatifs anti-TOCTOU),
  liste noire d'extensions, sanitation des noms de fichiers, 404 uniformes sur
  fuzzing de jeton.
- **En-têtes** durcis + **CSP** stricte (connect-src limité à l'endpoint S3 sur
  la page d'envoi seulement), `X-Frame-Options: DENY`, nosniff, Referrer-Policy.

**Courriels & Loi 25**

- Courriels **brandés** (lien aux destinataires, accusé à l'expéditeur),
  visuels partagés avec les pages via `brand._visuals()`.
- **Langue selon le contact** : si l'adresse correspond à une fiche
  `res.partner`, le courriel part dans `partner.lang` ; sinon la locale du
  visiteur. Envoi individualisé par destinataire.
- **Journal d'accès inaltérable** (`secure.transfer.access.log`, chaîne de
  hachage clonée de `bf_sign_log`) : chaque évènement (créé, finalisé, envoyé,
  vue, mot de passe OK/échec, OTP OK/échec, téléchargement, échéance dépassée,
  intégrité, signalement, suspension, purge…) passe par un point de contrôle
  unique. Vérifiable par `verify_chain()`. Pièce Loi 25 conservée même après
  purge des objets.

---

## Aperçu du flux

Un visiteur ouvre la page publique d'envoi (`/secrets`, ou `/to/<slug>` pour un
dépôt personnel), choisit **Fichiers** ou **Message seul**, remplit son courriel
et (hors dépôt perso) les destinataires, dépose ses fichiers, et obtient un lien
`https://<domaine de marque>/s/<jeton>`. Les octets vont **directement du
navigateur au bucket S3**. À la finalisation, chaque fichier est vérifié
(existence, taille, **épinglage ETag**), les courriels brandés partent (lien aux
destinataires dans leur langue, accusé à l'expéditeur — **jamais le mot de
passe**), et le transfert vit jusqu'à son échéance, où la purge S3 supprime les
objets **en conservant métadonnées et journal**.

Cycle de vie : `draft` → (upload par fichier) → `active` → `expired` (date /
budget de téléchargements / burn) → purge S3 (`deleted`, méta + journal gardés)
→ GC dur après `log_retention_days`. États additionnels : `cancelled`
(brouillons moissonnés) et `suspended` (kill-switch d'abus).

---

## Architecture

### Modèles

| Modèle | Rôle |
|---|---|
| `secure.transfer` (`mail.thread`) | Le transfert : jetons (`upload_token` éphémère + `token` de partage), état, expéditeur/destinataires, message, mot de passe, OTP, échéance, compteurs, `burn_after_download`/`notify_on_download`. |
| `secure.transfer.file` | Un fichier : nom sanitisé, taille (`Float` — jamais `Integer`, débordement > 2,1 Go), extension (deny-list), `s3_key` **opaque** (uuid, aucune PII), ETag épinglé, état, champs multipart (`s3_upload_id`, `part_size`, `parts_total`). |
| `secure.transfer.brand` | Marque : `domain`, `slug` + `fixed_recipient` (page de dépôt), visuels, limites, `tier`, `sender_allowlist`/`recipient_allowlist`, `powered_by`, facturation. |
| `secure.transfer.access.log` | Journal append-only hash-chaîné (Loi 25). Écriture bloquée hors point de contrôle ; suppression uniquement par le GC hebdo. |
| `res.config.settings` | Réglages tenant (params `ir.config_parameter`). |
| `reveal.link.wizard` | Assistant « Révéler le lien » (jetons stockés en clair, `groups=manager`). |

### Arborescence

```
bf_securetransfer/
├── __manifest__.py            # depends [web, mail, portal] ; external_dependencies boto3
├── hooks.py                   # post_init_hook : traductions courriel en_CA (jsonb)
├── README.md / SECURITY.md
├── controllers/main.py        # pages publiques (/secrets, /to/<slug>, /s/<token>…)
├── controllers/upload_api.py  # API JSON d'upload (create/presign/multipart/finalize/confirm)
├── models/s3.py               # SEUL fichier boto3 (lazy) : client, presign, head, multipart, CORS
├── models/secure_transfer.py  / _file.py / _brand.py / _access_log.py / res_config_settings.py
├── wizards/reveal_link_wizard.py
├── security/  data/  views/   # ACL+groupes ; séquence, marque défaut, crons, 3 templates ; vues backend + QWeb publiques
├── static/src/js/st_upload.js # JS pur : drag-drop, XHR PUT progress, chunking, resume, onglets, drop mode
├── static/src/{js/st_download.js, css/st_public.css}
├── migrations/18.0.1.1.0/post-migrate.py
├── i18n/ (pot + fr_CA + en_CA)
└── tests/ (lifecycle, access_log, host_resolution)   # 63 tests, S3 entièrement mocké
```

### Routes

| Route | Type | Rôle |
|---|---|---|
| `GET /secrets` | http | Page d'envoi brandée (Host → marque). |
| `GET /to/<slug>` | http | Page de dépôt personnelle (destinataire fixe). |
| `POST /secrets/api/create` | json | Brouillon → `{upload_token, limits}`. Courriel optionnel ; `drop_slug` pour un dépôt perso. |
| `POST /secrets/api/<ut>/presign` | json | Enregistre un fichier → PUT simple ou plan multipart. |
| `POST …/multipart/{initiate,sign,complete,abort,status}` | json | Cycle multipart (complete reconstruit depuis `ListParts`, jamais les ETags client). |
| `POST …/remove` | json | Retire un fichier pré-finalize. |
| `POST …/finalize` | json | Vérifie, active, envoie les courriels → `{share_url}`. |
| `POST …/confirm` et `…/confirm/resend` | json | Confirmation OTP expéditeur. |
| `GET /s/<token>` | http | Page de téléchargement / gate mot de passe / gate OTP / page neutre. |
| `POST /s/<token>/unlock` | http | Soumission du mot de passe (flag de session). |
| `POST /s/<token>/otp-request` et `/otp-verify` | http | Gate OTP destinataire. |
| `GET /s/<token>/dl/<file_id>` | http | Revérif ETag → 302 vers GET présigné. |
| `POST /s/<token>/report` | http | Signalement d'abus → suspension auto + courriels + activité. |

---

## Dépendances

- **Modules Odoo** : `web`, `mail`, `portal` (pas `website` : pages publiques
  autonomes, le routeur website ne doit jamais détourner un Host de marque).
- **Python** : `boto3` + `botocore` (épinglés dans les Dockerfiles des tenants —
  nouvelle couche pip finale, ne pas toucher la couche pyHanko). L'import est
  paresseux : sans boto3, le module s'installe mais toute opération S3 lève une
  erreur explicite.

---

## Mise en route (opérateur)

### 1. Clés d'accès S3 — `odoo.conf` ou environnement, jamais en base

Les clés voyagent **hors base de données** (un dump ou un refresh staging
emporterait les clés de production). Par ordre de priorité :

```ini
# variables d'environnement (prioritaires)
BF_SECURETRANSFER_S3_ACCESS_KEY=…
BF_SECURETRANSFER_S3_SECRET_KEY=…

# ou bloc odoo.conf
bf_securetransfer_s3_access_key = …
bf_securetransfer_s3_secret_key = …
```

Le bucket peut être **partagé entre plusieurs instances** ou dédié. Chaque
instance est isolée par son **préfixe de clé** `s3_key_prefix` (p. ex.
`transfers-prod`, `transfers-staging`) : c'est ce préfixe — et non le nom du
bucket — qui garantit qu'une purge ou un balayage d'orphelins d'une instance ne
touche jamais les objets d'une autre. **Rendre `s3_key_prefix` unique par
instance.** **Verrou d'objets (object lock) désactivé** — sinon la purge est
impossible. Après avoir cloné une base de production vers un environnement de
test, videz les tables `secure_transfer_*` (héritées du dump) et repointez
`s3_key_prefix` + `public_base_url` sur les valeurs de test, afin que le test
n'agisse jamais sur les objets de production.

### 2. Paramètres (Paramètres → Transfert sécurisé)

Non-secrets, stockés en `ir.config_parameter` (préfixe `bf_securetransfer.`) :

| Paramètre | Défaut | Rôle |
|---|---|---|
| `s3_endpoint_url`, `s3_region`, `s3_bucket` | — / `ca-east-1` / — | Point d'accès IDrive E2 |
| `s3_key_prefix` | — | Préfixe d'isolation par instance (unique !) |
| `s3_path_style` | `1` | Adressage path-style |
| `cors_origins` | — | Origines autorisées à téléverser (jamais `*`) |
| `public_base_url` | — | URL publique quand la marque n'a pas de domaine (à définir explicitement plutôt que de compter sur `web.base.url`) |
| `public_upload_enabled` | `1` | Interrupteur de la page d'envoi (les liens de téléchargement restent servis) |
| `presign_put_ttl` / `presign_part_ttl` / `presign_get_ttl` | 900 / 3600 / 300 s | Durées de vie des URLs présignées |
| `multipart_threshold_mb` / `part_size_mb` / `mpu_sign_batch_max` | 64 / 16 / 20 | Bascule multipart, taille de part, lot de presigns |
| `default_free_max_transfer_mb` / `default_paid_max_transfer_mb` | 2048 / 20480 | Plafonds par palier |
| `default_max_files` | 25 | Fichiers par transfert |
| `default_free_max_retention_days` / `default_paid_max_retention_days` | 7 / 90 | Rétention par palier |
| `draft_ttl_hours` | 24 | Moisson des brouillons abandonnés |
| `log_retention_days` | 365 | Rétention du journal après purge |
| `rate_create_per_hour`, `quota_daily_transfers_per_ip`, `quota_daily_bytes_per_ip_mb`, `quota_daily_transfers_per_sender` | 10 / 25 / 10240 / 5 | Anti-abus |
| `default_sender_allowlist` / `default_recipient_allowlist` | — | Listes d'autorisation par défaut du tenant (une marque peut surcharger) |
| `require_sender_otp` / `require_recipient_otp` | `0` / `0` | Active les gates OTP expéditeur / destinataire |
| `abuse_email` | — (courriel société) | Destinataire des avis d'abus |

### 3. Action « Configurer le bucket S3 »

Bouton dans Paramètres → Transfert sécurisé, **idempotent**, à relancer après
tout changement d'origines CORS :

- applique la politique **CORS** : origines explicites du paramètre
  `cors_origins` **plus** l'union des domaines de marques actives, méthode
  **PUT seulement**, `ExposeHeaders: ETag` (**obligatoire** — sans lui le
  multipart échoue silencieusement côté navigateur), `MaxAge 3600` ;
- tente les règles de cycle de vie (`AbortIncompleteMultipartUpload` 2 j +
  `Expiration` 45 j) — filet derrière la purge ; si IDrive E2 refuse, l'échec
  est consigné et les crons restent le mécanisme primaire ;
- exécute les **sondes** : `GetBucketLocation == ca-east-1` (preuve de
  résidence), object lock OFF, aller-retour put/head/get/delete,
  `Content-Length` signé appliqué, `DeleteObjects` par lot, cycle multipart
  complet. Le rapport s'affiche à l'écran.

### 4. CORS requis (rappel)

Le téléversement direct exige que **chaque origine publique** (page d'envoi)
figure dans `cors_origins` ou parmi les domaines de marques actives :
`https://secret.example.com`, l'origine staging pour la QA, et chaque futur
domaine de marque. Les téléchargements sont des navigations 302 → pas de CORS.

### 5. Reverse proxy (host public)

Placez chaque domaine public (p. ex. `secret.example.com`) derrière un reverse
proxy qui transmet à l'instance Odoo. Points importants de la configuration :

- `client_max_body_size 16m` — seul du JSON transite par Odoo, les octets vont
  direct au bucket ;
- location `/websocket` → port 8072 (miroir du host Odoo principal) ;
- **redirection 302** de `/web/login`, `/web/database`, `/odoo`, `/xmlrpc`
  vers l'instance principale — le host de marque n'expose que le produit ;
- **⚠️ durcissement obligatoire** : le proxy DOIT **écraser** `X-Forwarded-Host`
  (`$host`) et `X-Real-IP`/`X-Forwarded-For` (`$remote_addr`), jamais relayer la
  valeur client — sinon un visiteur usurpe son IP (contourne les rate-limits) et
  sélectionne une marque payante (limites élevées + courriels sous la marque
  d'un client). Même faiblesse héritée de bf_sign/bf_policy : le contrôle est au
  proxy, pas dans le code ;
- `X-Content-Type-Options: nosniff` + `Referrer-Policy`.

### 6. Marques

Configuration → Marques. La marque **Défaut** (sans domaine) sert tout hôte
inconnu ; ses visuels retombent sur le branding de la société. Une marque
payante : domaine nu (`secret.client.com`), logo/favicon/couleurs, palier
`paid`, limites propres (0 = défaut de la configuration), `powered_by` décoché le
cas échéant, `sender_allowlist`/`recipient_allowlist` pour verrouiller l'usage.

### 6b. Page de dépôt personnelle (`/to/<slug>`)

Sur la fiche marque, renseigner **Identifiant de page (slug)** (p. ex.
`depot`) et **Destinataire unique** (l'adresse qui recevra tout) — un nom
d'affichage optionnel. La marque devient une page de dépôt servie à
`/to/<slug>` : le champ destinataire est masqué et **forcé côté serveur**. Idéal
pour un lien « Envoyez-moi un fichier » (signature courriel, site). Rien à
configurer côté proxy si la page vit sous un domaine déjà servi (p. ex.
`https://exemple.com/to/depot`).

### 7. Onboarding d'un domaine de marque payant

1. **DNS du client** : `CNAME secrets.client.com → <domaine de l'instance>`,
   **DNS-only**. Vérifier : `getent hosts secrets.client.com`.
2. **Reverse proxy + certificat TLS** pour le nouveau domaine, avec le même
   durcissement d'en-têtes qu'à l'étape 5.
3. **Fiche marque** : domaine nu, palier **Payant**, visuels, « Propulsé par »
   décoché, limites élevées, `sender_allowlist` (p. ex. `@client.com`),
   `partner_id`, puis bouton **« Configurer le domaine (CORS) »**.
4. Surveiller le certificat du nouveau domaine.

### 8. Facturation du palier payant

Chaque marque payante porte les champs `billing_active` / `billing_ref` /
`price_year`. La facturation elle-même relève de votre outillage : un simple
registre de coûts avec refacturation à la demande, ou une facturation
**récurrente automatique** via `sale.subscription` (Enterprise) ou l'OCA
`contract`.

---

## Exploitation

- **Crons** : purge quotidienne 03:15 (expirés → suppression S3 par lots,
  métadonnées + journal conservés), GC horaire des brouillons abandonnés
  (abort multipart + suppression des objets), GC hebdomadaire des journaux
  hors rétention (seul chemin qui supprime des entrées de journal).
- **Échecs de purge** : compteur par transfert ; ≥ 5 échecs → activité admin.
  Endpoint S3 injoignable : le cron abandonne proprement et rattrape au run
  suivant.
- **Backups** : les buckets sont **exclus par design** (contenu éphémère — les
  sauvegarder contredirait la promesse de rétention). Consigné « no backup
  expected — by design » dans audit-backup-coverage.
- **Surveillance** : suivez le certificat TLS de chaque domaine public
  (renouvellement automatique recommandé).
- **Journal d'accès** : menu Journal d'accès — pièce Loi 25 ; l'intégrité de la
  chaîne se vérifie par `verify_chain()`.

## Tests

`63 tests` (`tests/test_lifecycle.py`, `test_access_log.py`,
`test_host_resolution.py`). **Toute** interaction S3 est mockée sur
`odoo.addons.bf_securetransfer.models.s3` : la suite tourne sans boto3 et sans
endpoint joignable. Lancer sur staging :

```
docker exec odoo-staging odoo -d staging -u bf_securetransfer \
    --test-enable --test-tags /bf_securetransfer --stop-after-init
```

## Déploiement

Installez / mettez à jour via votre procédure habituelle de déploiement Odoo :

```bash
odoo -d <database> -u bf_securetransfer --stop-after-init
```

La migration de `sender_email` vers *nullable* est appliquée automatiquement par
Odoo au `-u`.

---

## Feuille de route

**Phase 2 — livrée** : burn-after-download, notify-on-download, domaines perso
payants (CORS auto, runbook), tableau de bord, câblage facturation, OTP
expéditeur + destinataire, listes d'autorisation, pages de dépôt perso, mode
message seul, thème clair/sombre, langue courriel selon contact.

**Phase 3 — à venir** : ClamAV (champ `scanned` déjà livré, la route dl le
respecte), ZIP « tout télécharger » (exclu au MVP : proxy multi-Go), chiffrement
applicatif zéro-connaissance (clés S3 opaques prêtes ; incompatible ClamAV —
décision de positionnement), UI de reprise multipart cross-session, facturation
récurrente automatique.

**Réserve Loi 25** (à documenter dans l'EFVP produit) : IDrive est un processeur
**américain** (CLOUD Act). « Hébergé au Canada » est défendable ; « à l'abri de
tout accès étranger » ne l'est pas avant la Phase 3 (chiffrement zéro-
connaissance).

---

## Journal des versions

| Version | Faits saillants |
|---|---|
| `18.0.1.6.0` | Mode **Message seul** : le corps n'est **plus jamais inclus en clair** dans le courriel de notification — celle-ci ne porte que le lien, et le message se lit uniquement sur la page sécurisée (comportement aligné sur les envois à code). |
| `18.0.1.3.0`–`1.5.0` | **Message sécurisé à code destinataire** (OTP livré par courriel ou SMS) + **assistant d'envoi backend** ; confirmation d'envoi par code côté expéditeur ; **pages de dépôt personnelles** auto-provisionnées à la création d'un utilisateur interne ; publication d'une marque de dépôt par son seul **slug** ; durcissement de l'échappement `LIKE` sur la résolution d'hôte. _(Publication de rattrapage : versions intermédiaires regroupées.)_ |
| `18.0.1.2.1` | Correctif : les listes d'autorisation par défaut (`res.config.settings`) passent de `Text` à `Char` — un champ `Text` sur les paramètres faisait planter toute la page Paramètres (`_get_classified_fields`). Séparateur = virgules. |
| `18.0.1.2.0` | Pages de dépôt perso `/to/<slug>` (destinataire forcé) ; onglets Fichiers/Message seul ; courriel expéditeur optionnel au dépôt / requis à l'envoi ; correctif d'ordre des champs. |
| `18.0.1.1.0` | Langue des courriels selon le contact Odoo (`partner.lang`) ; traductions en_CA rendues durables par hook de migration. |
| `18.0.1.0.x` | Phase 2 : burn-after-download, notify-on-download, domaines perso payants, tableau de bord, facturation, OTP expéditeur/destinataire, listes d'autorisation anti-piggyback, suspension auto sur abus + avis courriel. |
| `18.0.1.0.0` | MVP : upload direct S3 (simple + multipart), liens tokenisés, expiration/mot de passe, journal Loi 25 hash-chaîné, multi-marques, purge/crons. |

## Licence

Distribué sous licence **LGPL-3**.
