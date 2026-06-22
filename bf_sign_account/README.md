# Blue Fox — Signature pour la comptabilité (`bf_sign_account`)

Module-pont qui ajoute **« Envoyer pour signature »** sur les pièces comptables
(`account.move` : factures clients et factures fournisseurs) via le mixin
`bf.sign.mixin` de [`bf_sign`](../bf_sign).

La facture est rendue en PDF (rapport standard `account.account_invoices`), une
demande de signature `bf_sign` liée est créée, puis le document signé est
reversé dans le fil de discussion de la pièce une fois signé par tous les
signataires.

Le bouton d'en-tête est masqué sur les écritures comptables pures
(`move_type == 'entry'`) ; il n'apparaît que sur les factures et avoirs.

## Dépendances

`bf_sign`, `account`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier [`LICENSE`](LICENSE).
