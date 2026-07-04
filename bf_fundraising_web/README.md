# Levée de fonds — Web & Portail donateur (`bf_fundraising_web`)

Service en ligne pour la suite de levée de fonds.

## Formulaire de don public (`/don`)

Un visiteur saisit nom, courriel, adresse, montant et (optionnellement) le fonds
et la campagne. Le don est créé dans Odoo — la fiche donateur est **appariée par
courriel ou créée** (marquée « constituant »). Le don est en **brouillon** ; à sa
**validation** par le personnel, le **reçu officiel** est émis (via
`bf_receipt_ca`) et **envoyé par courriel** automatiquement.

Le formulaire vit à `/don`. Aucun menu n'est ajouté automatiquement au site :
chaque organisme ajoute son propre lien/bouton « Faire un don » où il le souhaite
(un site de consultation, par exemple, ne devrait pas afficher de lien de don).

> Configuration requise : un **produit de don** doit être défini sur la société
> (« Produit pour les dons par virement ») pour que le formulaire crée les lignes.

## Portail donateur

Le donateur connecté voit, sous **Mon compte** :

- **Mes dons** — historique de ses dons (numéro, date, campagne, montant, lien
  vers le reçu) ;
- **Mes reçus officiels** — téléchargement des reçus PDF conformes ARC + RQ.

L'accès est restreint au donateur (vérification de propriété dans les
contrôleurs, rendu en `sudo`).

## Dépendances

`bf_receipt_ca`, `website`, `portal`. Licence AGPL-3.
