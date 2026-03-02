# Suivi des consentements (Loi 25)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Privacy Module](https://img.shields.io/badge/Privacy-Module-blue.svg)](https://example.com)

Module Odoo 18 CE pour la gestion des consentements conformément à la **Loi 25** du Québec sur la protection des renseignements personnels.

---

## Table des matières

- [Aperçu](#aperçu)
- [Documentation](#documentation)
- [Fonctionnalités](#fonctionnalités)
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

Ce module fournit un registre unifié qui relie :
- La **personne concernée** (Contact)
- La **finalité** (Purpose)
- Le **contexte** (Projet, Opportunité, Réunion)
- La **preuve** (Evidence)

Le tout avec un historique inviolable (audit) et des automatisations.

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

**Finalités incluses par défaut :**
| Code | Finalité | Opt-in express | Validité |
|------|----------|----------------|----------|
| `marketing` | Communications marketing | Oui | 365 jours |
| `recording` | Enregistrement vidéo | Oui | Illimité |
| `recording_audio` | Enregistrement audio | Oui | Illimité |
| `transcription` | Transcription | Oui | Illimité |
| `reference` | Utilisation comme référence | Non | 730 jours |
| `logo` | Utilisation du logo | Non | 730 jours |
| `case_study` | Étude de cas | Oui | 730 jours |
| `service` | Communications de service | Non requis | Illimité |
| `third_party` | Partage avec des tiers | Non | 365 jours |

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
- Modules dépendants : `base`, `mail`, `project`, `portal`

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

### 3. Configurer les groupes de sécurité

| Groupe | Accès |
|--------|-------|
| **Privacy User** | Lecture + création de consentements |
| **Privacy Manager** | CRUD complet sur tous les enregistrements |
| **Privacy Officer** | Administration + export + configuration |

Les utilisateurs sont assignés aux groupes via *Paramètres > Utilisateurs*.

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

### Modèles de données

```
privacy.purpose          # Finalités de consentement
privacy.notice           # Modèles d'avis
privacy.notice.version   # Versions immutables avec hash SHA256
privacy.consent          # Enregistrements de consentement (mail.thread)
privacy.consent.evidence # Preuves et pièces jointes
privacy.contact.preference # Préférences de communication
```

### Extensions

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
│   └── portal.py                    # Contrôleur du portail client
├── data/
│   ├── mail_template.xml            # Templates email
│   ├── privacy_cron.xml             # Tâches planifiées
│   └── privacy_purpose_data.xml     # Données initiales
├── models/
│   ├── privacy_consent.py           # Modèle principal
│   ├── privacy_consent_evidence.py
│   ├── privacy_contact_preference.py
│   ├── privacy_notice.py
│   ├── privacy_notice_version.py
│   ├── privacy_purpose.py
│   ├── project_project.py
│   └── res_partner.py
├── security/
│   ├── ir.model.access.csv          # Droits d'accès
│   └── privacy_security.xml         # Groupes et règles
├── static/description/
│   └── icon.png
├── views/
│   ├── menu_views.xml
│   ├── portal_templates.xml
│   ├── privacy_*.xml
│   ├── project_views.xml
│   └── res_partner_views.xml
└── wizards/
    ├── privacy_consent_request_wizard.py
    └── privacy_consent_withdraw_wizard.py
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

- Règles de sécurité par **entreprise** (multi-company)
- Les utilisateurs du **portail** ne voient que leurs propres données
- Accès graduel selon les groupes (User < Manager < Officer)

### Conformité Loi 25

| Exigence | Implémentation |
|----------|----------------|
| Consentement manifeste | Workflow explicite avec horodatage |
| Langage clair | Champ « résumé en langage clair » obligatoire |
| Par finalité | Une finalité = un enregistrement de consentement |
| Preuve | Modèle `privacy.consent.evidence` avec pièces jointes |
| Retrait | Wizard avec motif et propagation aux préférences |
| Expiration | Cron quotidien + alertes 30 jours avant |
| Mineurs | Champ « donné par » pour représentant légal |

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

### Tâches planifiées (Cron)

| Tâche | Fréquence | Action |
|-------|-----------|--------|
| Vérification des expirations | Quotidienne | Crée une activité 30 jours avant expiration |
| Marquage des expirés | Quotidienne | Passe le statut à « Expiré » |

### Templates email

- **Demande de consentement** : envoyé lors d'une nouvelle demande
- **Avertissement d'expiration** : disponible pour envoi manuel ou automatisé

---

## Dépendances

| Module | Usage |
|--------|-------|
| `base` | Modèle `res.partner`, infrastructure de base |
| `mail` | Chatter, activités, templates email |
| `project` | Extension du modèle `project.project` |
| `portal` | Contrôleur et templates du portail client |

---

## Licence

Ce module est distribué sous licence **MIT**.

```
MIT License

Copyright (c) 2026 Your Company

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Support

Pour signaler un problème ou suggérer une amélioration, veuillez contacter l'équipe technique ou ouvrir un ticket dans le dépôt.

---

## Historique des versions

| Version | Date | Description |
|---------|------|-------------|
| 18.0.2.0.0 | 2026-02 | Ajout du manuel d'utilisation complet, intégration DocuSeal, politiques de rétention, certificats de destruction |
| 18.0.1.0.0 | 2026-01 | Version initiale |

---

<sub>¹ Le code de ce module a été développé avec l'assistance de [Claude](https://claude.ai) (Anthropic) pour la revue et l'optimisation du code.</sub>
