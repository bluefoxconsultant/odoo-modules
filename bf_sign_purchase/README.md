# Blue Fox — Signature pour les achats (`bf_sign_purchase`)

Module passerelle qui branche les bons de commande d'achat sur la signature
électronique `bf_sign`.

## Ce que ça fait

- Ajoute une action « Envoyer pour signature » sur `purchase.order` (via le
  mixin `bf.sign.mixin`).
- Rend le bon de commande / la demande de prix en PDF
  (`purchase.action_report_purchase_order`), crée une demande de signature
  `bf_sign` liée, puis reverse le document signé dans le fil du bon de commande
  une fois signé.

## Dépendances

`bf_sign`, `purchase`.

## Licence

Distribué sous **Business Source License 1.1** (BUSL-1.1). Voir le fichier
[`LICENSE`](LICENSE) pour les paramètres exacts.

- **Permis sans entente** : l'usage en production pour vos propres opérations
  internes.
- **Demande une entente écrite** : fournir le module comme produit ou service à
  des tiers — hébergé, infogéré ou revendu.
- **Change Date** : le 2029-07-20, cette version bascule automatiquement en
  **LGPL-3.0-or-later**.
