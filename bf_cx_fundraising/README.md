# bf_cx_fundraising : sondage expérience donateur

S'auto-installe quand `bf_cx` et `bf_fundraising_core` sont installés.
Fonctionnalité produit pour les OBNL utilisateurs de la suite de
collecte de fonds (pas pour Blue Fox lui-même). À la validation d'un
don, envoie le sondage du programme désigné (`bf_cx.donor_program_id`,
vide = désactivé) au donateur. Une fois par don, garde-fous de
sollicitation appliqués. Un donateur peut donner souvent : la cadence
minimale du programme est la protection principale (90 jours
recommandés).
