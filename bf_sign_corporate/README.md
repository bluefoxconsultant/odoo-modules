# Blue Fox — Signature des résolutions corporatives (`bf_sign_corporate`)

Module-pont qui branche le moteur de signature électronique natif
[`bf_sign`](../bf_sign) sur les résolutions corporatives du module
[`project_knowledge_matrix`](../project_knowledge_matrix).

## Ce que ça fait

- Ajoute une action **« Envoyer pour signature »** sur la résolution corporative
  (`corporate.resolution`) via le mixin `bf.sign.mixin`, plus un bouton
  intelligent « Signatures » qui compte les demandes liées.
- Rend la résolution en PDF brandé (rapport
  `project_knowledge_matrix.action_report_corporate_resolution`), crée une
  demande de signature `bf_sign` liée, puis reverse le document signé (+ le
  certificat de complétion) dans le fil de discussion de la résolution une fois
  signée par tous.

## Signataires par défaut

La demande est pré-remplie à partir du registre corporatif :

- **résolution du conseil** → les administrateurs actifs (`corporate.director`) ;
- **résolution des actionnaires** → le proposeur (et le secondeur, s'il y a lieu).

Les signataires restent modifiables sur la demande en brouillon avant l'envoi.
Si un signataire par défaut n'a pas de courriel, l'action le signale clairement
en le nommant, plutôt que d'échouer sur une contrainte technique.

## Dépendances

`bf_sign`, `project_knowledge_matrix`.

## Licence

Distribué sous licence **LGPL-3**. Voir le fichier [`LICENSE`](LICENSE).
