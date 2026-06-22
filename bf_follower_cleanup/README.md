# BF — Nettoyage des abonnés (`bf_follower_cleanup`)

Cron qui retire des abonnés (followers) des chatters toute personne qui n'est
pas un·e employé·e interne.

## Fonctionnalités

- Tâche planifiée (cron) qui s'exécute **toutes les 5 minutes** et parcourt les
  `mail.followers` pour retirer les partenaires non rattachés à un·e employé·e.
- Garde les fils de discussion internes propres (évite la fuite de
  notifications vers des contacts externes ajoutés par inadvertance).

## Qui est conservé / retiré

Un abonné est **conservé** uniquement s'il correspond à un·e utilisateur·rice
interne, c'est-à-dire un `res.users` avec `share = False` (actif ou archivé).
Tout autre abonné (contact externe, utilisateur portail/partagé) est retiré au
prochain passage du cron.

### Exempter un partenaire

Le module ne maintient volontairement **aucune liste blanche** de contacts
externes à conserver. Pour qu'un partenaire reste abonné, il doit posséder un
compte utilisateur interne (`share = False`). Les contacts purement externes ne
peuvent donc pas être exemptés ; c'est le comportement attendu.

## Paramètres de configuration

Deux paramètres système (`ir.config_parameter`) règlent le comportement :

| Clé | Défaut | Rôle |
|-----|--------|------|
| `bf_follower_cleanup.always_remove_partner_ids` | *(vide)* | Liste optionnelle d'IDs `res.partner` (séparés par `,` ou `;`) à purger **inconditionnellement**, même s'ils sont rattachés à un·e utilisateur·rice interne — utile pour des comptes d'intégration/service. Laissé vide par défaut. |
| `bf_follower_cleanup.batch_size` | `5000` | Nombre maximal de lignes d'abonnés traitées par passage du cron. |

## Dépendances

`mail`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.

## Journal des modifications

### 18.0.1.0.1

- La valeur par défaut de `always_remove_partner_ids` est désormais **vide**
  (auparavant un ID de partenaire interne propre à un déploiement).
- Documentation des paramètres de configuration, de la cadence du cron et du
  comportement de la liste « toujours retirer » ; ajout du fichier `LICENSE`.
