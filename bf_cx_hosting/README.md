# bf_cx_hosting : CSAT post-maintenance

S'auto-installe quand `bf_cx` et `hosting_management` sont installés.
Quand une maintenance planifiée touchant un service client est marquée
faite, demande de feedback à 3 émojis (module rating) au client du
service. Opt-in (`bf_cx.hosting_feedback`, défaut désactivé), garde-fous
de sollicitation appliqués, partenaires internes exclus. Les
planifications étant récurrentes, l'indicateur d'envoi est réinitialisé à
chaque nouvelle occurrence : un envoi possible par cycle de maintenance,
encadré par le garde-fou anti-sursollicitation. Courriel brandé bilingue
(hook i18n partagé de `bf_cx`) avec lien de désabonnement.
