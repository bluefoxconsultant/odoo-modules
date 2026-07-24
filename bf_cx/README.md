# Expérience client (bf_cx)

Programme d'écoute client intégré à Odoo 18 Community : NPS, feedback
continu, plaintes et témoignages — sans licence externe.

## Écosystème

Six modules-ponts `auto_install` s'activent selon ce qui est installé :

| Pont | S'active avec | Apporte |
|---|---|---|
| `bf_cx_helpdesk` | helpdesk_mgmt | équipe Plaintes, tickets depuis plainte/détracteur, ticket auto optionnel |
| `bf_cx_privacy` | privacy_consent | consentement Loi 25 formel des témoignages, révocation propagée |
| `bf_cx_dashboard` | bf_dashboard | tuile NPS 30 j + détracteurs/plaintes à traiter |
| `bf_cx_meeting` | bf_meeting | demande de feedback 3 émojis après l'envoi d'un compte rendu (opt-in) |
| `bf_cx_digest` | daily_todo_digest | section « Expérience client » du digest quotidien |
| `bf_cx_crm` | crm | sondage « pourquoi » à la perte d'une opportunité (opt-in) |

## Garde-fous de sollicitation

Toute demande sortante — vagues, post-rencontre, post-perte, ET les
demandes d'évaluation du core (ratings de projets via le hook central
`rating_send_request`, CSAT de fermeture de tickets) — passe par
`res.partner._bf_cx_split_solicitable()` :

- **cooldown** par contact (`bf_cx.solicitation_cooldown_days`, défaut
  30 j ; surcharge par programme via `cooldown_days` — 90 j recommandé
  pour un NPS relationnel) avec estampille `bf_cx_last_solicited` (les
  rappels estampillent aussi) ;
- **liste noire courriel** (`mail.blacklist`) — les envois par
  `mail.template` la contourneraient sinon ;
- **recouvrement actif** (module de relances de factures Blue Fox, détecté à l'exécution via le champ `bf_followup_state`) :
  aucun « notez-nous » à un client en 2ᵉ rappel ou mise en demeure ;
- **liste « Ne pas contacter »** de `privacy_consent` (via le pont).

Les contacts reportés sont journalisés au chatter et **rattrapés par le
cron** à l'expiration du cooldown (un garde-fou diffère, il ne supprime
pas — sinon il biaise l'échantillon). Les programmes internes (360) sont
exempts : le budget de sollicitation est un concept client.

## Honnêteté statistique

Le NPS affiché (tableau de bord, digest, programmes) utilise une fenêtre
glissante configurable (`bf_cx.nps_window_days`, défaut 365) et est
**masqué sous 10 réponses** (« n insuffisant ») : en deçà, la marge
d'erreur dépasse ±20 points. Le n est toujours affiché à côté du score.

## Plaintes — ISO 10002

Accusé de réception réel (courriel au plaignant + date stockée + délai
calculé), alerte automatique au responsable quand l'échéance d'AR
approche, cause fondamentale et action corrective exigées avant
résolution, et **suivi de la satisfaction du plaignant après clôture**
(activité + champ dédié).

## Pulse et QR

Quand le sondage d'un programme est en accès public, le programme expose
l'URL permanente, un extrait HTML à coller dans les signatures et un QR
code téléchargeable (nécessite la lib Python `qrcode` dans le conteneur —
import paresseux : son absence ne bloque pas l'installation du module).

## Ce que fait le module

### Registre unifié des feedbacks
Tous les signaux mesurés atterrissent dans `bf.cx.feedback`, quel
que soit le canal :

- réponses aux sondages des programmes (hook `survey.user_input._mark_done`) ;
- évaluations par courriel du module core `rating` (projets, tickets…),
  ingérées à la consommation ;
- saisies manuelles (rencontre, téléphone).

Chaque entrée porte le type (NPS, CSAT, commentaire, interne 360), la note,
le verbatim, le programme/vague d'origine, le projet et le responsable du
suivi.

### Programmes et vagues NPS
Un **programme** relie un sondage Odoo (question « Échelle » 0-10) à une
intention de mesure. Les **vagues** envoient le sondage par lot : une
réponse à jeton individuel par contact (`_create_answer`), invitation par
gabarit de courriel, rappel automatique aux non-répondants (cron quotidien,
délai par programme). Le score NPS (% promoteurs − % détracteurs) est
calculé par programme et par vague. L'attribution de campagne (`utm.campaign`)
est portée par la vague — le lien sondage ↔ campagne n'existe pas dans le
core.

### Boucle fermée
Un détracteur (NPS ≤ 6) ou une note insatisfaite (< 3/5) crée
automatiquement une activité de suivi assignée au responsable du compte
(désactivable dans les paramètres). Les ponts peuvent étendre ce
comportement (ticket helpdesk).

### Plaintes
Registre autonome : numéro séquentiel (PLT####), gravité, échéance
d'accusé de réception (délai configurable), analyse de cause et action
corrective. Le pont `bf_cx_helpdesk` (auto-installé si
`helpdesk_mgmt` est présent) ajoute la création de ticket liée.

### Témoignages
Candidats détectés depuis les sondages (question d'opt-in), publication
bloquée tant qu'un consentement n'est pas consigné (verbal, écrit, ou
formel via `privacy_consent` avec le pont `bf_cx_privacy`).
La révocation (« Retirer ») rappelle où le témoignage est utilisé.

### Feedback interne (360)
Programmes de type « interne » : mêmes mécaniques de sondage, mais les
entrées sont réservées au groupe Gestionnaire (règle d'enregistrement).

## Architecture

- Aucune dépendance dure au helpdesk ni au module Vie privée : les liens
  vivent dans les modules-ponts `auto_install`
  (`bf_cx_helpdesk`, `bf_cx_privacy`).
- Le NPS ne passe PAS par `rating.rating` (contrainte SQL 0-5 du core) :
  il vit dans le registre du module, alimenté par `value_scale`.
- L'ingestion sondage est idempotente (verrou de ligne + dédoublonnage par
  réponse) : `_mark_done` peut être rappelé par le core.

## Sécurité

- `group_bf_cx_user` (Opérateur) : gère programmes, feedbacks,
  plaintes, témoignages ; ne voit pas le 360 interne.
- `group_bf_cx_manager` (Gestionnaire) : tout, y compris le 360 et
  la configuration.
- Multi-société sur les cinq modèles.
