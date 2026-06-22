# Tableau de bord Blue Fox (`bf_dashboard`)

Tableau de bord unifié qui agrège la facturation, l'hébergement, les matrices
de connaissances et la vie privée en une seule vue.

## Fonctionnalités

- Cartes de synthèse agrégeant plusieurs domaines opérationnels
  (facturation, hébergement, connaissances, consentements vie privée).
- Point d'entrée unique pour le suivi quotidien.
- Extensible : d'autres modules peuvent ajouter leurs propres cartes
  (voir `bf_subscription_dashboard`).

> Note : à l'installation, le `post_init_hook` `_set_home_action` redéfinit
> l'action d'accueil des utilisateurs pour ouvrir ce tableau de bord au
> démarrage de la session.

## Dépendances

`base`, `account`, `project`, `mail`, `hosting_management`,
`project_knowledge_matrix`, `privacy_consent`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
