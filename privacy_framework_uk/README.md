# Cadre de confidentialité — UK GDPR (Royaume-Uni)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)

Module **de données** (data-only) pour [`privacy_consent`](../privacy_consent). Ajoute le cadre **UK GDPR / Data Protection Act 2018** (variante britannique post-Brexit du RGPD).

## Ce que le pack ajoute

- Un enregistrement `privacy.framework` « UK GDPR » : **Information Commissioner's Office (ICO)**, délégué à la protection des données (DPO), âge du consentement **13 ans**, déclaration d'incident **72 h**, AIPD/DPIA (art. 35 UK GDPR).
- Les **6 bases légales** de l'art. 6(1) UK GDPR.
- Les **droits des personnes concernées** : accès, rectification, effacement, limitation, portabilité, opposition, réclamation auprès de l'ICO.

## Utilisation

Après installation, définissez ce cadre comme défaut de la société (**Vie privée → Configuration → Cadres réglementaires**) ou par enregistrement.

## Dépendances

`privacy_consent`. Module de données uniquement.

## Licence

LGPL-3 — Blue Fox Inc.
