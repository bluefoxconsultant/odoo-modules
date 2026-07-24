# bf_cx_helpdesk - pont Expérience client ↔ Helpdesk

S'auto-installe quand `bf_cx` et `helpdesk_mgmt` (OCA) sont installés.

- Équipe helpdesk « Plaintes » et canal « Expérience client » (données).
- Ticket depuis une plainte (lien bidirectionnel) et ticket de suivi
  depuis un feedback détracteur ; ticket automatique opt-in
  (`bf_cx.auto_ticket`, défaut désactivé).
- Garde-fou de sollicitation appliqué au sondage CSAT de fermeture de
  bf_helpdesk quand il est présent (défensif : aucune dépendance à
  bf_helpdesk).
