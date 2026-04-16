# bf_mail_vigie

Ajoute un bouton "Re-router" à la liste et au formulaire de `bf.email`
(module `bf_email_management`). Analyse les headers `In-Reply-To`,
`References` et le `parent_id` du `mail.message` source pour suggérer
une chatter cible plus pertinente. Sur confirmation, met à jour les
colonnes `model` / `res_id` du `mail.message` (et la projection
`bf.email` correspondante), sans renvoi ni notification.

## Dépendances

- `mail`
- `bf_email_management`

## Sécurité

- Aucune nouvelle donnée sensible stockée.
- Opération de re-route = mutation de colonnes, aucun `message_post`,
  aucun `send_mail`, aucun `mail.mail` créé.
- Exige `write` sur l'enregistrement cible et sur le `bf.email` source,
  `read` sur le `mail.message`.
- Le wizard est accessible aux utilisateurs internes (`base.group_user`),
  mais l'ACL sur chaque récord cible est vérifiée avant mutation.

## UX

- Bouton "Re-router" dans le header du formulaire `bf.email`.
- Menu d'action "Re-router ce courriel" accessible sur la liste
  (sélection multiple: un wizard par enregistrement).
- Champ `Cible` de type `Reference` qui combine un dropdown des 12
  modèles courants (tâche, piste CRM, ticket helpdesk, contact, BC,
  facture, etc.) et un picker Many2one filtré sur le modèle choisi.
- Si une suggestion automatique existe (via headers ou parent_id),
  un bouton "Appliquer la suggestion" pré-remplit le champ `Cible`.

## Architecture

```
bf_mail_vigie/
├── models/bf_email.py          # inherit + action_open_reroute_wizard
├── wizard/reroute_wizard.py    # TransientModel + action_reroute
├── wizard/reroute_wizard_views.xml
├── views/bf_email_views.xml    # inherit form header + button
└── security/ir.model.access.csv
```

## Licence

LGPL-3
