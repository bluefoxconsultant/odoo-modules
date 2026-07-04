# Reçus de dons — Canada (`bf_receipt_ca`)

Rend les reçus du module **Dons** conformes aux exigences de l'**ARC** et de
**Revenu Québec**, **en français**. C'est le différenciateur clé face à
Raiser's Edge (dont les reçus suivent les règles américaines).

## Contenu du reçu officiel

Tous les éléments obligatoires de l'ARC : mention « Reçu officiel aux fins de
l'impôt sur le revenu », nom légal + adresse de l'organisme, **numéro
d'enregistrement (BN/RR)**, **numéro de série unique** (`REÇU-AAAA-NNNNN`,
réinitialisé chaque année, sans trou), date de délivrance, date/année du don,
nom + adresse du donateur, **montant du don**, **montant de l'avantage**,
**montant admissible**, signature autorisée, nom de l'ARC + adresse
`canada.ca/organismesdebienfaisance`.

Dons **en nature** : description du bien, **juste valeur marchande**, évaluateur.

## Particularités

- Un seul reçu français portant le numéro BN/RR satisfait le fédéral **et** le
  Québec (reconnaissance automatique au Québec depuis 2016).
- Champs « lieu de délivrance » et « évaluateur » **configurables** (modernisation
  ARC 2024).
- **Annulation / réémission** avec chaîne de remplacement ; les reçus annulés
  sont conservés (exigence ARC).

## Configuration

Sur la société (Paramètres → Sociétés) : numéro d'enregistrement (BN/RR),
signataire autorisé, image de signature, options d'affichage.

Le reçu (PDF) réutilise la mise en page de document brandée de la société
(`web.external_layout`) et la police **Lexend** (`bf_lexend`).

## Courriel de reçu brandé

Le courriel accompagnant le reçu est **brandé de la même façon que les autres
modules Blue Fox** : s'il est installé, `bluefox_branding` fournit la mise en
page transactionnelle `bf_mail_layout` (en-tête avec logo, couleurs et pied de
page de la société), résolue à l'exécution via
`donation.tax.receipt.bf_receipt_email_layout()`. Sans `bluefox_branding`, le
courriel retombe sur la mise en page légère standard d'Odoo — c'est donc une
**dépendance optionnelle** (non déclarée dans `depends`).

## Dépendances

Requises : `bf_fundraising_core`, `bf_lexend`.
Optionnelle : `bluefox_branding` (branding du PDF et du courriel). Licence AGPL-3.
