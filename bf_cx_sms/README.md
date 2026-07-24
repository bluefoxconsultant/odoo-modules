# bf_cx_sms : invitation de sondage par SMS

S'auto-installe quand `bf_cx` et `bf_sms_archive` sont installés. Ajoute
le bouton « Inviter par SMS » sur les vagues d'envoi : les destinataires
sans adresse courriel mais avec un numéro reçoivent leur lien de sondage
personnel (jeton individuel) par SMS, sur la ligne configurée. Opt-in
(`bf_cx.sms_invite`, défaut désactivé), action manuelle seulement (aucun
cron), maximum 5 SMS par clic, garde-fous de sollicitation appliqués.
