# BF — Nettoyage des abonnés (`bf_follower_cleanup`)

Cron qui retire des abonnés (followers) des chatters toute personne qui n'est
pas un·e employé·e interne.

## Fonctionnalités

- Tâche planifiée qui parcourt les `mail.followers` et retire les partenaires
  non rattachés à un·e employé·e.
- Garde les fils de discussion internes propres (évite la fuite de
  notifications vers des contacts externes ajoutés par inadvertance).

## Dépendances

`mail`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
