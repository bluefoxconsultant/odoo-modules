# Cadre de confidentialité — GDPR (UE)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)

Module **de données** (data-only) pour [`privacy_consent`](../privacy_consent). Ajoute le cadre réglementaire **RGPD / GDPR** (Règlement (UE) 2016/679) afin que les consentements, courriels et certificats soient rendus selon le droit européen.

## Ce que le pack ajoute

- Un enregistrement `privacy.framework` « GDPR » : autorité de contrôle nationale / EDPB, **délégué à la protection des données (DPO)**, âge du consentement **16 ans**, déclaration d'incident **72 h** (art. 33) + notification aux personnes en cas de risque élevé (art. 34), AIPD/DPIA (art. 35).
- Les **6 bases légales** de l'art. 6(1) : consentement, contrat, obligation légale, intérêts vitaux, mission d'intérêt public, intérêt légitime.
- Les **droits des personnes concernées** : accès, rectification, effacement, limitation, portabilité, opposition, réclamation.

## Utilisation

Après installation, définissez ce cadre comme défaut de la société (**Vie privée → Configuration → Cadres réglementaires**) ou par enregistrement (consentement, avis, calendrier). Aucune autre configuration requise.

## Dépendances

`privacy_consent`. Module de données uniquement — aucun modèle, vue ou code ajouté.

## Licence

LGPL-3 — Blue Fox Inc.
