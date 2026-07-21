# Blue Fox — Signature des consentements Loi 25 (`bf_sign_privacy`)

Module-pont qui branche le moteur de signature électronique natif
[`bf_sign`](../bf_sign) sur le module de consentements
[`privacy_consent`](../privacy_consent).

`privacy_consent` peut envoyer ses consentements à signer via des plateformes
**externes** (DocuSeal, LibreSign). Ce pont ajoute une troisième voie,
**interne** : « Envoyer pour signature » sur le consentement (`privacy.consent`)
via le mixin `bf.sign.mixin`.

Le certificat de consentement est rendu en PDF (rapport
`privacy_consent.action_report_consent_certificate`), une demande de signature
`bf_sign` liée est créée, et le document signé est reversé dans le fil de
discussion du consentement une fois signé. Le sujet du consentement
(`subject_partner_id`) est pré-rempli comme signataire par défaut.

Les artefacts de consentement peuvent ainsi être signés avec le moteur de
signature électronique simple (SES) maison — opposable en droit québécois (voir
[`bf_sign`](../bf_sign)) — **sans dépendre d'un signataire externe**.

## Installation

S'auto-installe lorsque `bf_sign` **et** `privacy_consent` sont tous deux
présents (`auto_install: True`).

## Dépendances

`bf_sign`, `privacy_consent`.

## Licence

Distribué sous **Business Source License 1.1** (BUSL-1.1). Voir le fichier
[`LICENSE`](LICENSE) pour les paramètres exacts.

- **Permis sans entente** : l'usage en production pour vos propres opérations
  internes.
- **Demande une entente écrite** : fournir le module comme produit ou service à
  des tiers — hébergé, infogéré ou revendu.
- **Change Date** : le 2029-07-20, cette version bascule automatiquement en
  **LGPL-3.0-or-later**.
