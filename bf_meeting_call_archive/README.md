# Rencontres ↔ Archive d'appels (`bf_meeting_call_archive`)

Pont optionnel entre les modules `bf_meeting` et `bf_sms_archive` : lie un
compte rendu de rencontre à l'appel archivé correspondant.

## Fonctionnalités

- Champ `call_archive_id` sur `meeting.record` (visible quand le mode est
  « Téléphonique »).
- Relation inverse `meeting_record_ids` sur `call.archive.call` + bandeau dans
  le formulaire d'appel.
- Pré-remplissage automatique de `duration_minutes` et `partner_id` au choix de
  l'appel.
- Le journal brut des appels n'est jamais modifié : la promotion est purement
  déclarative.

S'auto-installe lorsque `bf_meeting` **et** `bf_sms_archive` sont tous deux
installés.

## Dépendances

`bf_meeting`, `bf_sms_archive`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier `LICENSE`.
