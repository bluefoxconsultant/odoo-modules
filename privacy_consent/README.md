# Suivi des consentements (Loi 25)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](https://mariadb.com/bsl11/)

Module Odoo 18 CE pour la gestion de la vie privée conformément à la **Loi 25** du Québec sur la protection des renseignements personnels : consentements, destruction documentaire et anonymisation.

Depuis la **v18.0.4.0.0**, le moteur est **multi-cadres** : la Loi 25 est intégrée par défaut, et des modules compagnons facultatifs ajoutent le **RGPD/GDPR (UE)**, le **UK GDPR**, la **LPRPDE/PIPEDA (Canada)** et le **Privacy Act 2020 (Nouvelle-Zélande)**.

---

## Table des matières

- [Aperçu](#aperçu)
- [Documentation](#documentation)
- [Fonctionnalités](#fonctionnalités)
  - [Consentements](#gestion-des-consentements)
  - [Destruction documentaire](#destruction-et-anonymisation-documentaire-v1800300)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Architecture technique](#architecture-technique)
- [Sécurité et conformité](#sécurité-et-conformité)
- [Portail client](#portail-client)
- [Automatisations](#automatisations)
- [Dépendances](#dépendances)
- [Licence](#licence)
- [Support](#support)

---

## Aperçu

La **Loi 25** (anciennement projet de loi 64) modernise le cadre juridique québécois en matière de protection des renseignements personnels. Elle impose aux organisations de nouvelles obligations, notamment :

- Obtenir un **consentement manifeste, libre, éclairé et spécifique** pour chaque finalité
- Présenter les demandes de consentement en **langage clair et simple**
- Documenter et **tracer** tous les consentements obtenus
- Permettre le **retrait** du consentement à tout moment
- Gérer les **expirations** et renouvellements

Ce module fournit :

**Consentements** : un registre unifié reliant personne concernee, finalite, contexte et preuve, avec historique inviolable et automatisations.

**Destruction et anonymisation** (v18.0.3.0.0) : calendrier de conservation par type de document, classification des renseignements personnels, registre de destruction immuable (Art. 3.2 LPRPSP), campagnes de destruction en lot, evaluations d'anonymisation selon les 3 criteres du Reglement A-2.1, r. 0.1, et droit a l'effacement (Art. 28.1 LPRPSP).

**Cadres réglementaires multiples** (v18.0.4.0.0) : un enregistrement `privacy.framework` porte les faits statutaires (autorité de surveillance, titre du responsable, âge du consentement, délais de déclaration d'incident, droits des personnes concernées, citations légales). Chaque société choisit son cadre par défaut, surchargeable par enregistrement (consentement, avis, calendrier de conservation, évaluation). Les courriels et certificats s'adaptent automatiquement au cadre applicable. La **Loi 25** est intégrée ; le **GDPR**, le **UK GDPR**, la **LPRPDE/PIPEDA** et le **Privacy Act 2020 (NZ)** s'ajoutent via des modules compagnons `privacy_framework_*` (voir [Dépendances](#dépendances)).

---

## Documentation

### Manuel d'utilisation

Un **manuel d'utilisation complet** en français est disponible pour les utilisateurs finaux :

📖 **[Manuel d'utilisation (Français)](doc/MANUEL_UTILISATEUR.md)**

Ce manuel couvre :

- **Navigation** : Structure des menus et accès selon les rôles
- **Tableau de bord** : Indicateurs clés et actions rapides
- **Opérations** : Gestion des consentements, demandes en attente, destructions
- **Configuration** : Finalités, avis, préférences, politiques de rétention, séquences de courriels, DocuSeal
- **Portail client** : Accès et fonctionnalités pour les clients
- **Intégrations** : Contacts, projets, marketing
- **Cycle de vie** : Diagramme d'états complet avec transitions
- **Preuves et traçabilité** : Types de preuves et données médico-légales
- **Automatisations** : Tâches cron et activités automatiques
- **Rôles et permissions** : Niveaux d'accès (Utilisateur, Gestionnaire, Responsable)
- **Conformité légale** : Loi 25, RGPD
- **Glossaire** : Définitions des termes clés

---

## Fonctionnalités

### Gestion des finalités (Purposes)

- Définition de finalités avec code unique et description en langage clair
- Configuration du type de consentement requis (express opt-in ou implicite)
- Durée de validité par défaut configurable
- Portée par canal (email, SMS, téléphone, vidéo, présentiel)
- Portée par contexte (projet, marketing, réunion, CRM)

**Finalités incluses par défaut (18) :**

*Finalités générales (consultation, hébergement, marketing) :*

| Code | Finalité | Opt-in express | Validité par défaut |
|------|----------|----------------|---------------------|
| `marketing` | Communications marketing et infolettres | Oui | 730 jours |
| `recording` | Enregistrement ponctuel de rencontres | Oui | 365 jours |
| `recording_audio` | Enregistrement audio | Oui | 365 jours |
| `transcription` | Transcription des communications | Oui | 365 jours |
| `training` | Formation interne | Oui | 365 jours |
| `reference` | Utilisation comme référence client | Non | 1095 jours (3 ans) |
| `logo` | Utilisation du logo | Non | 1095 jours (3 ans) |
| `case_study` | Étude de cas | Oui | 1825 jours (5 ans) |
| `service` | Communications de service | Consentement non requis | Illimité |
| `third_party` | Partage avec des tiers | Non | 365 jours |
| `agent` | Installation d'agent logiciel (LCAP/CASL) | Oui | Illimité (durée du mandat) |
| `sensibles` | Traitements à risque élevé et données sensibles | Oui | 365 jours |

*Finalités sectorielles — services de garde (CPE) :*

| Code | Finalité | Opt-in express | Validité par défaut |
|------|----------|----------------|---------------------|
| `medicaments` | Administration de médicaments | Oui | 365 jours |
| `sorties` | Sorties éducatives et excursions | Oui | 365 jours |
| `baignades` | Baignades et activités aquatiques | Oui | 365 jours |
| `transport` | Transport des enfants | Oui | 365 jours |
| `depart` | Personnes autorisées à récupérer l'enfant | Non | 365 jours |
| `surveillance` | Vidéosurveillance des locaux | Consentement non requis | Illimité (enregistrements conservés 30 j) |

> Les finalités sont **extensibles** : chaque organisation peut en ajouter, en modifier ou en désactiver selon son secteur. Les six dernières sont des modèles sectoriels pour les services de garde (CPE).

### Gestion des avis (Notices)

- Création de modèles d'avis bilingues (français/anglais)
- **Versionnage automatique** avec empreinte SHA256
- Traçabilité complète : quelle version a été présentée à quel moment
- Impossibilité de modifier une version déjà utilisée (immutabilité)

### Enregistrement des consentements

- Workflow complet : Brouillon → En attente → Accordé/Refusé → Retiré/Expiré
- Lien avec le **contact** (personne concernée)
- Lien optionnel avec un **représentant** (pour les mineurs < 14 ans)
- Lien contextuel avec un **projet** ou autre enregistrement
- Méthode de collecte traçable (portail, email, signature, verbal, importation)
- Horodatage de chaque changement d'état
- **Chatter intégré** pour l'historique complet

### Gestion des preuves (Evidence)

- Pièces jointes (PDF signé, capture d'écran, document)
- Notes de confirmation verbale
- Métadonnées techniques (adresse IP, user agent) pour le portail
- Traçabilité : qui a collecté, quand, comment

### Préférences de contact

- Gestion granulaire par canal :
  - Email de service / Email marketing
  - Téléphone / SMS
- Indicateur **Ne pas contacter** (coupe-circuit global)
- Langue préférée et heures de contact préférées
- Motif d'opt-out catégorisé
- Historique des modifications via chatter

### Destruction et anonymisation documentaire (v18.0.3.0.0)

#### Calendrier de conservation

- Regles de conservation par type de document (contrats, factures, dossiers RH, projets, etc.)
- Base legale obligatoire pour chaque regle (ex: Art. 2925 C.c.Q.)
- Periodes de conservation active et semi-active en annees
- Disposition finale configurable : detruire, anonymiser, archiver en permanence, transferer
- Revision annuelle integree avec suivi des dates

**Regles incluses par defaut :**

| Code | Type de document | Conservation | Base legale |
|------|-----------------|--------------|-------------|
| `CTR-001` | Contrats | 6 ans | Art. 2925 C.c.Q. |
| `FIN-001` | Factures et documents fiscaux | 7 ans (6+1) | Loi sur l'administration fiscale |
| `RH-001` | Dossiers employes | 5 ans (3+2) | Normes du travail |
| `PRJ-001` | Dossiers de projet | 5 ans | Art. 2925 C.c.Q. |
| `COR-001` | Correspondance | 3 ans | Pratique |
| `MED-001` | Documents medicaux | 7 ans | Regl. dossiers de sante (LSST) |
| `SEC-001` | Identifiants et mots de passe | 0 an | Securite |
| `CST-001` | Registres de consentement | 3 ans | Loi 25 |

#### Classification documentaire

- Classifie n'importe quel enregistrement Odoo avec ses categories de RP
- 10 categories de renseignements personnels (identification, medical, financier, biometrique, etc.)
- 4 niveaux de sensibilite (public, interne, confidentiel, hautement confidentiel)
- Identifiants directs et indirects
- Date d'expiration de retention calculee automatiquement
- **Liste blanche de modeles** : seuls les modeles pouvant contenir des RP peuvent etre classifies (securite)

#### Registre de destruction (immuable)

- Registre de destruction conforme a l'article 3.2 LPRPSP
- **Immutabilite totale** : aucune modification (sauf notes) ni suppression possible
- **Chaine SHA-256** : chaque entree integre l'empreinte de l'entree precedente (hash chaine) — toute alteration ou suppression d'un maillon rompt la chaine et devient detectable
- **Cron de verification d'integrite** : parcourt le registre dans l'ordre et signale toute empreinte rompue (v18.0.3.1)
- Numerotation automatique (REG-YYYY-NNNNN)
- Lien avec les demandes de destruction et les campagnes
- Double protection : Python (`write()`/`unlink()` overrides) + regles d'enregistrement ORM

#### Campagnes de destruction en lot

- Workflow complet : Brouillon -> Balayage -> Revision -> Approbation -> Execution -> Terminee
- Balayage automatique des documents depasses selon le calendrier de conservation
- Execution par ligne avec gestion des erreurs individuelle (pas d'abandon global)
- Creation automatique d'entrees au registre de destruction pour chaque document detruit
- Possibilite d'ignorer des documents individuellement

#### Evaluations d'anonymisation (Reglement A-2.1, r. 0.1)

- Evaluation des 3 criteres du Reglement sur l'anonymisation (mai 2024) :
  1. **Individualisation** : peut-on isoler une personne?
  2. **Correlation** : peut-on relier des jeux de donnees?
  3. **Inference** : peut-on deduire des RP?
- Risque global calcule automatiquement (le plus eleve des 3)
- Determination automatique si les donnees sont effectivement anonymes
- Reevaluations periodiques programmees avec alerte automatique
- Chaine de reevaluation (parent/enfant)

#### Droit a l'effacement (Art. 28.1 LPRPSP)

- Action serveur depuis la fiche contact : « Demander l'effacement des donnees »
- Creation automatique d'une demande de destruction avec toutes les classifications du contact
- Destruction securisee des identifiants (overwrite cryptographique)
- Creation d'activite pour la suppression manuelle du dossier Nextcloud

### Intégration aux Contacts

- Nouvel onglet **« Vie privée (Loi 25) »** dans la fiche contact
- **Badges visuels** : Marketing ✓/✗, Enregistrement ✓/✗, Référence ✓/✗
- Liste des consentements actifs
- Boutons d'action rapide :
  - Demander un consentement
  - Voir/modifier les préférences

### Intégration aux Projets

- Nouvel onglet **« Consentements »** dans la fiche projet
- Indicateur de statut global (Aucun / En attente / Partiel / Complet)
- Liste des consentements liés au projet
- Bouton pour demander des consentements aux contacts du projet

### Portail client (Preference Center)

- Page **« Mes préférences de confidentialité »** accessible à `/my/privacy/preferences`
- Gestion autonome des préférences de communication
- Historique des consentements
- Réponse aux demandes de consentement en attente
- Interface bilingue français/anglais

---

## Installation

### Prérequis

- Odoo 18.0 Community Edition
- Modules dépendants : `base`, `mail`, `project`, `portal`, `bluefox_branding`

### Procédure

1. **Copier le module** dans votre répertoire `addons` :
   ```bash
   cp -r privacy_consent /path/to/odoo/addons/
   ```

2. **Redémarrer Odoo** :
   ```bash
   ./odoo-bin -c odoo.conf -u base
   ```

3. **Installer le module** :
   - Aller dans *Applications*
   - Cliquer sur *Mettre à jour la liste des applications*
   - Rechercher « Suivi des consentements » ou « privacy_consent »
   - Cliquer sur *Installer*

---

## Configuration

### 1. Configurer les finalités

Accéder à **Privacy > Configuration > Finalités**

Pour chaque finalité, définir :
- **Code** : identifiant technique unique
- **Nom** : libellé affiché
- **Résumé en langage clair** : texte présenté aux personnes concernées
- **Consentement requis** : oui/non
- **Opt-in express requis** : pour les finalités sensibles
- **Validité par défaut** : nombre de jours (0 = illimité)

### 2. Créer les avis de consentement

Accéder à **Privacy > Configuration > Avis**

Pour chaque avis :
1. Associer une finalité
2. Rédiger le contenu en français et en anglais
3. Cliquer sur **« Créer une nouvelle version »**

### 3. Configurer les groupes de securite

| Groupe | Acces |
|--------|-------|
| **Privacy User** | Lecture des consentements, classifications, registre |
| **Privacy Manager** | CRUD sur consentements, classifications, campagnes. Peut creer des demandes de destruction |
| **Privacy Officer** | Administration complete. Peut approuver et executer les destructions et evaluations |

Les utilisateurs sont assignes aux groupes via *Parametres > Utilisateurs*.

---

## Utilisation

### Demander un consentement

**Depuis un contact :**
1. Ouvrir la fiche contact
2. Aller à l'onglet « Vie privée (Loi 25) »
3. Cliquer sur **« Demander un consentement »**
4. Sélectionner la finalité et l'avis
5. Choisir si un email doit être envoyé
6. Valider

**Depuis le menu Privacy :**
1. Aller à **Privacy > Operations > Consentements**
2. Cliquer sur **Créer**
3. Remplir les informations et enregistrer
4. Cliquer sur **« Envoyer la demande »**

### Accorder un consentement

- Depuis le **portail client** : le contact répond directement
- Depuis le **backend** : un utilisateur peut cliquer sur « Accorder »
- La date d'expiration est calculée automatiquement

### Retirer un consentement

1. Ouvrir le consentement accordé
2. Cliquer sur **« Retirer »**
3. Sélectionner le motif de retrait
4. Optionnellement, mettre à jour les préférences de contact
5. Valider

### Consulter l'historique

Chaque consentement dispose d'un **chatter** affichant :
- Les changements de statut
- Les emails envoyés
- Les notes ajoutées
- Les modifications de dates

---

## Architecture technique

### Modeles de donnees

**Consentements :**
```
privacy.purpose               # Finalites de consentement
privacy.notice                # Modeles d'avis
privacy.notice.version        # Versions immutables avec hash SHA256
privacy.consent               # Enregistrements de consentement (mail.thread)
privacy.consent.evidence      # Preuves et pieces jointes
privacy.contact.preference    # Preferences de communication
privacy.consent.group         # Groupes de consentement
privacy.dashboard             # Tableau de bord avec KPIs (transient)
```

**Destruction et anonymisation :**
```
privacy.retention.policy             # Politiques de retention (par consentement)
privacy.retention.calendar           # Calendrier de conservation (par type de document)
privacy.document.classification      # Classification documentaire (RP)
privacy.destruction.request          # Demandes de destruction (mail.thread)
privacy.destruction.register         # Registre de destruction immuable
privacy.destruction.campaign         # Campagnes de destruction en lot (mail.thread)
privacy.destruction.campaign.line    # Lignes de campagne
privacy.anonymization.assessment     # Evaluations d'anonymisation (mail.thread)
```

**Signatures electroniques :**
```
privacy.docuseal.config        # Configuration DocuSeal
privacy.docuseal.template      # Modeles DocuSeal
privacy.libresign.config       # Configuration LibreSign
privacy.libresign.template     # Modeles LibreSign
```

**Extensions :**
```
res.partner              # Onglet Privacy + badges + compteurs
project.project          # Onglet Consentements + statut global
```

### Structure des fichiers

```
privacy_consent/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── portal.py
│   ├── docuseal_webhook.py
│   └── libresign_webhook.py
├── data/
│   ├── mail_template.xml
│   ├── mail_template_sequence.xml
│   ├── mail_activity_type.xml
│   ├── privacy_cron.xml
│   ├── privacy_retention_cron.xml
│   ├── privacy_retention_calendar_data.xml
│   ├── privacy_destruction_register_cron.xml
│   ├── privacy_purpose_data.xml
│   └── privacy_notice_data.xml
├── doc/
│   └── MANUEL_UTILISATEUR.md
├── models/
│   ├── mail_blacklist.py
│   ├── privacy_consent.py
│   ├── privacy_consent_evidence.py
│   ├── privacy_consent_group.py
│   ├── privacy_contact_preference.py
│   ├── privacy_notice.py
│   ├── privacy_notice_version.py
│   ├── privacy_purpose.py
│   ├── privacy_dashboard.py
│   ├── privacy_retention.py
│   ├── privacy_retention_calendar.py
│   ├── privacy_document_classification.py
│   ├── privacy_destruction.py
│   ├── privacy_destruction_register.py
│   ├── privacy_destruction_campaign.py
│   ├── privacy_anonymization_assessment.py
│   ├── privacy_email_sequence.py
│   ├── privacy_docuseal_config.py
│   ├── privacy_docuseal_interface.py
│   ├── privacy_docuseal_template.py
│   ├── privacy_libresign_config.py
│   ├── privacy_libresign_interface.py
│   ├── privacy_libresign_template.py
│   ├── project_project.py
│   └── res_partner.py
├── report/
│   ├── privacy_destruction_certificate.xml
│   └── privacy_consent_certificate.xml
├── security/
│   ├── ir.model.access.csv          # 55 ACLs
│   └── privacy_security.xml         # 3 groupes, 14 regles d'enregistrement
├── views/
│   ├── menu_views.xml
│   ├── portal_templates.xml
│   ├── privacy_consent_views.xml
│   ├── privacy_consent_group_views.xml
│   ├── privacy_dashboard_views.xml
│   ├── privacy_destruction_views.xml
│   ├── privacy_destruction_register_views.xml
│   ├── privacy_destruction_campaign_views.xml
│   ├── privacy_anonymization_assessment_views.xml
│   ├── privacy_retention_views.xml
│   ├── privacy_retention_calendar_views.xml
│   ├── privacy_document_classification_views.xml
│   ├── privacy_email_sequence_views.xml
│   ├── privacy_docuseal_views.xml
│   ├── privacy_libresign_views.xml
│   ├── privacy_evidence_views.xml
│   ├── privacy_notice_views.xml
│   ├── privacy_preference_views.xml
│   ├── privacy_purpose_views.xml
│   ├── project_views.xml
│   └── res_partner_views.xml
├── tests/
│   ├── test_privacy_dashboard.py
│   ├── test_privacy_docuseal.py
│   ├── test_privacy_email.py
│   ├── test_privacy_portal.py
│   └── test_privacy_retention.py
└── wizards/
    ├── privacy_consent_request_wizard.py
    ├── privacy_consent_request_wizard_views.xml
    ├── privacy_consent_withdraw_wizard.py
    ├── privacy_consent_withdraw_wizard_views.xml
    ├── privacy_docuseal_send_wizard.py
    └── privacy_libresign_send_wizard.py
```

---

## Sécurité et conformité

### Audit trail

- Tous les modèles principaux héritent de `mail.thread`
- Les champs critiques (`status`, `expires_at`, etc.) ont `tracking=True`
- Chaque modification est journalisée dans le chatter

### Intégrité des avis

- Les versions d'avis sont **immutables** une fois utilisées
- Une empreinte **SHA256** est générée automatiquement
- Impossible de modifier le contenu d'une version liée à des consentements

### Isolation des données

- Regles de securite par **entreprise** (multi-company) sur tous les modeles
- Les utilisateurs du **portail** ne voient que leurs propres donnees
- Acces graduel selon les groupes (User < Manager < Officer)

### Durcissement de securite (v18.0.3.0.0)

- **Registre immuable** : double protection Python + regles ORM (no-unlink)
- **Liste blanche de modeles** pour la classification documentaire
- **Verification des droits d'acces** avant toute operation sudo() dans les destructions
- **Verification de groupe Python** sur toutes les actions sensibles (approuver, executer)
- **Contraintes de transition d'etat** sur les evaluations d'anonymisation
- **Validation des methodes** de destruction (rejet des valeurs inattendues)
- **Approbation cron securisee** : seules les demandes avec politique sont auto-approuvees
- **Isolation par entreprise** pour les demandes de destruction et classifications

### Conformite Loi 25

| Exigence | Implementation |
|----------|----------------|
| Consentement manifeste (Art. 14) | Workflow explicite avec horodatage |
| Langage clair (Art. 14) | Champ « resume en langage clair » obligatoire |
| Par finalite (Art. 14) | Une finalite = un enregistrement de consentement |
| Preuve (Art. 14) | Modele `privacy.consent.evidence` avec pieces jointes |
| Retrait (Art. 14) | Wizard avec motif et propagation aux preferences |
| Expiration | Cron quotidien + alertes 30 jours avant |
| Mineurs < 14 ans (Art. 14) | Champ « donne par » pour representant legal |
| Destruction (Art. 23) | Demandes de destruction + registre immuable |
| Gouvernance (Art. 3.2) | Calendrier de conservation + registre de destruction |
| Droit a l'effacement (Art. 28.1) | Action serveur depuis la fiche contact |
| Anonymisation (Regl. A-2.1) | Evaluation des 3 criteres avec reevaluation periodique |

---

## Portail client

### URLs disponibles

| URL | Description |
|-----|-------------|
| `/my/privacy/preferences` | Centre de préférences |
| `/my/privacy/consents` | Historique des consentements |
| `/my/privacy/consent/<id>` | Détail d'un consentement |
| `/my/privacy/consent/<id>/respond` | Répondre à une demande |

### Fonctionnalités

- **Gestion des préférences** : activer/désactiver les communications par canal
- **Bouton « Ne pas contacter »** : opt-out global
- **Historique** : voir tous les consentements passés et présents
- **Réponse aux demandes** : accorder ou refuser directement

---

## Automatisations

### Taches planifiees (Cron)

| Tache | Frequence | Action |
|-------|-----------|--------|
| Verification des expirations | Quotidienne | Cree une activite 30 jours avant expiration |
| Marquage des expires | Quotidienne | Passe le statut a « Expire » |
| Expiration auto des demandes en attente | Quotidienne | Expire les consentements restes sans reponse |
| Traitement des sequences de courriels | Quotidienne | Envoie les rappels et renouvellements programmes |
| Creation des demandes de destruction | Quotidienne | Cree les demandes selon les politiques de retention |
| Traitement des destructions planifiees | Quotidienne | Approuve et execute les demandes dues |
| Verification des reevaluations | Quotidienne | Signale les evaluations d'anonymisation dues |
| Verification de l'integrite du registre | Quotidienne | Recalcule la chaine SHA-256 et alerte en cas d'alteration |

### Templates email

- **Demande de consentement** : envoye lors d'une nouvelle demande
- **Avertissement d'expiration** : disponible pour envoi manuel ou automatise
- **Sequences automatisees** : sequences de courriels configurables (rappels, renouvellements)

---

## Dépendances

| Module | Usage |
|--------|-------|
| `base` | Modele `res.partner`, infrastructure de base |
| `mail` | Chatter, activites, templates email |
| `project` | Extension du modele `project.project` |
| `portal` | Controleur et templates du portail client |
| `bluefox_branding` | Gabarits de courriels et rapports brandes |

| Dependance Python | Usage |
|-------------------|-------|
| `cryptography` | Chiffrement des mots de passe et cles API |
| `dateutil` | Calcul des dates de reevaluation (relativedelta) |

### Modules compagnons facultatifs — cadres réglementaires (v18.0.4.0.0)

La Loi 25 (Québec) est intégrée au module principal ; **aucun module compagnon n'est requis** pour l'usage par défaut. Pour servir d'autres juridictions, installez le ou les modules data-only suivants (ils ne dépendent que de `privacy_consent`) :

| Module | Cadre ajouté | Autorité |
|--------|--------------|----------|
| `privacy_framework_gdpr` | RGPD / GDPR (Union européenne) | autorité de contrôle nationale / EDPB |
| `privacy_framework_uk` | UK GDPR / Data Protection Act 2018 | ICO |
| `privacy_framework_pipeda` | LPRPDE / PIPEDA (Canada fédéral) | CPVP / OPC |
| `privacy_framework_nz` | Privacy Act 2020 (Nouvelle-Zélande) | OPC NZ |

---

## Licence

Distribué sous **Business Source License 1.1** (BUSL-1.1). Voir le fichier
[`LICENSE`](LICENSE) pour les paramètres exacts.

- **Permis sans entente** : l'usage en production pour vos propres opérations
  internes.
- **Demande une entente écrite** : fournir le module comme produit ou service à
  des tiers — hébergé, infogéré ou revendu.
- **Change Date** : le 2029-07-20, cette version bascule automatiquement en
  **LGPL-3.0-or-later**.

```
This module is licensed under the **Business Source License 1.1** (BUSL-1.1). Production use for your own internal business operations is permitted; providing the module as a product or service to third parties — hosted, managed or resold — requires a separate written agreement. On 2029-07-20 it converts to LGPL-3.0-or-later. See [LICENSE](LICENSE) for the full text.
```

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

---

## Support

Pour signaler un problème ou suggérer une amélioration, veuillez contacter l'équipe technique ou ouvrir un ticket dans le dépôt.

---

## Historique des versions

| Version | Date | Description |
|---------|------|-------------|
| 18.0.4.1.0 | 2026-07 | Portail de consentement **brandé** : les gabarits du portail consomment les variables `--brand-primary` / `--brand-dark` issues de `report_brand_*` au lieu de couleurs codées en dur, avec repli sur les valeurs par défaut |
| 18.0.4.0.0 | 2026-06 | Moteur **multi-cadres réglementaires** : modèle `privacy.framework` (+ bases légales + droits des personnes), cadre par défaut par société surchargeable par enregistrement, courriels et certificats paramétrés. Loi 25 intégrée + modules compagnons GDPR / UK GDPR / PIPEDA / Privacy Act 2020 (NZ). La Loi 25 reste **inchangée** (rendu identique, chaîne d'intégrité du registre de destruction préservée) |
| 18.0.3.1.0 | 2026-04 | Registre de destruction a chaine SHA-256 (chaque entree integre l'empreinte de la precedente) + cron de verification d'integrite (8e tache planifiee) |
| 18.0.3.1.4 | 2026-06 | Synchronisation documentation et métadonnées (licence/LICENSE). Voir l'historique git pour le détail. |
| 18.0.3.0.1 | 2026-04-11 | Correctifs QA : 17 methodes action_* sans retour XML-RPC, selection secure_wipe manquante, ACL registre (notes editable par Officer), certificat PDF redirige vers rapport QWeb, codes README corriges |
| 18.0.3.0.0 | 2026-04 | Destruction et anonymisation documentaire : calendrier de conservation, classification documentaire, registre de destruction immuable, campagnes de destruction en lot, evaluations d'anonymisation (Regl. A-2.1), droit a l'effacement, audit de securite complet |
| 18.0.2.0.0 | 2026-02 | Ajout du manuel d'utilisation complet, integration DocuSeal, politiques de retention, certificats de destruction |
| 18.0.1.0.0 | 2026-01 | Version initiale |

---

<sub>¹ Le code de ce module a été développé avec l'assistance de [Claude](https://claude.ai) (Anthropic) pour la revue et l'optimisation du code.</sub>
