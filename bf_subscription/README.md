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

## Rapport et tableau de bord

- **Récapitulatif intégré** : ce module de base embarque son propre modèle
  `subscription.digest` (menu *Récapitulatif*), qui génère un rapport PDF des
  abonnements (sommaire de dépense, renouvellements à venir, abonnements
  dormants, coût par client géré) et peut l'envoyer périodiquement. Une
  configuration `subscription.digest` est livrée par défaut, en mode « sur
  demande » (`auto_send = False`).
- **Carte de tableau de bord (MRR)** : la carte de synthèse Abonnements du
  tableau de bord Blue Fox n'est **pas** fournie par ce module. Elle est
  ajoutée par le module-pont distinct `bf_subscription_dashboard`, qui
  s'auto-installe lorsque `bf_subscription` et `bf_dashboard` sont tous deux
  présents.

## Dépendances

`base`, `mail`, `account`, `analytic`, `bf_onboarding_base`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.

## Journal des modifications

### 18.0.1.3.1

- Retrait de noms de clients des textes d'aide et d'intégration (artefact
  public) ; ajout du fichier `LICENSE`.
