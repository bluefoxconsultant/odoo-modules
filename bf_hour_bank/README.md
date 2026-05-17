# Banque d'heures (`bf_hour_bank`)

Module Odoo 18 pour le suivi automatis\u00e9 des banques d'heures client.

## Fonctionnalit\u00e9s

- **Configuration par client** : projets inclus, filtres sociétés/partenaires/produits, destinataires du rapport
- **Calcul automatique du solde** : d\u00e9bits (feuilles de temps) + cr\u00e9dits (factures) + ajustements manuels
- **Ajustements manuels** : cr\u00e9dits ou d\u00e9bits hors factures/feuilles de temps (refacturations, corrections, JV)
- **Rapport PDF** : Blue Fox branded avec banni\u00e8re, tableau des entr\u00e9es (cr\u00e9dits en vert), sommaire par projet, synth\u00e8se mensuelle
- **Rapport Excel** : 4 onglets (Feuilles de temps, Sommaire par projet, Synth\u00e8se par mois, \u00c0 facturer)
- **Envoi par courriel** : wizard avec PDF + Excel en pi\u00e8ces jointes, email balis\u00e9 Blue Fox
- **Pr\u00e9visualisation** : aper\u00e7u PDF directement depuis le wizard d'envoi
- **Envoi automatique** : cron configurable (hebdomadaire, aux deux semaines, mensuel) avec rapport balis\u00e9 envoy\u00e9 aux destinataires
- **Paliers de notification** : alertes courriel proactives quand la consommation franchit un seuil (heures non factur\u00e9es, % d'un budget allou\u00e9, ou solde sous un plancher) avec XLSX joint
- **Portail client** : page `/my/hour-banks` accessible aux utilisateurs portail, avec t\u00e9l\u00e9chargement PDF/Excel en libre-service

## D\u00e9pendances

- `project`, `account`, `hr_timesheet`, `mail`, `portal`
- `openpyxl` (Python, pour g\u00e9n\u00e9ration Excel)
- `bf_lexend` (police Lexend dans les PDF)

## Logique de calcul

```
D\u00e9bits   = feuilles de temps des projets configur\u00e9s (account.analytic.line)
Cr\u00e9dits  = lignes de factures client post\u00e9es (account.move.line)
           filtr\u00e9es par soci\u00e9t\u00e9 + partenaire + produit (optionnels)
Ajust.   = entr\u00e9es manuelles (positif = cr\u00e9dit, n\u00e9gatif = d\u00e9bit)

Solde = \u03a3 cr\u00e9dits + \u03a3 ajustements - \u03a3 d\u00e9bits
```

Les entr\u00e9es sont affich\u00e9es par date d\u00e9croissante (plus r\u00e9centes en premier) dans le PDF, Excel et portail.

### Filtres de facturation

Trois niveaux de filtrage ind\u00e9pendants sont disponibles dans l'onglet Facturation :

#### Filtre soci\u00e9t\u00e9s

| Mode | Comportement |
|------|-------------|
| **Toutes les soci\u00e9t\u00e9s** (d\u00e9faut) | Aucun filtrage par soci\u00e9t\u00e9 |
| **Inclure seulement** | Seules les factures des soci\u00e9t\u00e9s s\u00e9lectionn\u00e9es comptent |
| **Exclure** | Toutes les factures sauf celles des soci\u00e9t\u00e9s s\u00e9lectionn\u00e9es |

#### Filtre partenaires de facturation

Champ optionnel permettant de cibler des partenaires sp\u00e9cifiques au lieu du `commercial_partner_id` automatique. Utile quand un m\u00eame client commercial a plusieurs contacts de facturation (ex. : changement de soci\u00e9t\u00e9 interne). Si vide, le comportement par d\u00e9faut (toutes les factures du partenaire commercial) est conserv\u00e9.

#### Filtre produits

| Mode | Comportement |
|------|-------------|
| **Toutes les lignes** (d\u00e9faut) | Toutes les lignes de facture du client sont incluses |
| **Inclure seulement** | Seules les lignes avec les produits list\u00e9s comptent |
| **Exclure** | Toutes les lignes sauf celles avec les produits list\u00e9s |

### Colonnes du rapport

| Colonne | Description |
|---------|-------------|
| Date | Date de l'op\u00e9ration |
| Nb d'heures | Heures (n\u00e9gatif = d\u00e9bit, positif = cr\u00e9dit) |
| Solde cumulatif | Balance cumulative \u00e0 cette date |
| Description | Nom de la ligne de temps ou num\u00e9ro de facture |
| Projet | Nom du projet ou "Heures factur\u00e9es" / "Ajustement" |
| T\u00e2che | Nom de la t\u00e2che (feuilles de temps uniquement) |

## Structure

```
bf_hour_bank/
\u251c\u2500\u2500 models/
\u2502   \u251c\u2500\u2500 hour_bank_client.py            # Configuration + g\u00e9n\u00e9ration rapports + paliers
\u2502   \u251c\u2500\u2500 hour_bank_adjustment.py        # Ajustements manuels
\u2502   \u251c\u2500\u2500 hour_bank_threshold_line.py    # Configuration des paliers
\u2502   \u2514\u2500\u2500 hour_bank_threshold_event.py   # Historique append-only des alertes
\u251c\u2500\u2500 wizard/
\u2502   \u2514\u2500\u2500 hour_bank_send_wizard.py       # Envoi par courriel (branded)
\u251c\u2500\u2500 controllers/
\u2502   \u2514\u2500\u2500 portal.py                      # Portail client (/my/hour-banks)
\u251c\u2500\u2500 report/
\u2502   \u251c\u2500\u2500 hour_bank_paperformat.xml      # Format papier US Letter
\u2502   \u2514\u2500\u2500 hour_bank_report_templates.xml # Template QWeb PDF
\u251c\u2500\u2500 views/
\u2502   \u251c\u2500\u2500 hour_bank_client_views.xml     # Formulaire, liste, recherche
\u2502   \u251c\u2500\u2500 hour_bank_threshold_views.xml  # Vues pour hour.bank.threshold.event
\u2502   \u251c\u2500\u2500 hour_bank_portal_templates.xml # Pages portail
\u2502   \u2514\u2500\u2500 menu_views.xml                 # Menu sous Projet
\u251c\u2500\u2500 data/
\u2502   \u251c\u2500\u2500 hour_bank_mail_template.xml
\u2502   \u2514\u2500\u2500 hour_bank_cron.xml             # Crons : rapports p\u00e9riodiques + paliers
\u251c\u2500\u2500 security/
\u2502   \u251c\u2500\u2500 hour_bank_security.xml         # R\u00e8gles d'acc\u00e8s (interne + portail)
\u2502   \u2514\u2500\u2500 ir.model.access.csv
\u251c\u2500\u2500 tests/
\u2502   \u2514\u2500\u2500 test_thresholds.py             # 10 tests unitaires des paliers
\u2514\u2500\u2500 i18n/
    \u2514\u2500\u2500 fr_CA.po
```

## Acc\u00e8s

### Backend (interne)
- **Projet > Banque d'heures > Clients**
- Lecture : `project.group_project_user`
- Gestion compl\u00e8te : `project.group_project_manager`

### Portail client
- **Mon compte > Banque d'heures** (`/my/hour-banks`)
- Acc\u00e8s : `base.group_portal` (restreint au `commercial_partner_id` du client)
- Routes disponibles :
  - `/my/hour-banks` \u2014 liste des banques d'heures
  - `/my/hour-banks/<id>` \u2014 d\u00e9tail avec tableau, solde, sommaire par projet
  - `/my/hour-banks/<id>/pdf` \u2014 t\u00e9l\u00e9chargement PDF
  - `/my/hour-banks/<id>/xlsx` \u2014 t\u00e9l\u00e9chargement Excel

## Envoi automatique (cron)

Le cron `Banque d'heures : Envoi automatique des rapports` s'ex\u00e9cute quotidiennement \u00e0 08h00 et envoie les rapports selon la fr\u00e9quence configur\u00e9e :

| Fr\u00e9quence | D\u00e9clenchement |
|-----------|-------------|
| Hebdomadaire | Chaque lundi |
| Aux deux semaines | Lundis des semaines ISO paires |
| Mensuel | 1er du mois |

## Paliers de notification

Onglet **Paliers** sur la fiche de banque. Trois modes mutuellement exclusifs, d\u00e9sactiv\u00e9s par d\u00e9faut.

### Modes

| Mode | Mesure | R\u00e9armement |
|------|--------|------------|
| **Heures non factur\u00e9es** | Somme des d\u00e9bits depuis la derni\u00e8re facture post\u00e9e du client | Nouvelle facture post\u00e9e |
| **% du budget allou\u00e9** | `heures non factur\u00e9es / budget allou\u00e9 \u00d7 100` | Modification de `Budget allou\u00e9 (h)` sur la banque |
| **Solde r\u00e9siduel sous seuil** | Solde courant cumulatif | Remont\u00e9e du solde au-dessus de `seuil + 0.5h` (hyst\u00e9r\u00e9sis) |

### Configuration

1. Choisir le **Mode de palier**
2. Si `% du budget` : renseigner **Budget allou\u00e9 (h)**
3. Ajouter une ou plusieurs lignes de **Paliers \u00e0 surveiller** (champ `value` \u2014 heures ou pourcentage selon mode)
4. **Destinataires des alertes** : laisser vide pour r\u00e9utiliser les destinataires du rapport p\u00e9riodique, ou renseigner un Many2many distinct pour des destinataires d'alerte sp\u00e9cifiques
5. **Notifier les followers internes** (d\u00e9faut activ\u00e9) : poste aussi un `message_notify` sur le chatter pour avertir les followers internes de la banque

### D\u00e9clenchement

- Cron **`Banque d'heures : V\u00e9rifier les paliers de notification`** quotidien \u00e0 08h30 UTC
- Bouton manuel **\u00ab V\u00e9rifier les paliers maintenant \u00bb** dans l'en-t\u00eate du formulaire
- Pour chaque ligne active : si la mesure courante atteint le seuil ET que la ligne est arm\u00e9e (cl\u00e9 de p\u00e9riode diff\u00e9rente du dernier d\u00e9clenchement), un courriel branded est envoy\u00e9 avec le XLSX en pi\u00e8ce jointe

### Audit

Chaque d\u00e9clenchement cr\u00e9e un enregistrement `hour.bank.threshold.event` (append-only) avec snapshot du mode, valeur du palier, valeur mesur\u00e9e, cl\u00e9 de p\u00e9riode, destinataires, pi\u00e8ce jointe XLSX et lien vers le message chatter. Smart button **\u00ab Alertes envoy\u00e9es \u00bb** sur le formulaire ouvre la liste filtr\u00e9e.

### Comportement \u00e0 la mise en place

Si vous activez les paliers sur une banque d\u00e9j\u00e0 au-del\u00e0 de plusieurs seuils, **tous les paliers cross\u00e9s se d\u00e9clenchent \u00e0 la prochaine v\u00e9rification** (la cascade est correcte logiquement mais peut \u00eatre bruyante). Pour \u00e9viter \u00e7a lors d'une configuration mid-mandat : ajouter d'abord les paliers en `active=False`, ou pr\u00e9voir d'absorber le batch initial dans le cron du lendemain.

### Effet \u00e0 l'installation/mise \u00e0 jour

L'installation ou la mise \u00e0 jour du module **ne cr\u00e9e aucun rappel, aucune activit\u00e9, aucun courriel** sur les banques existantes : le `threshold_mode` d\u00e9faut est `disabled` et le cron filtre d\u00e9j\u00e0 sur `threshold_mode != 'disabled'`. Pour activer la fonctionnalit\u00e9, l'op\u00e9rateur doit configurer chaque banque manuellement.

## Installation

```bash
docker exec <container> odoo -d <db> -i bf_hour_bank --stop-after-init --no-http
```
