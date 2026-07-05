# Sécurité — `bf_securetransfer`

## Signaler une vulnérabilité

Merci de signaler toute vulnérabilité de manière responsable à
**security@bluefoxconsultant.com**, sans divulgation publique préalable.

## Périmètre

Le module expose des **routes publiques non authentifiées** :

- `GET /secrets` — page d'envoi brandée (Host → marque)
- `POST /secrets/api/create` + `/secrets/api/<upload_token>/…` — API JSON
  d'upload (presign, multipart, remove, finalize)
- `GET /s/<token>` — page de téléchargement ; `POST /s/<token>/unlock` — mot de
  passe ; `GET /s/<token>/dl/<file>` — 302 vers un GET présigné ;
  `POST /s/<token>/report` — signalement d'abus

Aucun contenu de fichier ne transite par Odoo : les octets vont directement du
navigateur au bucket S3 (URLs présignées) et en reviennent par redirection 302.

## Modèle de menaces et mitigations

### Capacités et jetons

- **Deux jetons distincts** par transfert (défense en profondeur) :
  `upload_token` (phase brouillon seulement, **révoqué à la finalisation**) et
  `token` (lien `/s/`, **inerte avant l'activation**). UUID v4, comparaison en
  **temps constant** (`hmac.compare_digest`), 404 **uniformes** (un jeton
  inconnu, expiré ou en brouillon renvoie la même page neutre, sans
  métadonnée).
- Les jetons sont stockés en clair mais **réservés aux gestionnaires**
  (`groups=manager`) ; la révélation d'un lien passe par un assistant dédié et
  est **inscrite au journal**.
- **ACL** : le public n'a **aucun** accès modèle — tout passe par `sudo()`
  derrière la vérification de jeton dans les contrôleurs.

### Téléversement direct S3

- **URLs présignées à portée minimale** : PUT simple avec `Content-Length`
  signé (TTL 900 s), parts multipart signées **par lots ≤ 20 à la demande**
  (anti presign-farming, TTL 3600 s). La clé S3 est **opaque, générée serveur**
  (`<préfixe-tenant>/<uuid>/<uuid>` — aucun nom de fichier ni PII dans la clé ;
  le préfixe par tenant isole les instances sur un bucket partagé).
- **CORS restrictif** : origines explicites (jamais `*`), méthode PUT
  seulement, `ExposeHeaders: ETag`.
- **Complete multipart côté serveur** : la liste des parts est reconstruite via
  `ListParts` — jamais de confiance aux ETags fournis par le client.

### Intégrité des fichiers

- À la finalisation : `HEAD` de chaque objet (existence + **taille exacte**) et
  **épinglage de l'ETag**.
- Avant **chaque** téléchargement : re-`HEAD` + comparaison d'ETag. Un re-PUT
  malveillant après finalisation (avec un presign encore valide) est donc
  bloqué : téléchargement refusé + événement `integrity_mismatch` journalisé.
- Téléchargement par 302 vers un GET présigné (TTL 300 s) avec
  `ResponseContentDisposition: attachment` + `ResponseContentType:
  application/octet-stream` **forcés** — jamais de rendu inline : neutralise le
  XSS stocké via fichier HTML/SVG.
- Pas de SHA-256 côté client au MVP (WebCrypto ne streame pas — impossible sur
  20 Go) ; champ `checksum` réservé. Hook antivirus prévu (champ `scanned` —
  la route de téléchargement n'autorise déjà que `none`/`clean`).

### Anti-abus (page publique)

- **Courriel expéditeur requis** (pas de captcha au MVP).
- **Honeypot** `website_url` : rempli → faux succès silencieux, rien n'est
  créé.
- **Rate-limits burst** en mémoire par IP (création 10/h, API upload 120/min,
  échecs de jeton 20/5 min, mot de passe 8/15 min par IP+transfert, abus
  5/jour). *Limite connue : état par worker — un déploiement multi-worker
  multiplie le plafond effectif ; durcissement fort = limitation en amont
  (NPM/WAF).*
- **Quotas quotidiens en base** (fiables multi-worker, sous verrou
  `FOR UPDATE`) : 25 transferts et 10 Go déclarés par IP/jour, 5 transferts
  par courriel expéditeur/jour.
- **Liste noire d'extensions** (exécutables, scripts…), extension obligatoire,
  nom de fichier assaini (chemins, caractères de contrôle, RTL-override,
  ≤ 255) ; mimetype déterminé **côté serveur**.
- **Kill-switch** : `public_upload_enabled` (page d'envoi) et état `suspended`
  par transfert (abus signalé).

### Mot de passe

- Haché **pbkdf2_sha512** (passlib, dépendance cœur d'Odoo) ; le hash est
  réservé au groupe système. Le mot de passe **ne figure jamais** dans les
  courriels — canal séparé assumé.
- Gate serveur (session) ; échecs journalisés (`password_fail`) et plafonnés.

### Journal d'accès (Loi 25)

- **Append-only, chaîné par hachage** (patron `bf_sign_log`) : chaque entrée
  référence l'empreinte de la précédente ; `write()`/`unlink()` bloqués au
  niveau ORM, ACL lecture seule y compris pour les gestionnaires. Toute
  altération rompt la chaîne (`verify_chain()`).
- Le journal note le **nom du fichier au moment de l'événement** : la preuve
  survit à la purge des objets.
- Fidélité assumée : l'événement `download` atteste un **téléchargement
  initié** (302 émis), pas la réception complète des octets.
- Cycle de vie : la purge supprime les objets S3 mais **conserve métadonnées et
  journal** (jamais de `unlink`, règle maison) ; seul le GC hebdomadaire
  supprime les enregistrements après `log_retention_days` (365 j).

### Pages publiques et en-têtes

- Pages QWeb **autonomes** (sans layout portal/website) ; en-têtes de sécurité
  sur chaque réponse : **CSP** (avec le host S3 ajouté au `connect-src` de la
  page d'envoi — seul ajout), `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- Le host de marque n'expose que le produit : `/web/login`, `/web/database`,
  `/odoo`, `/xmlrpc` redirigés 302 vers l'instance principale (config NPM).
- Contenu utilisateur (message, noms de fichiers) rendu **échappé uniquement**
  (`t-esc`) ; réponses d'erreur JSON génériques, sans détail interne.

### Secrets et rayon d'explosion

- Clés S3 **hors base** (env / `odoo.conf`) — un dump de base ou un refresh
  staging n'emporte jamais les clés de production.
- **Isolation par préfixe de clé (`s3_key_prefix`)** : sur un bucket partagé,
  chaque instance n'écrit, ne purge et ne balaie que sous son propre préfixe.
  Object lock OFF (sinon la purge est impossible). Le refresh staging purge les
  enregistrements hérités et repointe le préfixe pour que le staging ne puisse
  pas agir sur les objets prod. Pour une isolation plus forte, un bucket +
  une clé scopée par tenant restent possibles.

## Non-garanties

- La chaîne de hachage du journal est **sans secret** : elle détecte une
  altération mais ne résiste pas à un acteur ayant l'écriture en base (qui
  pourrait recalculer la chaîne). Pas d'ancrage externe (RFC 3161) au MVP.
- Si votre fournisseur S3 est de propriété **américaine** (p. ex. IDrive E2),
  les données peuvent résider au Canada (région vérifiée par sonde) mais le
  CLOUD Act s'applique — « hébergé au Canada » est défendable, « à l'abri de
  tout accès étranger » ne l'est pas (réserve à documenter ; chiffrement
  applicatif = Phase 3).
- Le lien `/s/<token>` est une **capacité** : quiconque le détient (transfert
  de courriel, épaule, historique) accède aux fichiers, sous réserve du mot de
  passe. Le mot de passe optionnel est la mitigation offerte.
- Chiffrement en transit (TLS) et au repos côté fournisseur ; **pas de
  chiffrement zéro-connaissance** au MVP.
