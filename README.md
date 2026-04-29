# Blue Fox — Odoo 18 CE Modules

Custom Odoo 18 Community Edition modules developed by [Blue Fox Inc.](https://bluefoxconsultant.com)

## Modules

| Directory | Name | Version | License | Description |
|---|---|---|---|---|
| `audit_ti` | Audit TI - Loi 25 | 18.0.1.17.0 | LGPL-3 | Gestion des audits de sécurité informatique pour la conformité Loi 25 |
| `bf_appointment` | Blue Fox Appointment | 18.0.2.7.1 | AGPL-3 | Pages publiques de prise de rendez-vous en libre-service (étend `resource_booking`) |
| `bf_dark_mode` | Blue Fox Dark Mode | 18.0.1.0.0 | MIT | Mode sombre pour Odoo utilisant la palette Blue Fox |
| `bf_document_nextcloud_sync` | Document Nextcloud Sync | 18.0.1.1.0 | LGPL-3 | Synchronisation documents Odoo ↔ Nextcloud via WebDAV |
| `bf_email_management` | Gestion des courriels | 18.0.1.5.1 | LGPL-3 | Inbox unifiée IMAP + chatters Odoo, avec re-routage UI |
| `bf_gamification` | Fox Quest | 18.0.2.1.0 | LGPL-3 | Système de gamification avec XP, niveaux, badges et récompenses |
| `bf_hour_bank` | Banque d'heures | 18.0.1.6.0 | LGPL-3 | Suivi automatisé des banques d'heures client |
| `bf_mail_import` | BF Import courriel (.eml) | 18.0.1.2.0 | LGPL-3 | Importer des fichiers .eml dans le chatter Odoo |
| `bf_mail_vigie` | BF Vigie courriels (re-router) | 18.0.2.0.0 | LGPL-3 | Bouton "Re-router" sur `bf.email` pour déplacer un courriel mal routé vers la bonne chatter |
| `bf_meeting` | Rencontres | 18.0.3.3.0 | LGPL-3 | Ordres du jour, comptes rendus et tâches à discuter en rencontre |
| `bf_sms_archive` | Archive SMS & Appels | 18.0.1.3.0 | LGPL-3 | Archivage et recherche de SMS et journaux d'appels Android |
| `bf_task_unblock_notify` | BF Notification de déblocage de tâche | 18.0.1.6.1 | LGPL-3 | Notifie les assignés quand leur tâche est débloquée |
| `bf_timesheet_timer` | BF Timer - Feuilles de temps | 18.0.1.6.0 | LGPL-3 | Timer global de feuilles de temps avec multi-timer et interface OWL |
| `bf_universal_search` | BF Recherche universelle | 18.0.1.3.0 | LGPL-3 | Recherche transversale dans tous les modules via la palette de commandes |
| `bf_webmail` | Courriel Blue Fox | 18.0.1.1.0 | LGPL-3 | Accès au courriel SnappyMail depuis la barre Odoo |
| `calendar_nextcloud_sync` | Calendar Nextcloud Sync | 18.0.1.23.0 | LGPL-3 | Synchronisation calendrier bidirectionnelle Odoo ↔ Nextcloud via n8n |
| `contacts_nextcloud_sync` | Contacts Nextcloud Sync | 18.0.1.0.0 | LGPL-3 | Synchronisation des contacts Odoo avec le carnet Nextcloud via CardDAV |
| `daily_todo_digest` | Daily To-Do Digest | 18.0.1.2.0 | LGPL-3 | Courriel quotidien regroupant activités, tâches en retard et aperçu de la semaine |
| `hosting_management` | Gestion d'hébergement | 18.0.2.23.0 | LGPL-3 | Gérer les services d'hébergement pour les clients avec suivi de versions et facturation |
| `privacy_consent` | Suivi des consentements (Loi 25) | 18.0.3.0.1 | LGPL-3 | Vie privée, consentements et destruction documentaire (Loi 25) |
| `project_knowledge_matrix` | Project Knowledge Matrix | 18.0.9.9.0 | LGPL-3 | Base de connaissances projets, politiques et documentation |

## Installation

Add this repository to your Odoo `addons_path`:

```conf
addons_path = /path/to/odoo/addons,/path/to/odoo-modules
```

Then install individual modules from the Odoo Apps menu.

## Compatibility

All modules target **Odoo 18.0 Community Edition**.

## License

Unless stated otherwise in the module's `__manifest__.py`, modules are released under **LGPL-3**. The repository-level `LICENSE` file contains the full MIT text that applies to modules explicitly declaring MIT (currently `bf_dark_mode`).

## Credits

Authored and maintained by Blue Fox Inc. AI coding assistants (including Anthropic's Claude) were used as productivity tools during development; architectural decisions, code review, testing and release responsibility rest with Blue Fox.
