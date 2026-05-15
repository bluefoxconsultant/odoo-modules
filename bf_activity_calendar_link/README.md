# BF Activites - Lien Calendrier

**Version** : 18.0.1.1.0
**Licence** : MIT
**Auteur** : Blue Fox Inc.
**Compatibilite** : Odoo 18 Community & Enterprise

## Probleme

Odoo 18 possede nativement le champ `calendar_event_id` sur `mail.activity` et
l'inverse `activity_ids` sur `calendar.event`. Cependant, **aucune interface ne
permet de lier un evenement calendrier existant a une activite** : ni le wizard
de planification, ni le formulaire popup d'activite, ni le formulaire
d'evenement calendrier n'exposent cette relation.

Ce module comble ce manque en ajoutant l'UI necessaire aux trois endroits cles.

## Fonctionnalites

### Wizard de planification (chatter > Planifier une activite)

- Champ **Evenement calendrier** (Many2one) pour selectionner un evenement existant
- Auto-remplissage de l'echeance et du resume a partir de l'evenement
- Bloc d'information affichant les dates, le lieu et la source de synchronisation
- Le lien est automatiquement ecrit sur l'activite creee

### Formulaire popup d'activite

- Champ **Evenement calendrier** visible lors de la creation ou modification
- Bloc d'information avec dates, lieu, participants et badge Nextcloud

### Formulaire d'evenement calendrier

- **Bouton statistique** "Activites" dans la boite de boutons
- **Onglet "Activites liees"** listant toutes les activites rattachees
  (resume, type, echeance, responsable, etat, document source)

### Integration Nextcloud

Le module depend de `calendar_nextcloud_sync` et affiche un badge **Nextcloud**
lorsque l'evenement lie provient d'une synchronisation CalDAV. Les evenements
Nextcloud ne sont jamais modifies par ce module (lecture seule).

## Securite

- **Filtrage par participation** : le dropdown d'evenements n'affiche que les
  evenements ou l'utilisateur courant est participant ou organisateur
  (`partner_ids.user_ids in uid`). Les evenements prives d'autres utilisateurs
  sont exclus.
- **Pas de creation ni de navigation** : les options `no_create`, `no_open` et
  `no_quick_create` empechent la creation accidentelle d'evenements et la
  navigation vers le formulaire complet.
- **Cascade natif** : la suppression d'un evenement (y compris via sync
  Nextcloud) entraine automatiquement la suppression des activites liees
  (`ondelete='cascade'` defini par le module `calendar` natif).
- **Pas de nouveau modele** : le module herite uniquement de modeles existants,
  donc aucune regle d'acces supplementaire n'est necessaire.

## Dependances

| Module                     | Source          | Role                              |
|----------------------------|-----------------|-----------------------------------|
| `calendar`                 | Odoo core       | Champ natif `calendar_event_id`   |
| `calendar_nextcloud_sync`  | Blue Fox Inc.   | Champ `x_sync_source` pour badge  |

## Installation

```bash
docker exec <conteneur-odoo> odoo -d <base> -i bf_activity_calendar_link --stop-after-init
```

Ou via l'interface : Applications > Mettre a jour la liste > Rechercher
"Activites - Lien Calendrier" > Installer.

## Structure des fichiers

```
bf_activity_calendar_link/
  __init__.py
  __manifest__.py
  README.md
  models/
    __init__.py
    mail_activity.py          # Champs related/computed sur mail.activity
    calendar_event.py         # Action pour creer une activite liee
  wizard/
    __init__.py
    mail_activity_schedule.py # Extension du wizard avec onchange + override
  views/
    mail_activity_schedule_views.xml  # Formulaire wizard
    mail_activity_views.xml          # Formulaire popup d'activite
    calendar_event_views.xml         # Bouton stat + onglet activites
```

## Details techniques

### Champs ajoutes sur `mail.activity`

| Champ                            | Type      | Source                          |
|----------------------------------|-----------|---------------------------------|
| `calendar_event_start`           | Datetime  | Related `calendar_event_id.start` |
| `calendar_event_location`        | Char      | Related `calendar_event_id.location` |
| `calendar_event_sync_source`     | Selection | Related `calendar_event_id.x_sync_source` |
| `calendar_event_attendee_names`  | Char      | Computed depuis `calendar_event_id.partner_ids` |

### Champs ajoutes sur `mail.activity.schedule` (TransientModel)

| Champ                            | Type      | Source                          |
|----------------------------------|-----------|---------------------------------|
| `calendar_event_id`              | Many2one  | Nouvel input utilisateur        |
| `calendar_event_start`           | Datetime  | Related `calendar_event_id.start` |
| `calendar_event_stop`            | Datetime  | Related `calendar_event_id.stop` |
| `calendar_event_location`        | Char      | Related `calendar_event_id.location` |
| `calendar_event_sync_source`     | Selection | Related `calendar_event_id.x_sync_source` |

### Methode ajoutee sur `calendar.event`

- `action_create_linked_activity()` : ouvre le formulaire d'activite avec les
  valeurs par defaut pre-remplies (evenement, resume, echeance).

## Licence

MIT License

Copyright (c) 2026 Blue Fox Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Remerciements

Le developpement de ce module a ete assiste par des outils d'intelligence
artificielle (Claude, Anthropic) pour la generation de code, la revue de
securite et la redaction de documentation.
