# Journal des modifications — `bf_sign`

Le versionnage suit la convention Odoo `18.0.MAJOR.MINOR.PATCH`.

## 18.0.3.11.0 — Téléverser une image de signature/paraphe

- **Troisième mode « Téléverser »** sur les pavés de signature et de paraphe, en
  plus de « Dessiner » et « Saisir » : le signataire peut choisir un fichier
  **PNG ou JPG** (p. ex. une signature numérisée). L'image est ajustée et centrée
  dans la zone, puis traitée comme les autres modes.
- **Aucun changement au pipeline ni au format de stockage** : l'image téléversée
  est dessinée sur le canevas et réencodée en PNG (`canvas.toDataURL`), donc elle
  passe par les mêmes validations (PNG, taille max), la même apposition et la même
  piste de vérification. Un JPG est converti en PNG automatiquement, côté client.

## 18.0.3.10.0 — Paraphe au clavier + valeurs tirées du signataire

- **Paraphe saisissable au clavier.** Le pavé « Votre paraphe » offre maintenant
  le même choix **Dessiner / Saisir** que la signature : on peut taper ses
  initiales (avec un style manuscrit/cursif/élégant) au lieu de devoir les
  dessiner, ce qui était malcommode au trackpad.
- **Valeurs prédéterminées à partir du nom du signataire.** En mode « Saisir »,
  le champ du paraphe est pré-rempli avec les initiales déduites du nom du
  signataire (« Marie Tremblay » → « MT »), et le nom tapé de la signature
  reste pré-rempli avec le nom complet. Les deux demeurent modifiables.
- Aucun changement au pipeline d'apposition ni à la piste de vérification : un
  paraphe tapé produit la même image PNG qu'un paraphe dessiné.

## 18.0.3.8.3 — Logo sur fond foncé dans les en-têtes

- Les en-têtes foncés (courriels brandés + pages publiques de signature) utilisent
  le **logo sur fond foncé** de la société (`report_brand_logo`, nouveau champ
  `bluefox_branding`) lorsqu'il est défini — typiquement la version blanche du logo
  — sinon le logo standard. Évite un logo foncé invisible sur la bande foncée.
  (Les 3 gabarits courriel `noupdate` sont recréés via migration pour appliquer
  le changement.)

## 18.0.3.8.1 — Société par défaut = société principale du créateur

- La demande de signature prend par défaut la **société principale** du créateur
  (au lieu de la société active du sélecteur multi-société), pour que le document
  soit toujours brandé (couleurs + logo) par l'organisation primaire même si une
  autre société est sélectionnée. Le champ reste modifiable en brouillon.

## 18.0.3.8.0 — Durcissement (audit pré-publication)

### Sécurité
- **Le jeton de signature ne transite plus par un message persistant** :
  l'invitation est envoyée en courriel autonome (sans lien document,
  auto-supprimé), de sorte qu'un utilisateur de signature ne peut plus récupérer
  le jeton d'un signataire depuis le corps d'un `mail.message` et signer à sa
  place. Restaure la garantie « pas de signature pour autrui » de la 18.0.3.4.0.
- **Règles d'enregistrement** sur signataires / pavés / journal : un utilisateur
  ne voit que ceux des demandes qu'il peut voir (plus de lecture des signataires,
  pavés et pistes de vérification d'autres créateurs ou sociétés).
- **Reversement au record source restreint** : à la finalisation, le document
  signé n'est reversé que si le créateur de la demande a réellement l'accès en
  écriture au record source (plus d'écriture `sudo` vers un `res_model` / `res_id`
  arbitraire).
- **Plafond de renvois OTP** (anti-bombardement de courriels) en plus du délai de
  30 s entre envois.

## 18.0.3.7.0 — Raffinements d'expérience

### Courriels
- **Titre de l'en-tête à droite du logo** (et non en dessous), aligné sur les
  autres courriels Blue Fox — invitation, complétion, refus et code OTP.

### Sécurité — révélation du lien
- **« Copier le lien » en deux temps** : la révélation d'un lien de signataire
  affiche d'abord un **avertissement** ; le lien n'est exposé — et la révélation
  inscrite dans la piste de vérification — **qu'après confirmation** explicite du
  gestionnaire (annuler ne révèle ni ne journalise rien).

### Signature
- **Signature tapée** en option sur la page de signature : le signataire peut
  **saisir son nom** (plusieurs styles) au lieu de le dessiner — le tracé reste
  l'option par défaut.

## 18.0.3.6.0 — Vérification par code (OTP) au moment de la signature

- **OTP courriel optionnel** (désactivé par défaut, activable globalement ou par
  demande) : le signataire saisit un code à 6 chiffres envoyé à son courriel
  **avant** de consulter et signer — preuve du contrôle de la boîte au moment de
  la signature. Code à durée de vie limitée, plafond de tentatives, routes
  `/document` et `/submit` bloquées tant que non vérifié. La méthode d'identité
  consignée devient `email_otp`.

## 18.0.3.5.0 — Envoi pour signature depuis d'autres modules

- **Mixin `bf.sign.mixin`** : bouton « Envoyer pour signature » + bouton
  statistique sur n'importe quel modèle, avec points de personnalisation
  (rapport, signataires, nom de fichier).
- **Fabrique `bf.sign.request.create_from_record`** : rend un record en PDF et
  crée une demande **liée** (`res_model` / `res_id`).
- **Reversement au record source** : à la signature complète, le document signé +
  le certificat sont copiés sur le record source et une note est publiée au fil
  (aucun changement d'état).
- **Modules-pont** : `bf_sign_sale` (devis / commandes) et `bf_sign_purchase`
  (bons de commande).

## 18.0.3.4.0 — Intégrité du lien de signataire

- **Le lien / jeton de signature n'est plus exposé au demandeur** : `access_token`
  et `signing_url` réservés aux gestionnaires — un utilisateur ne peut plus copier
  le lien d'un signataire et signer à sa place. L'invitation reste envoyée
  normalement (rendu sous `sudo`).
- **Révélation « bris de glace »** par un gestionnaire, **inscrite dans la piste
  de vérification** (événement `link_revealed`).

## 18.0.3.3.0 — Clé de chiffrement par l'interface & corrections

### Configuration
- **Clé Fernet en libre-service** : un administrateur peut **générer ou importer**
  la clé de chiffrement du certificat de scellement depuis *Paramètres* (stockée
  en base) ; une clé définie dans `odoo.conf` / l'environnement garde la priorité.
  Compromis documenté dans `SECURITY.md`.

### Courriels
- **Titre d'action** ajouté à l'en-tête des courriels (invitation / complétion /
  refus).

### Performance (widget de placement)
- **Rastérisation du PDF découplée du rechargement des données** + cache des
  pages : changer de type de pavé / enregistrer / appliquer un modèle ne re-rend
  plus tout le document.

### Page de signature publique
- **Correctif d'affichage du document** : Odoo livrant pdf.js en build **ESM**,
  son chargement en script classique échouait silencieusement → chargement via
  `import()` dynamique.

## 18.0.3.2.1 — Correctif de plantage OWL

- Correction d'un plantage du widget de placement (`ctx.String is not a
  function`) : `String(...)` n'est pas exposé dans le contexte des gabarits OWL.

## 18.0.3.2.0 — Marqueurs de placement côté signataire & verrouillage structurel

### Expérience de signature
- **Aperçu rendu du document** sur la page de signature (PDF.js → image par page)
  remplaçant l'`<iframe>` brut, avec **marqueurs de placement numérotés** : chaque
  pavé du signataire (signature, paraphe, texte, date) apparaît à sa position
  exacte sur le document, avec un **identifiant clair** (badge numéroté en ordre
  de lecture : page, puis haut→bas, gauche→droite).
- **Référence croisée** : les en-têtes des cartes « Votre signature / paraphe »
  et chaque champ à remplir portent le même numéro que le marqueur correspondant.
  Toucher un marqueur amène au champ/à la carte associé(e).
- **Miroir en direct** : la signature/le paraphe dessiné(e) et les valeurs
  texte/date saisies s'affichent dans les marqueurs au fil de la saisie (le
  marqueur passe au vert une fois rempli). Repli `<noscript>`/erreur vers un lien
  d'ouverture du PDF.

### Intégrité — verrouillage structurel
- **Destinataires et pavés gelés hors brouillon** : une fois la demande envoyée
  (ou signée), il n'est plus possible d'ajouter, modifier, déplacer ou retirer un
  **signataire** ou un **pavé** — appliqué au niveau du modèle
  (`create`/`write`/`unlink`) sur `bf.sign.signer` et `bf.sign.field`, avec une
  *allowlist* des champs que le flux de signature doit encore écrire
  (`filled_value`, images, consentement, état…). Échappatoire : « Remettre en
  brouillon ». Reflété dans le formulaire (lecture seule + bandeau) et le widget
  de disposition (placement désactivé hors brouillon).

## 18.0.3.1.0 — Correctifs du widget & modèles de pavés

- **Affichage du document de fond corrigé** dans le widget de placement (rendu
  hors-écran → image, plus de problème de synchronisation du canvas) et
  compression verticale corrigée.
- **Modèles de pavés réutilisables** (`bf.sign.field.template`) mémorisant la
  disposition **par rang de signataire** ; barre « Modèle » (appliquer /
  enregistrer) dans le widget.

## 18.0.3.0.0 — Sceau numérique PAdES

- **Sceau numérique** (pyHanko) : signature cryptographique invisible
  « organisation » sur le document final → un lecteur PDF (Adobe…) affiche
  « signé / non modifié » (type DocuSeal). Certificat X.509 auto-signé généré
  depuis les réglages, **chiffré par Fernet** dans `ir.config_parameter` (clé hors
  base via `odoo.conf` / environnement). Vérification d'intégrité étendue au sceau.

## 18.0.2.1.0 — Durcissement & finition du palier 1

### Sécurité
- **Validation des entrées** : les images de signature/paraphe sont validées
  (format PNG, taille plafonnée, intégrité via Pillow) **avant** que le
  signataire ne soit marqué signé, et le document téléversé est validé (PDF,
  taille, non chiffré, lisible) à l'envoi. Plafonds configurables
  (`bf_sign.max_signature_kb`, `bf_sign.max_document_mb`).
- **Garde anti-double-finalisation** : verrou de ligne (`SELECT … FOR UPDATE`) +
  relecture de l'état en tête de `_finalize`, pour sérialiser deux soumissions
  « dernier signataire » concurrentes (pas de pièces jointes ni de courriel en
  double).

### Intégrité & preuve
- **Réancrage RFC 3161** : le jeton d'horodatage couvre désormais le **contenu
  signé** (nouvelle empreinte `hash_stamped`) et est obtenu **avant** le rendu du
  certificat, de sorte que le certificat **affiche réellement** l'horodatage et
  l'heure attestée (`tsa_gentime`). Délai d'attente TSA ramené à 10 s.
- **Vérification d'intégrité en un clic** (`action_verify_integrity`) : recalcul
  de la chaîne du journal, de l'empreinte du document scellé et concordance du
  jeton RFC 3161 ; résultat affiché et consigné au chatter.

### Fonctionnalités
- **Flux de refus** : route publique `/sign/<id>/<token>/refuse`, bouton et motif
  sur la page de signature, page de confirmation, courriel d'avis au demandeur.

### UX
- **Widget de placement** plus robuste : erreurs PDF.js surfacées, bouton
  « Recharger », garde empêchant le placement tant que le formulaire a des
  modifications non enregistrées (les pavés étant écrits immédiatement).

### Publication
- `external_dependencies` Python déclarées au manifeste (`PIL`, `reportlab`,
  `PyPDF2`).
- Description du manifeste corrigée (multi-signataires).
- Suite de tests (`tests/`) couvrant cycle de vie, validation, signature
  parallèle/séquentielle, idempotence de finalisation, immuabilité du journal,
  refus, expiration et vérification d'intégrité.
- Ajout de `README.md`, `CHANGELOG.md`, `SECURITY.md`.

## 18.0.2.0.x — Multi-signataires & placement

- Multi-signataires (parallèle / séquentiel) via `bf.sign.signer`.
- Placement visuel des pavés (`bf.sign.field`) par glisser-déposer (widget OWL +
  PDF.js) et moteur d'estampage (reportlab + PyPDF2).
- Certificat de complétion brandé, empreintes SHA-256, piste append-only
  chaînée, horodatage RFC 3161 optionnel.

## 18.0.1.0.0 — Palier 1 initial (SES)

- Modèles `bf.sign.request` / `bf.sign.log`, contrôleur public tokenisé,
  signature dessinée, certificat QWeb, journal immuable.
