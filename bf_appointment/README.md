# Blue Fox Appointment (`bf_appointment`)

Pages de réservation publiques en libre-service, en extension de *Resource
Booking* (OCA).

## Fonctionnalités

- **Pages publiques de prise de rendez-vous** par type de réservation, avec
  créneaux calculés à partir des disponibilités des ressources.
- **Portail client** : confirmation, reprogrammation et annulation en
  libre-service.
- **Consentement vie privée** intégré (`privacy_consent`) à la prise de
  rendez-vous.
- **Création automatique de tâches/projets** au moment de la réservation.
- **Courriels balisés Blue Fox** via `bluefox_branding` (en-tête, couleurs de
  marque, pied de page par société).
- **Assistant d'intégration** (`bf_onboarding_base`) pour configurer les types
  de réservation.

## Dépendances

`resource_booking`, `portal`, `mail`, `project`, `privacy_consent`,
`bluefox_branding`, `bf_onboarding_base`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
