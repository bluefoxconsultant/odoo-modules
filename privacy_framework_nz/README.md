# Cadre de confidentialité — Privacy Act 2020 (Nouvelle-Zélande)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)

Module **de données** (data-only) pour [`privacy_consent`](../privacy_consent). Ajoute le cadre néo-zélandais **Privacy Act 2020**.

## Ce que le pack ajoute

- Un enregistrement `privacy.framework` « Privacy Act 2020 » : **Office of the Privacy Commissioner (OPC)**, **Privacy Officer**, notification d'incident « dès que possible » + schéma **NotifyUs** en cas de préjudice grave (*serious harm*).
- Des **bases de traitement** fondées sur les Information Privacy Principles (IPP) : consentement/autorisation, finalité de collecte directement liée, autorisé par la loi.
- Les **droits** : accès (IPP 6), correction (IPP 7), plainte auprès du Privacy Commissioner.

## Utilisation

Après installation, définissez ce cadre comme défaut de la société (**Vie privée → Configuration → Cadres réglementaires**) ou par enregistrement.

## Dépendances

`privacy_consent`. Module de données uniquement.

## Licence

LGPL-3 — Blue Fox Inc.
