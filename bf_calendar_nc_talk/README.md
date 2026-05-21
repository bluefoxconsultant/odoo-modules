# BF Calendar — Nextcloud Talk button (`bf_calendar_nc_talk`)

Ajoute un bouton **« + Nextcloud Talk »** à côté de « + Réunion Odoo » sur les
événements du calendrier.

## Fonctionnalités

- Crée une conversation Nextcloud Talk publique via l'API OCS (Spreed).
- Écrit l'URL de la salle dans le champ `videocall_location` de l'événement,
  de sorte que les invitations et rappels pointent vers la visioconférence.
- Configuration de l'instance Nextcloud cible via les paramètres système.

## Dépendances

`calendar`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
