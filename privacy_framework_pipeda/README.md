# Cadre de confidentialité — LPRPDE / PIPEDA (Canada)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)

Module **de données** (data-only) pour [`privacy_consent`](../privacy_consent). Ajoute le cadre fédéral canadien **LPRPDE / PIPEDA** (pour les clients canadiens hors Québec).

## Ce que le pack ajoute

- Un enregistrement `privacy.framework` « PIPEDA » : **Commissariat à la protection de la vie privée du Canada (CPVP / OPC)**, responsable de la vie privée, notification d'incident en cas de **risque réel de préjudice grave** (*real risk of significant harm*).
- Des **bases de traitement** fondées sur les 10 principes d'équité de l'information : consentement, exception légale (art. 7), transaction commerciale (art. 7.2).
- Les **droits** : accès, contestation de l'exactitude / correction (principe 4.9), plainte auprès du CPVP.

## Utilisation

Après installation, définissez ce cadre comme défaut de la société (**Vie privée → Configuration → Cadres réglementaires**) ou par enregistrement.

## Dépendances

`privacy_consent`. Module de données uniquement.

## Licence

LGPL-3 — Blue Fox Inc.
