# Rencontres — Portail client (`bf_meeting_portal`)

Donne au client, dans son portail Odoo, un accès en lecture aux comptes rendus de
rencontre de [`bf_meeting`](../bf_meeting) **qui lui ont déjà été envoyés par
courriel**, sous `/my/meetings`.

## Cas d'usage

Le client a reçu un compte rendu par courriel il y a trois semaines et ne le
retrouve plus. Plutôt que de le lui réexpédier, il le reconsulte lui-même.

## Principe : une archive, pas une divulgation

Le portail ne publie rien de neuf. Un compte rendu n'y apparaît que si :

- `report_state == 'sent'`,
- `report_sent_date` est renseignée, **et**
- le partenaire figure dans `report_recipient_ids`.

⚠️ **L'état seul ne prouve rien.** `report_state` est un champ ordinaire : la vue
kanban de `bf_meeting` est groupée dessus sans `records_draggable="0"`, donc
glisser une carte dans la colonne « Envoyé » émet un `write` nu ; les scripts
d'import et les écritures XML-RPC le posent aussi directement. Sur la base
d'origine, 118 des 202 comptes rendus « envoyés » n'avaient ainsi aucune
`report_sent_date`.

`report_sent_date`, elle, n'est écrite que par `action_send_report_direct`, dans
le même `write()` que l'état, et cette méthode refuse de s'exécuter sans
destinataires et met un courriel en file. L'exiger rend l'invariant vrai au lieu
de le promettre — et sur les données d'origine, cela n'a retiré aucun compte
rendu légitime.

⚠️ **Point de vigilance à l'intégration.** Cet invariant tient tant que rien
n'écrit `report_sent_date` à cru. Si vous avez des scripts, des automatisations
ou des outils externes qui manipulent `meeting.record` par l'ORM ou XML-RPC,
faites-leur appeler `action_send_report_direct` plutôt que d'écrire les champs
directement. Le `readonly=True` du champ ne protège pas : c'est une contrainte
de vue, l'ORM et XML-RPC écrivent quand même.

Le partenaire visé est l'utilisateur du portail **ou sa société**
(`commercial_partner_id`) : les contacts d'une même organisation voient ce qui a
été adressé à l'organisation, mais pas ce qui a été adressé nommément à un
collègue.

⚠️ **Le critère n'est pas « participant ».** L'envoi d'un compte rendu dans
`bf_meeting` n'a délibérément aucun repli sur la liste des participants, pour
éviter des envois accidentels au client. Brancher la visibilité du portail sur la
présence rouvrirait ce risque : quelqu'un assiste à une rencontre et pourrait lire
un compte rendu que personne n'a choisi de lui transmettre.

## Les ordres du jour ne sont volontairement pas exposés

Ils l'étaient dans la 1.x. Ils ont été retirés en 2.0.0 : **aucun champ de
`bf_meeting` ne prouve qu'un ordre du jour a été expédié.**

- `sent_date` ne le prouve pas. `action_send_agenda_wizard` l'estampe à la simple
  **ouverture** du composeur, pour ouvrir la fenêtre de contributions, et rien ne
  l'efface si l'assistant est abandonné.
- L'état non plus. `action_confirm()` n'envoie que si `auto_send_on_confirm`, dont
  le défaut est `False` ; `action_start_meeting()` confirme un brouillon
  automatiquement ; `action_create_meeting_record()` écrit `done` sans condition.
  `confirmed`/`done` est donc atteignable sans le moindre courriel.
- Le fil de discussion non plus : les `mail.mail` sont purgés après envoi, et sur
  des données réelles ni `message_type`, ni `notification_ids`, ni `partner_ids`
  ne distinguaient l'envoi de l'abandon.

Combinés, ces trois points rendaient visible d'un client participant un ordre du
jour interne jamais expédié — et comme un brouillon a rarement de
`recipient_ids`, par la branche de repli sur `participant_ids`, la plus large.
Plutôt que d'inventer un critère approximatif sur un contenu confidentiel, les
ordres du jour sortent du portail. Ils y reviendront quand `bf_meeting` portera
un marqueur d'envoi fiable.

## Ce qui est exposé, et ce qui ne l'est jamais

Affiché : résumé, sujets et leurs points, décisions (avec décideur et élément lié),
éléments d'action (assigné, échéance), questions ouvertes, livrables, présences.
La page tire ces sections de `meeting.record._get_report_data()`, la méthode qui
alimente le rapport client, pour rester à parité avec lui.

**PDF** : le rapport attaché au courriel du compte rendu
(`report_template_ids` -> `action_report_meeting_record`). Il est **regénéré à la
lecture**, pas repris de la pièce jointe archivée : il reflète donc les
corrections apportées au compte rendu depuis l'envoi. C'est le même rapport, pas
le même octet.

**Jamais transmis au gabarit** : `verbatim`, `verbatim_html` (transcription
brute), `review_notes`, ni les notes en direct. `structured_notes_json` n'est pas
exposé tel quel ; seules en sont extraites les sections que le rapport client rend
déjà. Les pièces jointes ne sont pas exposées.

## Sécurité

**Aucun droit ORM n'est accordé au groupe portail** — ni `ir.model.access`, ni
`ir.rule`. C'est délibéré : accorder l'ACL sur `meeting.record` ouvrirait
`/web/dataset/call_kw` et permettrait à un utilisateur portail authentifié de lire
la transcription brute par RPC, hors des gabarits.

Le contrôleur est donc la seule porte d'entrée. Il applique le domaine de
visibilité dans la recherche elle-même — `search([('id','=',id)] + domaine)`,
jamais un `browse()` sur un identifiant fourni par le client — puis passe en
`sudo()` pour lire les données. Les gabarits ne reçoivent que des **dictionnaires
en liste blanche**, jamais l'enregistrement : un champ interne reste inatteignable
même si un gabarit est modifié plus tard par distraction.

`report_state`, `report_sent_date` et `report_recipient_ids` passent en
`copy=False` (voir `models/meeting_record.py`). Sans cela, dupliquer un compte
rendu envoyé produisait une copie marquée « envoyé », destinataires intacts, que
le portail aurait montrée alors qu'aucun courriel n'était jamais parti pour elle.

Toutes les routes sont en `auth='user'`. Les enregistrements archivés sont exclus.

## Structure

```
controllers/portal.py                 domaine de visibilité, listes blanches, routes
models/meeting_record.py              copy=False sur les champs de visibilité
views/meeting_portal_templates.xml    entrée d'accueil, fil d'Ariane, liste, détail
static/src/img/portal_icon.svg        icône de la carte (64x64 intrinsèque)
```

Routes : `/my/meetings`, `/my/meetings/record/<id>` et
`/my/meetings/record/<id>/pdf`.

L'entrée d'accueil déclare `placeholder_count` : `portal.portal_docs_entry` rend
ses cartes en `d-none` par défaut, une carte sans compteur reste donc invisible.
Le compteur est alimenté par `_prepare_home_portal_values`.

## Dépendances

- `bf_meeting` — le modèle `meeting.record`
- `portal` — `CustomerPortal` et les gabarits d'accueil

## Installation

```bash
odoo -d <base> -i bf_meeting_portal --stop-after-init
```

Le module déclarant des contrôleurs, redémarrez le service ensuite pour que les
routes soient servies.

Aucune configuration n'est requise. La portée dépend entièrement de
`report_recipient_ids` : sur une base dont l'historique a été envoyé sans
renseigner ce champ, le portail ne couvrira que les envois à venir.

## Licence

LGPL-3
