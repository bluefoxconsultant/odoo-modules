# Blue Fox — Signature électronique (`bf_sign`)

Signature électronique **native Odoo 18 Community** (sans dépendance au module
`sign` d'Odoo Enterprise), instrumentée pour être **opposable en droit
québécois**. Signature électronique simple (SES) prouvable et inaltérable, avec
**sceau numérique PAdES** optionnel (document « signé / non altéré » dans un
lecteur PDF, à la DocuSeal).

- **Version** : `18.0.3.12.0` — voir [`CHANGELOG.md`](CHANGELOG.md).
- **Licence** : LGPL-3.
- **Modèle de menace & non-garanties** : voir [`SECURITY.md`](SECURITY.md).

---

## Aperçu

`bf_sign` permet de faire signer un PDF **à même Odoo** par un ou plusieurs
signataires, via un **lien public personnel tokenisé** (aucun compte Odoo
requis), puis de produire un **document scellé + certificat de complétion** avec
une **piste de vérification inaltérable**. L'objectif est qu'une signature
« tienne en cour » : consentement explicite, lien signataire↔document, intégrité
vérifiable et présomption d'intégrité renversant le fardeau de la preuve.

Au-delà du téléversement manuel d'un PDF, n'importe quel autre module (Ventes,
Achats…) peut **envoyer son propre document pour signature** grâce au mixin
`bf.sign.mixin` ; le document signé est ensuite **reversé dans le fil du record
source**.

## Cadre juridique (Québec / Canada)

- La signature électronique est valide en principe : **C.c.Q. art. 2827** (la
  signature manifeste le consentement, le manuscrit n'est pas requis) et la *Loi
  concernant le cadre juridique des technologies de l'information* (**LCCJTI**),
  principe d'équivalence fonctionnelle.
- Trois conditions d'opposabilité : **consentement**, **lien
  signataire↔document** (LCCJTI art. 39), **intégrité vérifiable** (LCCJTI
  art. 5-6).
- **Présomption d'intégrité** (**C.c.Q. art. 2840**) : c'est la partie qui
  conteste qui doit prouver l'atteinte — fardeau inversé.
- Jurisprudence : *Bennington Financial Corp. c. Dufour* (Cour du Québec) — une
  signature DocuSign a été reconnue sur la base d'un certificat de complétion,
  d'une piste de vérification et du contexte entourant la signature.

> **Portée.** Ce module produit une **signature électronique simple (SES)**, pas
> une signature avancée (AES) ni qualifiée (QES) au sens eIDAS. Il n'y a pas de
> régime QES au Canada et les actes notariés restent hors périmètre. Le sceau
> PAdES renforce l'**inaltérabilité** du document final mais reste un cachet
> d'organisation auto-signé (voir « Sceau numérique » plus bas). Le champ
> `signature_method` prépare un palier AES via LibreSign sans changer la
> structure.

---

## Fonctionnalités

### Signature
- **Multi-signataires** en parallèle ou en séquentiel (relance automatique du
  suivant en mode séquentiel).
- **Placement visuel des pavés** (signature / paraphe / date / texte) par
  glisser-déposer sur le document (widget OWL + PDF.js), coordonnées en fractions
  de page indépendantes de la résolution.
- **Champs remplissables par le signataire** (texte / date) avec mode de
  remplissage `signer` / `fixed` / `auto`.
- **Modèles de pavés réutilisables** (`bf.sign.field.template`) mémorisant la
  disposition par **rang de signataire**.
- **Page de signature publique** brandée et responsive : aperçu du document rendu
  avec **marqueurs de placement numérotés** (ordre de lecture), miroir en direct
  de la signature/des champs, consentement explicite horodaté, **refus** possible.

### Identité du signataire
- **Lien personnel tokenisé** par signataire (UUID, comparaison en temps
  constant), envoyé par courriel — preuve = contrôle de la boîte de réception.
- **Vérification par code (OTP) optionnelle** : le signataire saisit un code à 6
  chiffres envoyé à son courriel **avant** de consulter et signer (preuve du
  contrôle de la boîte *au moment de la signature*). Activable globalement et/ou
  par demande. Code à durée limitée, plafonné en tentatives.
- **Le lien de signature n'est jamais exposé au demandeur** : `access_token` et
  `signing_url` sont réservés aux gestionnaires ; un gestionnaire peut révéler le
  lien via une action **« Copier le lien »** qui est **inscrite dans la piste de
  vérification**.

### Intégrité & preuve
- **Sceau numérique PAdES** (pyHanko) *(optionnel)* : signature cryptographique
  invisible « organisation » sur le document final → un lecteur PDF (Adobe…)
  affiche « signé / non modifié ».
- **Empreintes SHA-256** du document original, du contenu estampé (horodaté) et
  du bundle scellé.
- **Piste de vérification append-only chaînée** (hash-chain) : horodatage serveur
  UTC, IP, agent utilisateur, méthode d'identité (`email_link_token` /
  `email_otp` / `internal_user`), empreintes avant/après — `write`/`unlink`
  bloqués au niveau ORM.
- **Verrouillage structurel** : destinataires et pavés gelés une fois la demande
  envoyée (modifiable seulement en « brouillon »).
- **Horodatage de confiance RFC 3161** *(optionnel)* : jeton TSA sur le contenu
  signé, **affiché dans le certificat**, preuve de date indépendante.
- **Vérification d'intégrité en un clic** : recalcul de la chaîne du journal, de
  l'empreinte du document scellé, du sceau PAdES et du jeton d'horodatage.

### Intégration & expérience
- **Envoi pour signature depuis d'autres modules** via `bf.sign.mixin` (Ventes,
  Achats… — voir « Intégration »), avec **reversement du document signé** dans le
  fil du record source.
- **Certificat de complétion** PDF brandé fusionné au document.
- **Courriels brandés** (invitation, complétion avec pièces jointes, refus, code
  OTP) via `bf_onboarding_base` (couleurs/logo de la société) + `bf_lexend`.
- **Expiration automatique** des liens (cron quotidien) et **assistant
  d'intégration** (`bf_onboarding_base`).

---

## Modèle de données

| Modèle | Rôle |
|---|---|
| `bf.sign.request` | La demande de signature : document, paramètres, signataires, pavés, empreintes, pièces signées, lien `res_model`/`res_id` vers le record source. |
| `bf.sign.signer` | Un signataire : courriel, `access_token` (manager-only), état, image de signature/paraphe, champs OTP. |
| `bf.sign.field` | Un pavé placé (type, page, position en fractions, mode de remplissage). |
| `bf.sign.field.template` (+ `.line`) | Disposition de pavés réutilisable, par rang de signataire. |
| `bf.sign.log` | Journal append-only chaîné (immuable). |
| `bf.sign.seal` (AbstractModel) | Couche de scellement PAdES (génération du certificat, `seal_pdf`, `verify_pdf`, gestion de la clé Fernet). |
| `bf.sign.mixin` (AbstractModel) | « Envoyer pour signature » sur n'importe quel modèle. |

---

## Intégration : envoyer un document d'un autre module pour signature

Le module expose une fabrique et un mixin pour brancher la signature sur
n'importe quel modèle Odoo possédant un rapport PDF.

**Fabrique** — `bf.sign.request.create_from_record(record, report_ref=…,
document_file=…, signers=…, field_template=…, send=False)` : rend le record en
PDF (via `ir.actions.report._render_qweb_pdf`) ou accepte des octets PDF, crée la
demande **liée** (`res_model`/`res_id`), ajoute les signataires, applique au
besoin un modèle de pavés, et envoie si demandé.

**Mixin** — `bf.sign.mixin` ajoute à un modèle :
- le bouton **« Envoyer pour signature »** (`action_send_for_signature`) — crée
  une demande brouillon liée et l'ouvre pour placer les pavés puis envoyer ;
- un **bouton statistique** « Signatures » (`action_view_sign_requests`) ;
- des points de personnalisation : `_sign_report_ref()`, `_sign_default_signers()`
  (par défaut le `partner_id` du record), `_sign_document_filename()`.

**Reversement** — à la signature complète, `_notify_source_signed()` copie le PDF
signé + le certificat sur le record source et publie une note au fil (aucun
changement d'état).

**Modules-pont fournis** (à installer selon les besoins, dépendances propres) :

| Module | Cible | Rapport |
|---|---|---|
| `bf_sign_sale` | `sale.order` (devis / commandes) | `sale.action_report_saleorder` |
| `bf_sign_purchase` | `purchase.order` | `purchase.action_report_purchase_order` |
| `bf_sign_account` | `account.move` (factures clients / fournisseurs) | `account.account_invoices` |
| `bf_sign_privacy` | `privacy.consent` (consentements Loi 25) | `privacy_consent.action_report_consent_certificate` |

Brancher un nouveau modèle se réduit à : `_inherit = ["<model>",
"bf.sign.mixin"]`, surcharger `_sign_report_ref()` (retourner l'xmlid du rapport
PDF), et ajouter les boutons `action_send_for_signature` /
`action_view_sign_requests` en vue.

---

## Dépendances

**Modules Odoo** : `mail`, `portal`, `bf_lexend`, `bf_onboarding_base`.

**Bibliothèques Python**
- *Requises* (livrées avec l'image Odoo) : `Pillow` (PIL), `reportlab`, `PyPDF2`.
- *Sceau PAdES (optionnel)* : `cryptography`, `pyHanko` (+ `asn1crypto`,
  `pyhanko-certvalidator`). Sans elles, le sceau reste inactif ; le reste
  fonctionne.
- *RFC 3161 (optionnel)* : `requests`, `asn1crypto` (importés paresseusement,
  seulement si activé).

---

## Configuration

*Paramètres → Signature électronique* :

- **Clé de chiffrement (scellement)** — clé Fernet protégeant le certificat de
  scellement. **Générer** une clé (stockée en base) ou en **importer** une. Une
  clé définie dans `odoo.conf` / l'environnement a toujours **priorité** (voir
  « Sceau numérique » et `SECURITY.md` pour le compromis base de données).
- **Sceau numérique (PAdES)** — bouton **« Générer le certificat de scellement »**
  (auto-signé « <Société> — Sceau de signature »). Le sceau devient actif dès
  qu'un certificat existe ; la case sert d'interrupteur d'arrêt.
- **Vérification par code (OTP)** — activer par défaut, sur chaque nouvelle
  demande, la vérification par code envoyé au courriel du signataire. Réglable
  demande par demande.
- **Échéance par défaut** (jours) avant expiration d'un lien.
- **Limites de taille** : plafonds sur les images de signature (Ko) et le document
  téléversé (Mo).
- **Texte de consentement par défaut**.
- **Horodatage RFC 3161** : activation + **URL de la TSA**. Désactivé par défaut
  (ajoute un appel réseau synchrone à la finalisation).

### Choix d'une autorité d'horodatage (TSA)

- **Notarius** (Québec) — aligné sur le cadre C.c.Q./LCCJTI.
- **DigiCert** (`http://timestamp.digicert.com`), **Sectigo**
  (`http://timestamp.sectigo.com`) — autorités commerciales reconnues.
- `https://freetsa.org/tsr` — gratuit, **pour les essais seulement** (sa racine
  doit être distribuée pour vérifier les jetons).

### Sceau numérique : mise en place

1. **Clé Fernet** : la définir dans `odoo.conf` (`bf_sign_fernet_key = …`) ou
   l'environnement (`BF_SIGN_FERNET_KEY`) — recommandé, durci ; **ou** la générer
   depuis Paramètres (stockée en base, libre-service). La clé chiffre le
   certificat de scellement dans `ir.config_parameter`.
2. **Certificat** : cliquer « Générer le certificat de scellement ». Tout document
   finalisé est ensuite scellé automatiquement.
3. Le certificat étant **auto-signé**, Adobe affiche « valide mais non approuvé
   par une AC ». Pour la coche verte, ancrer sur une PKI reconnue (palier futur).

> Changer une clé Fernet déjà active alors qu'un certificat existe est **refusé**
> (le certificat deviendrait illisible) ; supprimer d'abord le certificat.

---

## Fonctionnement (cycle de vie)

1. **Création** d'une demande (PDF téléversé **ou** envoyé depuis un autre module),
   ajout des signataires, placement des pavés.
2. **Envoi** : validation du PDF, calcul de `hash_original`, échéance, envoi des
   liens personnels (tous, ou le premier en mode séquentiel).
3. **(Optionnel) Vérification OTP** : le signataire saisit le code reçu par
   courriel avant d'accéder au document.
4. **Signature** : le signataire consulte le document, consent, signe — ou
   **refuse**. Les images sont validées (PNG, taille, intégrité) avant acceptation.
5. **Finalisation** (dernier signataire) : estampage, horodatage RFC 3161
   optionnel, rendu du certificat, fusion, **sceau PAdES** optionnel, empreintes,
   journalisation, courriel de confirmation (document signé + certificat), et
   **reversement** au record source le cas échéant.

---

## Modèle de sécurité (résumé)

- **Accès par jeton** : `access_token` UUID par signataire, comparaison en temps
  constant (`hmac.compare_digest`), **réservé aux gestionnaires** (le demandeur ne
  peut pas s'auto-signer) ; révélation par un gestionnaire **journalisée**.
- **OTP courriel** (optionnel) : preuve du contrôle de la boîte au moment de la
  signature ; expiration + plafond de tentatives ; routes `/document` et `/submit`
  bloquées tant que non vérifié.
- **Anti-force brute** : limitation par IP des échecs de jeton (en mémoire, par
  worker — voir `SECURITY.md`).
- **Intégrité** : empreintes SHA-256 + **journal append-only chaîné** ; sceau
  PAdES + ancrage **RFC 3161** (TSA indépendante) pour la preuve hors plateforme.
- **Inaltérabilité** : un document signé ne peut être supprimé ; les entrées de
  journal ne peuvent être ni modifiées ni supprimées.
- **Secrets** : certificat/clé de scellement chiffrés par Fernet ; la clé Fernet
  peut rester hors base (env/`odoo.conf`) — compromis documenté dans `SECURITY.md`.

Voir **[`SECURITY.md`](SECURITY.md)** pour le modèle de menace détaillé, le
périmètre des routes publiques et les non-garanties.

---

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier [`LICENSE`](LICENSE).
