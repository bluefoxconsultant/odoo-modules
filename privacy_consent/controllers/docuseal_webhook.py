import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DocuSealWebhookController(http.Controller):
    """Contrôleur pour les notifications webhook DocuSeal."""

    @http.route(
        "/privacy/docuseal/webhook",
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def docuseal_webhook(self):
        """Traiter les notifications webhook DocuSeal.

        DocuSeal envoie des webhooks pour :
        - submission.created
        - submission.started
        - submission.completed
        - submission.expired
        - form.started
        - form.viewed
        - form.completed
        """
        try:
            data = request.jsonrequest
        except Exception:
            _logger.error("JSON invalide dans le webhook DocuSeal")
            return {"status": "error", "message": "Invalid JSON"}

        _logger.info("Webhook DocuSeal reçu : %s", data.get("event_type"))

        # Vérifier la signature du webhook si le secret est configuré
        if not self._verify_webhook_signature(data):
            _logger.warning("Échec de la vérification de la signature du webhook DocuSeal")
            return {"status": "error", "message": "Invalid signature"}

        event_type = data.get("event_type", "")
        submission_data = data.get("data", {})
        submission_id = str(submission_data.get("id") or submission_data.get("submission_id", ""))

        if not submission_id:
            _logger.warning("ID de soumission manquant dans le webhook DocuSeal")
            return {"status": "error", "message": "Missing submission ID"}

        # Trouver le consentement associé
        Consent = request.env["privacy.consent"].sudo()
        consent = Consent.search([
            ("docuseal_submission_id", "=", submission_id),
        ], limit=1)

        if not consent:
            _logger.info("Aucun consentement trouvé pour la soumission DocuSeal %s", submission_id)
            return {"status": "ok", "message": "Submission not tracked"}

        # Traiter selon le type d'événement
        if event_type == "submission.completed":
            self._handle_submission_completed(consent, submission_data)
        elif event_type == "submission.expired":
            self._handle_submission_expired(consent, submission_data)
        elif event_type == "form.completed":
            self._handle_form_completed(consent, submission_data)

        return {"status": "ok"}

    def _verify_webhook_signature(self, data):
        """Vérifier la signature du webhook DocuSeal."""
        # Obtenir la signature des en-têtes
        signature = request.httprequest.headers.get("X-DocuSeal-Signature", "")
        if not signature:
            # Aucune signature fournie - autoriser si aucun secret configuré
            Config = request.env["privacy.docuseal.config"].sudo()
            config = Config.search([("active", "=", True)], limit=1)
            if config and config.webhook_secret_encrypted:
                return False
            return True

        # Obtenir le secret configuré
        Config = request.env["privacy.docuseal.config"].sudo()
        config = Config.search([("active", "=", True)], limit=1)
        if not config or not config.webhook_secret_encrypted:
            return True

        secret = config._decrypt_value(config.webhook_secret_encrypted)
        if not secret:
            return True

        # Calculer la signature attendue
        payload = json.dumps(data, separators=(",", ":"))
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def _handle_submission_completed(self, consent, submission_data):
        """Traiter l'événement submission.completed."""
        _logger.info("Traitement de submission.completed pour le consentement %s", consent.id)

        # Obtenir les documents signés
        documents = []
        Config = request.env["privacy.docuseal.config"].sudo()
        config = Config.search([("active", "=", True)], limit=1)

        if config:
            Interface = request.env["privacy.docuseal.interface"].sudo()
            try:
                documents = Interface.get_submission_documents(
                    config, consent.docuseal_submission_id
                )
            except Exception as e:
                _logger.error("Échec du téléchargement des documents signés : %s", e)

        # Traiter la complétion
        consent._process_docuseal_completion(submission_data, documents)

    def _handle_submission_expired(self, consent, submission_data):
        """Traiter l'événement submission.expired."""
        _logger.info("Traitement de submission.expired pour le consentement %s", consent.id)

        consent.write({
            "docuseal_status": "expired",
        })
        consent.message_post(
            body="La demande de signature DocuSeal a expiré.",
            message_type="notification",
        )

    def _handle_form_completed(self, consent, submission_data):
        """Traiter l'événement form.completed (complétion partielle)."""
        _logger.info("Traitement de form.completed pour le consentement %s", consent.id)

        consent.message_post(
            body="Le signataire a complété le formulaire. En attente de la finalisation de la soumission.",
            message_type="notification",
        )
