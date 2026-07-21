# Blue Fox — Signature pour les ventes (`bf_sign_sale`)

Module passerelle qui branche les commandes de vente sur la signature
électronique `bf_sign`.

## Ce que ça fait

- Ajoute une action « Envoyer pour signature » sur `sale.order` (via le mixin
  `bf.sign.mixin`).
- Rend le devis / bon de commande en PDF (`sale.action_report_saleorder`),
  crée une demande de signature `bf_sign` liée, puis reverse le document signé
  dans le fil de la commande une fois signé par tous.

## Dépendances

`bf_sign`, `sale`.

## Licence

Distribué sous **Business Source License 1.1** (BUSL-1.1). Voir le fichier
[`LICENSE`](LICENSE) pour les paramètres exacts.

- **Permis sans entente** : l'usage en production pour vos propres opérations
  internes.
- **Demande une entente écrite** : fournir le module comme produit ou service à
  des tiers — hébergé, infogéré ou revendu.
- **Change Date** : le 2029-07-20, cette version bascule automatiquement en
  **LGPL-3.0-or-later**.
