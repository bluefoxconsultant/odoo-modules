# Levée de fonds — Cœur (`bf_fundraising_core`)

Plateforme de gestion des donateurs et de collecte de fonds pour organismes de
bienfaisance (OBNL), bâtie par-dessus le module **Dons** (OCA `donation`).
Comparable à **Raiser's Edge / Blackbaud**, en français, dans Odoo.

## Ce que ça ajoute

- **Structure de collecte à 4 niveaux** : Fonds → Campagne → Sollicitation →
  Trousse (Fund / Campaign / Appeal / Package), avec objectifs et montants
  amassés calculés et barres de progression.
- **Le Fonds pilote la comptabilité analytique** : chaque fonds pointe vers un
  compte analytique ; les lignes de don sont ventilées automatiquement.
- **Fiche constituant** enrichie sur `res.partner` : type (individu, foyer,
  organisation, fondation), regroupement par foyer, codes de sollicitation
  (ne pas solliciter / appeler / etc.), sommaire des dons (total, premier don,
  dernier don, plus grand don), capacité et cote de richesse, prospect majeur.
- **Rapport donateurs inactifs (LYBUNT)** et autres filtres de segmentation
  directement sur la liste des constituants.

## Dépendances

`donation` (OCA), `analytic`, `bf_onboarding_base`.

Le **reçu officiel canadien conforme (ARC + Revenu Québec, en français)** est
fourni par le module compagnon **`bf_receipt_ca`**. Le formulaire web de don et
le portail donateur sont dans **`bf_fundraising_web`**.

## Licence

AGPL-3 (le module étend le module OCA `donation`, sous AGPL-3).
