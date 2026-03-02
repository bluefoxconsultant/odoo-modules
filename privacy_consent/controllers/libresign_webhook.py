import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class LibresignWebhookController(http.Controller):
    """Controller for LibreSign webhook notifications."""

    @http.route(
        "/privacy/libresign/webhook",
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def libresign_webhook(self):
        """Handle LibreSign webhook notifications.

        LibreSign sends webhooks for:
        - file_signed: When a file has been signed by all signers
        """
        try:
            data = request.jsonrequest
        except Exception:
            _logger.error("Invalid JSON in LibreSign webhook")
            return {"status": "error", "message": "Invalid JSON"}

        _logger.info("LibreSign webhook received: %s", data.get("event"))

        # Verify webhook signature if secret is configured
        if not self._verify_webhook_signature(data):
            _logger.warning("LibreSign webhook signature verification failed")
            return {"status": "error", "message": "Invalid signature"}

        event = data.get("event", "")
        file_data = data.get("file", {})
        file_uuid = str(file_data.get("uuid", ""))

        if not file_uuid:
            _logger.warning("LibreSign webhook missing file UUID")
            return {"status": "error", "message": "Missing file UUID"}

        # Find the related consent
        Consent = request.env["privacy.consent"].sudo()
        consent = Consent.search([
            ("libresign_file_uuid", "=", file_uuid),
        ], limit=1)

        if not consent:
            _logger.info("No consent found for LibreSign file UUID %s", file_uuid)
            return {"status": "ok", "message": "File not tracked"}

        # Process based on event type
        if event == "file_signed":
            self._handle_file_signed(consent, file_data)

        return {"status": "ok"}

    def _verify_webhook_signature(self, data):
        """Verify the webhook signature from LibreSign."""
        signature = request.httprequest.headers.get("X-LibreSign-Signature", "")
        if not signature:
            Config = request.env["privacy.libresign.config"].sudo()
            config = Config.search([("active", "=", True)], limit=1)
            if config and config.webhook_secret_encrypted:
                return False
            return True

        Config = request.env["privacy.libresign.config"].sudo()
        config = Config.search([("active", "=", True)], limit=1)
        if not config or not config.webhook_secret_encrypted:
            return True

        secret = config._decrypt_value(config.webhook_secret_encrypted)
        if not secret:
            return True

        payload = json.dumps(data, separators=(",", ":"))
        expected = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def _handle_file_signed(self, consent, file_data):
        """Handle file_signed event."""
        _logger.info("Processing file_signed for consent %s", consent.id)

        # Download signed document
        documents = []
        Config = request.env["privacy.libresign.config"].sudo()
        config = Config.search([("active", "=", True)], limit=1)

        if config:
            Interface = request.env["privacy.libresign.interface"].sudo()
            try:
                doc = Interface.get_file_content(config, consent.libresign_file_uuid)
                if doc:
                    documents.append(doc)
            except Exception as e:
                _logger.error("Failed to download signed document: %s", e)

        # Process completion
        consent._process_libresign_completion(file_data, documents)
