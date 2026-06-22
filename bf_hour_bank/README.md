# Banque d'heures (`bf_hour_bank`)

Module Odoo 18 pour le suivi automatisé des banques d'heures client.

## Fonctionnalités

- **Configuration par client** : projets inclus, filtres sociétés/partenaires/produits, destinataires du rapport
- **Calcul automatique du solde** : débits (feuilles de temps) + crédits (factures) + ajustements manuels
- **Ajustements manuels** : crédits ou débits hors factures/feuilles de temps (refacturations, corrections, JV)
- **Rapport PDF** : Blue Fox branded avec bannière, tableau des entrées (crédits en vert), sommaire par projet, synthèse mensuelle
- **Rapport Excel** : 4 onglets (Feuilles de temps, Sommaire par projet, Synthèse par mois, À facturer)
- **Envoi par courriel** : wizard avec PDF + Excel en pièces jointes, email balisé Blue Fox
- **Prévisualisation** : aperçu PDF directement depuis le wizard d'envoi
- **Envoi automatique** : cron configurable (hebdomadaire, aux deux semaines, mensuel) avec rapport balisé envoyé aux destinataires
- **Paliers de notification** : alertes courriel proactives quand la consommation franchit un seuil (heures non facturées, % d'un budget alloué, ou solde sous un plancher) avec XLSX joint
- **Portail client** : page `/my/hour-banks` accessible aux utilisateurs portail, avec téléchargement PDF/Excel en libre-service

## Dépendances

- `project`, `account`, `hr_timesheet`, `mail`, `portal`
- `bluefox_branding` (en-tête et palette de marque des rapports)
- `bf_onboarding_base` (panneau d'accueil guidé)
- `openpyxl` (Python, pour génération Excel)

## Logique de calcul

```
Débits   = feuilles de temps des projets configurés (account.analytic.line)
Crédits  = lignes de factures client postées (account.move.line)
           filtrées par société + partenaire + produit (optionnels)
Ajust.   = entrées manuelles (positif = crédit, négatif = débit)

Solde = Σ crédits + Σ ajustements - Σ débits
```

Les entrées sont affichées par date décroissante (plus récentes en premier) dans le PDF, Excel et portail.

### Filtres de facturation

Trois niveaux de filtrage indépendants sont disponibles dans l'onglet Facturation :

#### Filtre sociétés

| Mode | Comportement |
|------|-------------|
| **Toutes les sociétés** (défaut) | Aucun filtrage par société |
| **Inclure seulement** | Seules les factures des sociétés sélectionnées comptent |
| **Exclure** | Toutes les factures sauf celles des sociétés sélectionnées |

#### Filtre partenaires de facturation

Champ optionnel permettant de cibler des partenaires spécifiques au lieu du `commercial_partner_id` automatique. Utile quand un même client commercial a plusieurs contacts de facturation (ex. : changement de société interne). Si vide, le comportement par défaut (toutes les factures du partenaire commercial) est conservé.

#### Filtre produits

| Mode | Comportement |
|------|-------------|
| **Toutes les lignes** (défaut) | Toutes les lignes de facture du client sont incluses |
| **Inclure seulement** | Seules les lignes avec les produits listés comptent |
| **Exclure** | Toutes les lignes sauf celles avec les produits listés |

### Colonnes du rapport

| Colonne | Description |
|---------|-------------|
| Date | Date de l'opération |
| Nb d'heures | Heures (négatif = débit, positif = crédit) |
| Solde cumulatif | Balance cumulative à cette date |
| Description | Nom de la ligne de temps ou numéro de facture |
| Projet | Nom du projet ou "Heures facturées" / "Ajustement" |
| Tâche | Nom de la tâche (feuilles de temps uniquement) |

## Structure

```
bf_hour_bank/
├── models/
│   ├── hour_bank_client.py            # Configuration + génération rapports + paliers
│   ├── hour_bank_adjustment.py        # Ajustements manuels
│   ├── hour_bank_threshold_line.py    # Configuration des paliers
│   └── hour_bank_threshold_event.py   # Historique append-only des alertes
├── wizard/
│   └── hour_bank_send_wizard.py       # Envoi par courriel (branded)
├── controllers/
│   └── portal.py                      # Portail client (/my/hour-banks)
├── report/
│   ├── hour_bank_paperformat.xml      # Format papier US Letter
│   └── hour_bank_report_templates.xml # Template QWeb PDF
├── views/
│   ├── hour_bank_client_views.xml     # Formulaire, liste, recherche
│   ├── hour_bank_threshold_views.xml  # Vues pour hour.bank.threshold.event
│   ├── hour_bank_portal_templates.xml # Pages portail
│   └── menu_views.xml                 # Menu sous Projet
├── data/
│   ├── hour_bank_mail_template.xml
│   └── hour_bank_cron.xml             # Crons : rapports périodiques + paliers
├── security/
│   ├── hour_bank_security.xml         # Règles d'accès (interne + portail)
│   └── ir.model.access.csv
├── tests/
│   └── test_thresholds.py             # 10 tests unitaires des paliers
└── i18n/
    └── fr_CA.po
```

## Accès

### Backend (interne)
- **Projet > Banque d'heures > Clients**
- Lecture : `project.group_project_user`
- Gestion complète : `project.group_project_manager`

### Portail client
- **Mon compte > Banque d'heures** (`/my/hour-banks`)
- Accès : `base.group_portal` (restreint au `commercial_partner_id` du client)
- Routes disponibles :
  - `/my/hour-banks` — liste des banques d'heures
  - `/my/hour-banks/<id>` — détail avec tableau, solde, sommaire par projet
  - `/my/hour-banks/<id>/pdf` — téléchargement PDF
  - `/my/hour-banks/<id>/xlsx` — téléchargement Excel

## Envoi automatique (cron)

Le cron `Banque d'heures : Envoi automatique des rapports` s'exécute quotidiennement à 08h00 et envoie les rapports selon la fréquence configurée :

| Fréquence | Déclenchement |
|-----------|-------------|
| Hebdomadaire | Chaque lundi |
| Aux deux semaines | Lundis des semaines ISO paires |
| Mensuel | 1er du mois |

## Paliers de notification

Onglet **Paliers** sur la fiche de banque. Trois modes mutuellement exclusifs, désactivés par défaut.

### Modes

| Mode | Mesure | Réarmement |
|------|--------|------------|
| **Heures non facturées** | Somme des débits depuis la dernière facture postée du client | Nouvelle facture postée |
| **% du budget alloué** | `heures non facturées / budget alloué × 100` | Modification de `Budget alloué (h)` sur la banque |
| **Solde résiduel sous seuil** | Solde courant cumulatif | Remontée du solde au-dessus de `seuil + 0.5h` (hystérésis) |

### Configuration

1. Choisir le **Mode de palier**
2. Si `% du budget` : renseigner **Budget alloué (h)**
3. Ajouter une ou plusieurs lignes de **Paliers à surveiller** (champ `value` — heures ou pourcentage selon mode)
4. **Destinataires des alertes** : laisser vide pour réutiliser les destinataires du rapport périodique, ou renseigner un Many2many distinct pour des destinataires d'alerte spécifiques
5. **Notifier les followers internes** (défaut activé) : poste aussi un `message_notify` sur le chatter pour avertir les followers internes de la banque

### Déclenchement

- Cron **`Banque d'heures : Vérifier les paliers de notification`** quotidien à 08h30 UTC
- Bouton manuel **« Vérifier les paliers maintenant »** dans l'en-tête du formulaire
- Pour chaque ligne active : si la mesure courante atteint le seuil ET que la ligne est armée (clé de période différente du dernier déclenchement), un courriel branded est envoyé avec le XLSX en pièce jointe

### Audit

Chaque déclenchement crée un enregistrement `hour.bank.threshold.event` (append-only) avec snapshot du mode, valeur du palier, valeur mesurée, clé de période, destinataires, pièce jointe XLSX et lien vers le message chatter. Smart button **« Alertes envoyées »** sur le formulaire ouvre la liste filtrée.

### Comportement à la mise en place

Si vous activez les paliers sur une banque déjà au-delà de plusieurs seuils, **tous les paliers crossés se déclenchent à la prochaine vérification** (la cascade est correcte logiquement mais peut être bruyante). Pour éviter ça lors d'une configuration mid-mandat : ajouter d'abord les paliers en `active=False`, ou prévoir d'absorber le batch initial dans le cron du lendemain.

### Effet à l'installation/mise à jour

L'installation ou la mise à jour du module **ne crée aucun rappel, aucune activité, aucun courriel** sur les banques existantes : le `threshold_mode` défaut est `disabled` et le cron filtre déjà sur `threshold_mode != 'disabled'`. Pour activer la fonctionnalité, l'opérateur doit configurer chaque banque manuellement.

## Installation

```bash
docker exec <container> odoo -d <db> -i bf_hour_bank --stop-after-init --no-http
```
