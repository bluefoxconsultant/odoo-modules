# bf_cx_meeting : feedback post-compte-rendu

S'auto-installe quand `bf_cx` et `bf_meeting` sont installés. À l'envoi
d'un compte rendu au client, demande de feedback à 3 émojis (module
rating) au partenaire du projet. Opt-in (`bf_cx.meeting_feedback`,
défaut désactivé) et garde-fous de sollicitation appliqués : cooldown
anti-sursollicitation par contact et drapeau par rencontre
(`bf_cx_feedback_requested`) pour qu'un renvoi de compte rendu ne
redéclenche pas de demande.
