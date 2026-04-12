# Blue Fox Appointment

Module Odoo 18 Community étendant `resource_booking` avec des pages de prise de rendez-vous publiques en libre-service, des rappels courriel automatisés et une détection du fuseau horaire côté client.

## Cas d'usage

Permettre à un prospect ou à un client de réserver une rencontre (démo, consultation, suivi) sans créer de compte Odoo, avec confirmation, rappels et annulation par courriel — le tout s'intégrant au calendrier de la ressource réservée.

## Fonctionnalités

- **Page publique de réservation** — une URL par type de réservation, accessible sans authentification
- **Détection de fuseau horaire côté client** — JavaScript détecte la TZ du navigateur et convertit les créneaux affichés
- **Questions d'accueil (intake)** — champs personnalisés par type de réservation collectés au moment de la prise de rendez-vous
- **Modèles de courriel** — confirmation, rappel (J-1), courriel de suivi, annulation
- **Séquence de rappels configurable** — planification de plusieurs envois avant la rencontre (modèle `appointment.email.schedule`)
- **Cron de synchronisation** — envoie les courriels programmés selon le délai configuré
- **Portail d'annulation** — lien signé dans les courriels permettant au client d'annuler lui-même

## Architecture technique

### Modèles

| Modèle | Rôle |
|---|---|
| `resource.booking.type` (hérité) | Ajout de champs : URL publique, modèles courriel, fuseau horaire |
| `resource.booking` (hérité) | Liaison aux questions d'accueil, état de notification |
| `calendar.event` (hérité) | Propagation des données depuis la réservation |
| `appointment.intake` | Questions d'accueil par type de réservation |
| `appointment.email.schedule` | Planification de rappels automatiques |
| `res.config.settings` (hérité) | Configuration globale (branding, URLs) |

### Dépendances

| Module | Rôle |
|---|---|
| `resource_booking` | Modèle de base pour les réservations |
| `portal` | Accès non authentifié aux pages publiques |
| `mail` | Modèles de courriel et envoi |

### Sécurité

- Règle `ir.rule` bloquant l'accès direct aux `appointment.intake.answer` pour les utilisateurs publics (accès uniquement via contrôleur signé)
- ACL standards pour utilisateurs internes

## Installation

```bash
docker compose exec odoo odoo -d <database> -i bf_appointment --stop-after-init
```

Configurer ensuite un `resource.booking.type` avec son URL publique et les modèles de courriel associés.

## Licence

AGPL-3

## Remerciements

Ce module a été développé avec l'assistance de Claude (Anthropic) pour l'architecture, l'implémentation et la documentation technique.
