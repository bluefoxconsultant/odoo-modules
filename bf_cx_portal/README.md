# bf_cx_portal : feedback au portail client

S'auto-installe quand `bf_cx` et `portal` sont installés. Ajoute la page
portail `/my/feedback` : le client connecté consulte les feedbacks de sa
société (date, type, note, commentaire; le feedback interne 360 est
exclu) et peut soumettre un commentaire libre, enregistré comme verbatim
(canal « Autre ») dans le registre unifié. Aucun envoi sortant. Lecture
bornée au partenaire commercial de l'utilisateur (contrôleur à domaine
strict + ACL lecture seule + règle d'enregistrement portail); à la
création, seul le texte du commentaire vient de l'utilisateur, tout le
reste est forcé côté serveur.
