# Abonnements (`bf_subscription`)

Registre unique des abonnements payants : SaaS, adhésions corporatives,
infrastructure, certificats, noms de domaine, services professionnels
récurrents.

## Fonctionnalités

- Suivi des abonnements **en propre** ou **gérés au nom d'un client**.
- Corrélation manuelle et automatique avec les factures fournisseur
  (`account.move`).
- Refacturation au client en 3 modes : au coût / avec marge (%) / montant fixe.
- Relances automatiques avant renouvellement (activité Odoo).
- Vue tableau de bord : coût mensualisé, prochains renouvellements, MRR
  consolidé.
- Boutons intelligents sur la fiche partenaire (abonnements gérés / facturés).

## Dépendances

`base`, `mail`, `account`, `analytic`, `bf_onboarding_base`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
