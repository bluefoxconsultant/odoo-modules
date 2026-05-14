# Privacy & Consent Tracking (Loi 25)

[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)

Odoo 18 CE module for managing privacy under Quebec's **Loi 25** (Act respecting the protection of personal information): consents, document destruction, and anonymization.

---

## Table of contents

- [Overview](#overview)
- [Documentation](#documentation)
- [Features](#features)
  - [Consents](#consent-management)
  - [Document destruction](#document-destruction-and-anonymization-v1800300)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Technical architecture](#technical-architecture)
- [Security and compliance](#security-and-compliance)
- [Client portal](#client-portal)
- [Automations](#automations)
- [Dependencies](#dependencies)
- [License](#license)
- [Support](#support)

---

## Overview

**Loi 25** (formerly Bill 64) modernizes Quebec's legal framework for personal-information protection. It places new obligations on organizations, including:

- Obtaining **manifest, free, informed and specific consent** for each purpose
- Presenting consent requests in **clear and simple language**
- Documenting and **tracing** every consent obtained
- Allowing **withdrawal** of consent at any time
- Managing **expiration** and renewals

This module provides:

**Consents**: a unified register linking the data subject, purpose, context, and proof, with a tamper-evident history and automations.

**Destruction and anonymization** (v18.0.3.0.0): retention calendar by document type, classification of personal information, immutable destruction register (Art. 3.2 LPRPSP), bulk destruction campaigns, anonymization assessments against the 3 criteria of Regulation A-2.1, r. 0.1, and right to erasure (Art. 28.1 LPRPSP).

---

## Documentation

### User manual

A full **user manual** in French is available for end users:

📖 **[User manual (French)](doc/MANUEL_UTILISATEUR.md)**

The manual covers:

- **Navigation**: menu structure and access by role
- **Dashboard**: KPIs and quick actions
- **Operations**: managing consents, pending requests, destructions
- **Configuration**: purposes, notices, preferences, retention policies, email sequences, DocuSeal
- **Client portal**: client access and features
- **Integrations**: contacts, projects, marketing
- **Lifecycle**: full state diagram with transitions
- **Evidence and traceability**: types of evidence and forensic data
- **Automations**: cron jobs and automatic activities
- **Roles and permissions**: access levels (User, Manager, Officer)
- **Legal compliance**: Loi 25, GDPR
- **Glossary**: definitions of key terms

---

## Features

### Purpose management

- Define purposes with a unique code and a plain-language description
- Configure required consent type (express opt-in or implicit)
- Configurable default validity duration
- Channel scope (email, SMS, phone, video, in-person)
- Context scope (project, marketing, meeting, CRM)

**Purposes seeded by default:**
| Code | Purpose | Express opt-in | Validity |
|------|---------|----------------|----------|
| `marketing` | Marketing communications | Yes | 365 days |
| `recording` | Video recording | Yes | Unlimited |
| `recording_audio` | Audio recording | Yes | Unlimited |
| `transcription` | Transcription | Yes | Unlimited |
| `reference` | Use as reference | No | 730 days |
| `logo` | Logo use | No | 730 days |
| `case_study` | Case study | Yes | 730 days |
| `service` | Service communications | Not required | Unlimited |
| `third_party` | Sharing with third parties | No | 365 days |

### Notice management

- Bilingual (French/English) notice templates
- **Automatic versioning** with SHA-256 fingerprint
- Full traceability: which version was presented, when
- Cannot edit a version that is already in use (immutability)

### Consent recording

- Full workflow: Draft → Pending → Granted/Denied → Withdrawn/Expired
- Linked to the **contact** (data subject)
- Optional link to a **representative** (for minors under 14)
- Contextual link to a **project** or other record
- Traceable collection method (portal, email, signature, verbal, import)
- Timestamp on every state change
- **Integrated chatter** for full history

### Evidence management

- Attachments (signed PDF, screenshot, document)
- Verbal confirmation notes
- Technical metadata (IP address, user agent) for portal flows
- Traceability: who collected, when, how

### Contact preferences

- Granular per-channel management:
  - Service email / Marketing email
  - Phone / SMS
- **Do-not-contact** flag (global kill switch)
- Preferred language and preferred contact hours
- Categorized opt-out reason
- Change history via chatter

### Document destruction and anonymization (v18.0.3.0.0)

#### Retention calendar

- Retention rules by document type (contracts, invoices, HR files, projects, etc.)
- Mandatory legal basis for each rule (e.g. Art. 2925 C.c.Q.)
- Active and semi-active retention periods in years
- Configurable final disposition: destroy, anonymize, archive permanently, transfer
- Built-in annual review with date tracking

**Default rules included:**

| Code | Document type | Retention | Legal basis |
|------|---------------|-----------|-------------|
| `CTR-001` | Contracts | 6 years | Art. 2925 C.c.Q. |
| `FIN-001` | Invoices and tax documents | 7 years (6+1) | Tax administration act |
| `RH-001` | Employee files | 5 years (3+2) | Labor standards |
| `PRJ-001` | Project files | 5 years | Art. 2925 C.c.Q. |
| `COR-001` | Correspondence | 3 years | Practice |
| `MED-001` | Medical documents | 7 years | Health record reg. (LSST) |
| `SEC-001` | Credentials and passwords | 0 years | Security |
| `CST-001` | Consent register | 3 years | Loi 25 |

#### Document classification

- Classify any Odoo record with its PI categories
- 10 personal-information categories (identification, medical, financial, biometric, etc.)
- 4 sensitivity levels (public, internal, confidential, highly confidential)
- Direct and indirect identifiers
- Retention expiration date computed automatically
- **Model whitelist**: only models that may contain PI can be classified (security)

#### Destruction register (immutable)

- Destruction register compliant with article 3.2 LPRPSP
- **Total immutability**: no modification (except notes) and no deletion possible
- SHA-256 verification fingerprint to deter tampering
- Automatic numbering (REG-YYYY-NNNNN)
- Linked to destruction requests and campaigns
- Double protection: Python (`write()` / `unlink()` overrides) + ORM record rules

#### Bulk destruction campaigns

- Full workflow: Draft → Scan → Review → Approval → Execution → Completed
- Automatic scan of records past their retention according to the retention calendar
- Per-line execution with individual error handling (no global abort)
- Automatic destruction-register entries for each destroyed record
- Ability to skip records individually

#### Anonymization assessments (Reg. A-2.1, r. 0.1)

- Assessment against the 3 criteria of the Anonymization Regulation (May 2024):
  1. **Individualization**: can a person be isolated?
  2. **Correlation**: can data sets be linked?
  3. **Inference**: can PI be deduced?
- Overall risk computed automatically (the highest of the 3)
- Automatic determination of whether data is effectively anonymous
- Periodic re-assessment scheduled with automatic alert
- Re-assessment chain (parent/child)

#### Right to erasure (Art. 28.1 LPRPSP)

- Server action from the contact form: "Request erasure of data"
- Automatic creation of a destruction request covering all classifications of the contact
- Secure destruction of identifiers (cryptographic overwrite)
- Activity created for manual deletion of the Nextcloud folder

### Contacts integration

- New **"Privacy (Loi 25)"** tab on the contact form
- **Visual badges**: Marketing ✓/✗, Recording ✓/✗, Reference ✓/✗
- List of active consents
- Quick action buttons:
  - Request a consent
  - View / edit preferences

### Projects integration

- New **"Consents"** tab on the project form
- Global status indicator (None / Pending / Partial / Complete)
- List of consents linked to the project
- Button to request consents from project contacts

### Client portal (Preference Center)

- **"My privacy preferences"** page at `/my/privacy/preferences`
- Self-service management of communication preferences
- Consent history
- Reply to pending consent requests
- Bilingual French/English UI

---

## Installation

### Prerequisites

- Odoo 18.0 Community Edition
- Required modules: `base`, `mail`, `project`, `portal`

### Procedure

1. **Copy the module** into your `addons` directory:
   ```bash
   cp -r privacy_consent /path/to/odoo/addons/
   ```

2. **Restart Odoo**:
   ```bash
   ./odoo-bin -c odoo.conf -u base
   ```

3. **Install the module**:
   - Go to *Apps*
   - Click *Update Apps List*
   - Search for "Privacy & Consent" or "privacy_consent"
   - Click *Install*

---

## Configuration

### 1. Configure purposes

Go to **Privacy > Configuration > Purposes**

For each purpose, define:
- **Code**: unique technical identifier
- **Name**: displayed label
- **Plain-language summary**: text presented to data subjects
- **Consent required**: yes/no
- **Express opt-in required**: for sensitive purposes
- **Default validity**: number of days (0 = unlimited)

### 2. Create consent notices

Go to **Privacy > Configuration > Notices**

For each notice:
1. Associate a purpose
2. Write the content in French and English
3. Click **"Create new version"**

### 3. Configure security groups

| Group | Access |
|-------|--------|
| **Privacy User** | Read consents, classifications, register |
| **Privacy Manager** | CRUD on consents, classifications, campaigns. May create destruction requests |
| **Privacy Officer** | Full administration. May approve and execute destructions and assessments |

Users are assigned to groups via *Settings > Users*.

---

## Usage

### Request a consent

**From a contact:**
1. Open the contact form
2. Go to the "Privacy (Loi 25)" tab
3. Click **"Request a consent"**
4. Select the purpose and notice
5. Choose whether to send an email
6. Submit

**From the Privacy menu:**
1. Go to **Privacy > Operations > Consents**
2. Click **Create**
3. Fill in the information and save
4. Click **"Send request"**

### Grant a consent

- From the **client portal**: the contact replies directly
- From the **backend**: a user can click "Grant"
- The expiration date is computed automatically

### Withdraw a consent

1. Open the granted consent
2. Click **"Withdraw"**
3. Select the withdrawal reason
4. Optionally, update the contact preferences
5. Submit

### View history

Each consent has a **chatter** showing:
- Status changes
- Emails sent
- Notes added
- Date changes

---

## Technical architecture

### Data models

**Consents:**
```
privacy.purpose               # Consent purposes
privacy.notice                # Notice templates
privacy.notice.version        # Immutable versions with SHA-256 hash
privacy.consent               # Consent records (mail.thread)
privacy.consent.evidence      # Evidence and attachments
privacy.contact.preference    # Communication preferences
privacy.consent.group         # Consent groups
privacy.dashboard             # KPI dashboard (transient)
```

**Destruction and anonymization:**
```
privacy.retention.policy             # Retention policies (per consent)
privacy.retention.calendar           # Retention calendar (per document type)
privacy.document.classification      # Document classification (PI)
privacy.destruction.request          # Destruction requests (mail.thread)
privacy.destruction.register         # Immutable destruction register
privacy.destruction.campaign         # Bulk destruction campaigns (mail.thread)
privacy.destruction.campaign.line    # Campaign lines
privacy.anonymization.assessment     # Anonymization assessments (mail.thread)
```

**Electronic signatures:**
```
privacy.docuseal.config        # DocuSeal configuration
privacy.docuseal.template      # DocuSeal templates
privacy.libresign.config       # LibreSign configuration
privacy.libresign.template     # LibreSign templates
```

**Extensions:**
```
res.partner              # Privacy tab + badges + counters
project.project          # Consents tab + global status
```

### File structure

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
│   └── privacy_security.xml         # 3 groups, 14 record rules
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

## Security and compliance

### Audit trail

- All main models inherit from `mail.thread`
- Critical fields (`status`, `expires_at`, etc.) are `tracking=True`
- Every change is logged in the chatter

### Notice integrity

- Notice versions are **immutable** once used
- A **SHA-256** fingerprint is generated automatically
- The content of a version linked to consents cannot be edited

### Data isolation

- Per-**company** security rules (multi-company) on every model
- **Portal** users only see their own data
- Tiered access by group (User < Manager < Officer)

### Security hardening (v18.0.3.0.0)

- **Immutable register**: double protection Python + ORM rules (no-unlink)
- **Model whitelist** for document classification
- **Access-rights checks** before any `sudo()` operation in destructions
- **Group checks in Python** on every sensitive action (approve, execute)
- **State-transition constraints** on anonymization assessments
- **Method validation** for destruction (rejects unexpected values)
- **Secure cron approval**: only requests with a policy are auto-approved
- **Per-company isolation** for destruction requests and classifications

### Loi 25 compliance

| Requirement | Implementation |
|-------------|----------------|
| Manifest consent (Art. 14) | Explicit workflow with timestamps |
| Plain language (Art. 14) | Mandatory "plain-language summary" field |
| Per purpose (Art. 14) | One purpose = one consent record |
| Evidence (Art. 14) | `privacy.consent.evidence` model with attachments |
| Withdrawal (Art. 14) | Wizard with reason and propagation to preferences |
| Expiration | Daily cron + 30-day-ahead alerts |
| Minors under 14 (Art. 14) | "Given by" field for legal representative |
| Destruction (Art. 23) | Destruction requests + immutable register |
| Governance (Art. 3.2) | Retention calendar + destruction register |
| Right to erasure (Art. 28.1) | Server action from the contact form |
| Anonymization (Reg. A-2.1) | 3-criteria assessment with periodic re-assessment |

---

## Client portal

### Available URLs

| URL | Description |
|-----|-------------|
| `/my/privacy/preferences` | Preference center |
| `/my/privacy/consents` | Consent history |
| `/my/privacy/consent/<id>` | Consent detail |
| `/my/privacy/consent/<id>/respond` | Respond to a request |

### Features

- **Preferences management**: enable/disable communications by channel
- **"Do not contact" button**: global opt-out
- **History**: see every past and present consent
- **Respond to requests**: grant or deny directly

---

## Automations

### Scheduled tasks (cron)

| Task | Frequency | Action |
|------|-----------|--------|
| Expiration check | Daily | Creates an activity 30 days before expiration |
| Mark as expired | Daily | Sets status to "Expired" |
| Create destruction requests | Daily | Creates requests according to retention policies |
| Process scheduled destructions | Daily | Approves and executes due requests |
| Re-assessment check | Daily | Flags anonymization assessments that are due |

### Email templates

- **Consent request**: sent on a new request
- **Expiration warning**: available for manual or automated sending
- **Automated sequences**: configurable email sequences (reminders, renewals)

---

## Dependencies

| Module | Use |
|--------|-----|
| `base` | `res.partner` model, base infrastructure |
| `mail` | Chatter, activities, email templates |
| `project` | Extension of the `project.project` model |
| `portal` | Client-portal controller and templates |

| Python dependency | Use |
|-------------------|-----|
| `cryptography` | Encryption of passwords and API keys |
| `dateutil` | Re-assessment date computation (relativedelta) |

---

## License

This module is distributed under the **GNU LGPL-3** license.

```
This module is licensed under the GNU Lesser General Public License v3.0 (LGPL-3). See [LICENSE](LICENSE) for the full text.
```

## Disclaimer

This module is provided as-is, without warranty of any kind. Use at your own risk. Blue Fox Inc. assumes no liability for any damages arising from the use of this software.

---

## Support

To report a problem or suggest an improvement, contact the technical team or open a ticket in the repository.

---

## Version history

| Version | Date | Description |
|---------|------|-------------|
| 18.0.3.0.1 | 2026-04-11 | QA fixes: 17 `action_*` methods without XML-RPC return, missing `secure_wipe` selection, register ACL (notes editable by Officer), PDF certificate redirected to QWeb report, README codes fixed |
| 18.0.3.0.0 | 2026-04 | Document destruction and anonymization: retention calendar, document classification, immutable destruction register, bulk destruction campaigns, anonymization assessments (Reg. A-2.1), right to erasure, full security audit |
| 18.0.2.0.0 | 2026-02 | Added complete user manual, DocuSeal integration, retention policies, destruction certificates |
| 18.0.1.0.0 | 2026-01 | Initial release |

---

<sub>Authored and maintained by Blue Fox Inc. AI coding assistants were used as productivity tools during development.</sub>
