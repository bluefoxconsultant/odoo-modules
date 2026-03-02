{
    "name": "Suivi des consentements (Loi 25)",
    "version": "18.0.2.18.0",
    "category": "Privacy/Compliance",
    "summary": "Suivi des consentements pour la conformité à la Loi 25 du Québec",
    "description": """
Suivi des consentements (Loi 25)
================================

Module de gestion des consentements pour la conformité à la Loi 25 du Québec.

Fonctionnalités :
-----------------
* Tableau de bord avec KPIs (consentements en attente, expirant, taux)
* Gestion des modèles de consentement (avec finalités intégrées)
* Versionnage des modèles avec hash d'intégrité
* Suivi des consentements par contact et projet
* Préférences de contact (DNC, canaux)
* Portail client (Centre de préférences) avec renouvellement
* Politiques de rétention et destruction de données
* Intégration DocuSeal pour signatures électroniques
* Intégration LibreSign (Nextcloud) pour signatures électroniques
* Séquences de courriels automatisées (relances)
* Automatisations (expiration, rappels)
* Assistants pour demandes et retraits
* Intégration complète avec Contacts et Projets
* Certificats de destruction PDF

Conformité Loi 25 :
--------------------
* Résumés en langage clair
* Suivi des consentements express
* Gestion du consentement des mineurs
* Piste de vérification avec preuves
* Politiques de rétention des données
* Certificats de destruction
    """,
    "author": "Your Company Name",
    "website": "https://example.com",
    "license": "Other OSI approved licence",
    "depends": ["base", "mail", "project", "portal"],
    "external_dependencies": {
        "python": ["cryptography"],
    },
    "data": [
        # Sécurité en premier
        "security/privacy_security.xml",
        "security/ir.model.access.csv",
        # Données
        "data/privacy_purpose_data.xml",
        "data/privacy_notice_data.xml",
        "data/privacy_cron.xml",
        "data/privacy_retention_cron.xml",
        "data/mail_template.xml",
        "data/mail_template_sequence.xml",
        "data/mail_activity_type.xml",
        # Vues
        "views/privacy_purpose_views.xml",
        "views/privacy_notice_views.xml",
        "views/privacy_consent_views.xml",
        "views/privacy_consent_group_views.xml",
        "views/privacy_evidence_views.xml",
        "views/privacy_preference_views.xml",
        "views/privacy_dashboard_views.xml",
        "views/privacy_retention_views.xml",
        "views/privacy_destruction_views.xml",
        "views/privacy_docuseal_views.xml",
        "views/privacy_libresign_views.xml",
        "views/privacy_email_sequence_views.xml",
        "views/res_partner_views.xml",
        "views/project_views.xml",
        "views/menu_views.xml",
        "views/portal_templates.xml",
        # Rapports
        "report/privacy_destruction_certificate.xml",
        "report/privacy_consent_certificate.xml",
        # Assistants
        "wizards/privacy_consent_request_wizard_views.xml",
        "wizards/privacy_consent_withdraw_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
