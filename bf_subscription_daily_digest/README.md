# Abonnements — section du digest quotidien (`bf_subscription_daily_digest`)

Module-pont qui injecte une section **« Renouvellements à venir »** dans le
courriel du digest quotidien (`daily_todo_digest`).

S'auto-installe lorsque `bf_subscription` **et** `daily_todo_digest` sont tous
deux présents.

Cette section quotidienne est un simple aperçu, distinct du récapitulatif
complet d'abonnements (`subscription.digest`) embarqué dans `bf_subscription` :
ce dernier reste le canal officiel pour le rapport détaillé (sommaire de
dépense, dormants, coût par client géré, envoi périodique), tandis que ce
module-pont se contente de glisser un rappel des renouvellements imminents dans
le courriel du digest quotidien déjà existant.

## Dépendances

`bf_subscription`, `daily_todo_digest`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
