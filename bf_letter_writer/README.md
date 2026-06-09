# Letter Writer (`bf_letter_writer`)

Rédaction de lettres officielles brandées dans Odoo 18 — en-tête verrouillé, fusion
de champs, modèles réutilisables et blocs de texte.

## Aperçu

`bf_letter_writer` ajoute une application **Lettres** à Odoo pour produire des
lettres officielles dont l'en-tête (logo, couleurs, signataire, pied de page) est
**piloté par la société** et **verrouillé** : l'auteur ne contrôle que le corps du
texte, ce qui garantit le respect des règles de marque. Le module est
**multi-société / marque blanche** — chaque société émet ses lettres avec sa
propre identité visuelle.

## Fonctionnalités

### En-tête brandé (marque blanche) — 5 modes
Piloté par `res.company` ; chaque société émet ses lettres avec sa propre
identité. Le « chrome » est verrouillé — l'utilisateur n'édite que le corps,
l'appel et la salutation finale.

- **Bannière foncée** *(générée)* — en-tête sombre avec logo, couleurs de
  marque (`report_brand_primary` / `report_brand_dark` via `bf_lexend`),
  adresse, mention d'en-tête et pied de page.
- **Classique sobre** *(générée)* — variante claire avec filet.
- **Image téléversée (PNG/JPG)** — l'image d'en-tête de la société sert de
  fond pleine page ; le corps est décalé pour la dégager.
- **PDF téléversé (superposition)** — le corps est *estampé* sur chaque page
  du PDF d'en-tête de la société (via PyPDF2). Qualité vectorielle.
- **Sans en-tête (papier pré-imprimé)** — aucun chrome ; le corps est décalé
  d'une marge configurable pour s'imprimer proprement sur du papier à
  en-tête déjà imprimé.

Les modes *image*, *PDF* et *pré-imprimé* utilisent les marges configurables
`letter_body_top_margin` / `letter_body_bottom_margin` de la société.

### Modèles de lettres
- Modèles réutilisables (`letter.template`) avec objet et corps.
- Champs de fusion : jetons `{{ object.champ }}` (style « publipostage Word ») et
  syntaxe QWeb `<t t-out="object.champ"/>` pour les cas avancés.
- Légende des champs de fusion intégrée à l'éditeur de modèle.
- Blocs de texte suggérés rattachés au modèle.

### Fusion de champs (publipostage)
- Application d'un modèle sur une lettre : le corps est rendu avec les valeurs du
  destinataire.
- **Fusion en lot** : un modèle, plusieurs destinataires → une lettre par
  destinataire.
- Action sur la liste des contacts : « Créer des lettres » à partir d'une
  sélection.
- Détection des champs de fusion non remplis (avertissement non bloquant).

### Blocs de texte (quicktext)
- Bibliothèque de blocs réutilisables (`letter.quicktext`), classés par catégorie,
  avec raccourci.
- Insertion dans le corps via un sélecteur (au début ou à la fin).
- Les blocs peuvent eux-mêmes contenir des champs de fusion.
- Trois blocs de départ fournis.

### Génération et envoi
- PDF brandé natif (QWeb), format US Letter.
- Aperçu PDF en un clic.
- Envoi par courriel avec le PDF en pièce jointe, dans une enveloppe courriel
  brandée.
- Bouton d'impression natif Odoo (rapport lié au modèle).

### Cycle de vie
- États : **Brouillon → Finalisée → Envoyée**.
- Numérotation automatique `LET-AAAA-NNN`.
- Référence destinataire (nom + adresse) figée à la finalisation.
- Suivi (chatter) et activités.
- **Archivage** des lettres (champ `active` + filtre « Archivées »).

### Confort d'utilisation
- **Titre automatique** : « Lettre à [destinataire] » dès qu'un destinataire
  est choisi (remplacé par l'objet du modèle si un modèle est appliqué).
- **Aperçu de l'en-tête** : vignette de l'image d'en-tête sur la fiche société
  et sur la lettre en mode image.
- Boutons distincts **Aperçu PDF** (ouvre) et **Télécharger le PDF**.
- Les lettres avec champs de fusion non remplis sont **surlignées** dans la
  liste.

### Intégrations optionnelles (détectées à l'exécution)
- **`bf_persona`** : pré-remplissage de l'appel et de la salutation finale depuis
  le persona du destinataire.
- **`bf_claude_chat`** : bouton « Réviser avec Claude » qui ouvre l'assistant avec
  la lettre en contexte.
- Aucune dépendance dure : le module fonctionne seul ; les boutons disparaissent
  si les modules ne sont pas installés.

### Configuration guidée
- Panneau d'intégration (onboarding) en 3 étapes : en-tête → modèles →
  première lettre.

## Modèles

| Modèle | Rôle |
|---|---|
| `letter.document` | La lettre (instance) |
| `letter.template` | Modèle de lettre réutilisable |
| `letter.quicktext` | Bloc de texte réutilisable |
| `letter.merge.wizard` | Assistant de fusion en lot |
| `letter.send.wizard` | Assistant d'envoi par courriel |
| `letter.quicktext.picker` | Assistant d'insertion de bloc |

## Champs de fusion disponibles

`{{ object.partner_id.name }}`, `{{ object.partner_id.parent_id.name }}`,
`{{ object.recipient_name }}`, `{{ object.letter_date }}`,
`{{ object.reference }}`, `{{ object.company_id.name }}`,
`{{ object.signatory_id.name }}`, `{{ object.signatory_function }}` — ainsi que
toute expression QWeb `<t t-out="..."/>`.

## Configuration

Fiche **Société** → onglet **Lettres** :
- **En-tête par défaut** appliqué aux nouvelles lettres + marges haute/basse du
  corps (modes sans en-tête généré).
- **Image d'en-tête** (PNG/JPG) et **PDF d'en-tête** téléversables.
- **Signataire** par défaut, fonction, image de signature.
- **Mention d'en-tête** et **pied de page** (modes générés).

Les couleurs de marque proviennent de `bf_lexend`.

## Sécurité

- Tout utilisateur interne peut rédiger des lettres (créer / modifier).
- Le groupe **Rédacteur de lettres / Gestionnaire** gère les modèles, les blocs de
  texte et la configuration de l'en-tête.
- Règles multi-société sur les lettres et les blocs de texte.

## Dépendances

- Odoo : `base`, `mail`, `bf_lexend`, `bf_onboarding_base`.
- Python : `PyPDF2` (mode « PDF téléversé » — fourni dans l'image Odoo BF).

## Notes techniques

- La fusion utilise `mail.render.mixin` (le moteur de `mail.template`) : passe
  `inline_template` pour les jetons `{{ }}`, puis passe `qweb` si des
  `<t t-out>` subsistent. Le résultat est encapsulé en `Markup`.
- Le PDF est un gabarit QWeb autonome (pas `web.external_layout`), comme les
  autres rapports brandés Blue Fox ; les couleurs sont injectées depuis
  `doc.company_id`.
- Mode `pdf_overlay` : `_get_pdf_binary()` rend le corps sans chrome puis
  `_stamp_on_letterhead()` le superpose à chaque page du PDF d'en-tête via
  PyPDF2.
- Mode `image` : fond pleine page (limite connue — couvre la première page ;
  préférer `pdf_overlay` pour les lettres multi-pages).
- Détection des modules optionnels via `ir.module.module` (état `installed`).
- Licence LGPL-3.

## Tests

Suite `TransactionCase` dans `tests/test_letter_writer.py` couvrant chaque
fonctionnalité annoncée. Exécution :

```bash
odoo -c <conf> -d <db> -u bf_letter_writer --test-enable --test-tags /bf_letter_writer --stop-after-init
```
