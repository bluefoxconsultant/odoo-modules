# Hébergement — pont vers les abonnements (`bf_subscription_hosting`)

Module-pont entre [`hosting_management`](../hosting_management) et
[`bf_subscription`](../bf_subscription).

## Pourquoi

Les coûts d'infrastructure récurrents (noms de domaine, renouvellements SSL,
services) sont souvent saisis **deux fois** : une fois comme domaine
d'hébergement (`hosting.domain`) et une fois comme abonnement
(`subscription.subscription`). Ce pont élimine cette double saisie.

## Ce que fait le module

Ajoute un bouton **« Créer un abonnement »** dans l'en-tête de la fiche du
domaine d'hébergement. Il crée un abonnement **brouillon** pré-rempli à partir
des données du domaine :

| Domaine (`hosting.domain`) | Abonnement (`subscription.subscription`) |
| --- | --- |
| `name` | `name` (« Nom de domaine — … ») |
| — | `category` = `domain_name` |
| `annual_cost` | `cycle_amount`, `cycle` = `annual` |
| `currency_id` | `currency_id` |
| `partner_id` | `vendor_id` (à réviser — voir ci-dessous) |
| `date_expiration` | ancre `start_date` (→ prochain renouvellement) |
| `auto_renew` | `auto_renew` |
| `registrar` | `external_reference` |

Un champ de liaison est stocké **dans les deux sens**
(`hosting.domain.subscription_id` ↔ `subscription.subscription.hosting_domain_id`)
afin que le bouton se masque une fois l'abonnement créé — pas de doublon. Un
bouton intelligent ouvre l'abonnement lié.

**Pas de synchronisation automatique en arrière-plan** : la création est
volontaire, ponctuelle et l'abonnement reste en **brouillon** pour révision
avant activation.

> Le champ `vendor_id` de l'abonnement (le fournisseur/registraire) est requis.
> Comme `hosting.domain` ne stocke pas le registraire sous forme de partenaire,
> il est pré-rempli avec le `partner_id` du domaine (ou la société) ; ajustez-le
> au besoin avant d'activer l'abonnement.

## Installation

S'auto-installe lorsque `hosting_management` **et** `bf_subscription` sont tous
deux présents (`auto_install: True`).

## Dépendances

`hosting_management`, `bf_subscription`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier [`LICENSE`](LICENSE).
