import base64
import hmac
import logging
import threading
import time
from collections import defaultdict

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import Controller, request, route

from ..models.bf_sign_field import VALUE_TYPES

_logger = logging.getLogger(__name__)

# Anti-brute-force on token validation (per client IP), mirrors bf_appointment.
_token_fail_lock = threading.Lock()
_token_fail_data = defaultdict(list)
_TOKEN_FAIL_MAX = 10
_TOKEN_FAIL_WINDOW = 300  # seconds


def _client_ip():
    try:
        env = request.httprequest.environ
        for key in ("HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR"):
            value = env.get(key, "")
            if value:
                return value.split(",")[0].strip()
        return request.httprequest.remote_addr or "unknown"
    except Exception:
        return "unknown"


def _user_agent():
    try:
        return request.httprequest.headers.get("User-Agent", "")[:512]
    except Exception:
        return ""


def _check_token_rate_limit():
    ip = _client_ip()
    now = time.monotonic()
    with _token_fail_lock:
        attempts = _token_fail_data[ip]
        cutoff = now - _TOKEN_FAIL_WINDOW
        _token_fail_data[ip] = [t for t in attempts if t > cutoff]
        return len(_token_fail_data[ip]) < _TOKEN_FAIL_MAX


def _record_token_failure():
    ip = _client_ip()
    now = time.monotonic()
    with _token_fail_lock:
        _token_fail_data[ip].append(now)


class BfSignController(Controller):

    def _sign_page_ctx(self, req_sudo, signer, access_token, **extra):
        """Shared render context for the public signing page.

        Computes the reading-order field list and the {field_id: number} map so
        the placement markers on the document and the inputs below share the
        same clear identifier.
        """
        overlay_fields = signer._overlay_fields()
        field_numbers = {f.id: i + 1 for i, f in enumerate(overlay_fields)}
        # Pre-compute the marker numbers per pad type in Python (QWeb does not
        # reliably evaluate list comprehensions inside t-value on the website
        # render path).
        sig_nums = ", ".join(str(field_numbers[f.id]) for f in overlay_fields
                             if f.field_type == "signature")
        ini_nums = ", ".join(str(field_numbers[f.id]) for f in overlay_fields
                             if f.field_type == "initials")
        ctx = {
            "req": req_sudo, "signer": signer, "access_token": access_token,
            "need_initials": signer.has_initials,
            "overlay_fields": overlay_fields, "field_numbers": field_numbers,
            "sig_nums": sig_nums, "ini_nums": ini_nums,
            "default_initials": signer._default_initials(),
            # Kept in sync with the model so a new pad type does not need a
            # matching edit in the QWeb template.
            "value_types": tuple(sorted(VALUE_TYPES)),
        }
        ctx.update(extra)
        return ctx

    def _resolve_signer(self, request_id, access_token):
        """Validate token → return (request_sudo, signer_sudo) or (False, False)."""
        if not access_token:
            return False, False
        if not _check_token_rate_limit():
            _logger.warning("bf_sign: token rate limit exceeded for IP %s", _client_ip())
            return False, False
        signer = request.env["bf.sign.signer"].sudo().search(
            [("request_id", "=", int(request_id))], limit=0)
        match = signer.filtered(
            lambda s: s.access_token and hmac.compare_digest(s.access_token, access_token))
        if not match:
            _record_token_failure()
            return False, False
        match = match[0]
        return match.request_id, match

    # ── Sign page ─────────────────────────────────────────────────────────────
    @route("/sign/<int:request_id>/<access_token>", type="http", auth="public",
           methods=["GET"], csrf=False)
    def sign_page(self, request_id, access_token, **kw):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        if signer.state == "signed":
            return request.redirect("/sign/%s/%s/done" % (request_id, access_token))
        if req_sudo.state in ("cancelled", "expired", "refused"):
            return request.render("bf_sign.sign_unavailable", {"req": req_sudo})
        if not req_sudo._signer_can_sign(signer):
            # Sequential: not this signer's turn yet.
            return request.render("bf_sign.sign_waiting", {"req": req_sudo, "signer": signer})
        if signer._otp_required():
            # Identity check: send a code on first arrival, then ask for it.
            if not signer.otp_sent_at:
                signer._otp_send()
            return request.render(
                "bf_sign.sign_otp", self._otp_ctx(req_sudo, signer, access_token))
        try:
            req_sudo.register_signer_view(signer, ip=_client_ip(), user_agent=_user_agent())
        except Exception as exc:  # noqa: BLE001
            _logger.warning("bf_sign: register_signer_view failed: %s", exc)
        return request.render(
            "bf_sign.sign_page",
            self._sign_page_ctx(req_sudo, signer, access_token))

    # ── Email OTP identity step ────────────────────────────────────────────────
    def _otp_ctx(self, req_sudo, signer, access_token, error=None):
        email = signer.email or ""
        masked = email
        if "@" in email:
            local, _sep, domain = email.partition("@")
            masked = ((local[0] + "***") if local else "***") + "@" + domain
        return {
            "req": req_sudo, "signer": signer, "access_token": access_token,
            "masked_email": masked, "error": error,
        }

    @route("/sign/<int:request_id>/<access_token>/otp/verify", type="http",
           auth="public", methods=["POST"], csrf=False)
    def sign_otp_verify(self, request_id, access_token, **post):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        if not signer._otp_required():
            return request.redirect("/sign/%s/%s" % (request_id, access_token))
        if signer._otp_verify(post.get("code")):
            request.env["bf.sign.log"].sudo()._append(
                req_sudo, "otp_verified", actor=signer.email, ip_address=_client_ip(),
                user_agent=_user_agent(), identity_method="email_otp",
                note=_("Signataire : %s") % signer.name)
            return request.redirect("/sign/%s/%s" % (request_id, access_token))
        return request.render(
            "bf_sign.sign_otp", self._otp_ctx(req_sudo, signer, access_token, error=True))

    @route("/sign/<int:request_id>/<access_token>/otp/resend", type="http",
           auth="public", methods=["POST"], csrf=False)
    def sign_otp_resend(self, request_id, access_token, **post):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        if signer._otp_required():
            signer._otp_send()
        return request.redirect("/sign/%s/%s" % (request_id, access_token))

    # ── Serve the original PDF inline ──────────────────────────────────────────
    @route("/sign/<int:request_id>/<access_token>/document", type="http",
           auth="public", methods=["GET"], csrf=False)
    def sign_document(self, request_id, access_token, **kw):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer or not req_sudo.document_file:
            return request.not_found()
        if signer._otp_required():
            return request.not_found()
        pdf = base64.b64decode(req_sudo.document_file)
        filename = req_sudo.document_filename or "document.pdf"
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", http.content_disposition(filename).replace(
                "attachment", "inline")),
            ("Content-Length", len(pdf))])

    # ── Submit the signature ───────────────────────────────────────────────────
    @route("/sign/<int:request_id>/<access_token>/submit", type="http",
           auth="public", methods=["POST"], csrf=False)
    def sign_submit(self, request_id, access_token, **post):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        if signer.state == "signed":
            return request.redirect("/sign/%s/%s/done" % (request_id, access_token))
        if signer._otp_required():
            return request.redirect("/sign/%s/%s" % (request_id, access_token))

        consent = post.get("consent") in ("on", "true", "1", "yes")
        sig_b64 = self._strip_data_url(post.get("signature", ""))
        ini_b64 = self._strip_data_url(post.get("initials", ""))
        field_values = {k[len("field_"):]: v for k, v in post.items()
                        if k.startswith("field_")}

        if not sig_b64 or not consent:
            return request.render(
                "bf_sign.sign_page",
                self._sign_page_ctx(req_sudo, signer, access_token, error=True))
        try:
            req_sudo.register_signer_signature(
                signer, sig_b64, ini_b64, consent,
                ip=_client_ip(), user_agent=_user_agent(), field_values=field_values)
        except UserError as exc:
            # Expected validation errors: surface their (safe) message.
            return request.render(
                "bf_sign.sign_page",
                self._sign_page_ctx(req_sudo, signer, access_token,
                                    error=True, error_message=str(exc)))
        except Exception:  # noqa: BLE001
            # Unexpected error: log internally, show a generic message (no detail leak).
            _logger.exception("bf_sign: signature failed for %s", req_sudo.name)
            return request.render(
                "bf_sign.sign_page",
                self._sign_page_ctx(req_sudo, signer, access_token, error=True))
        return request.redirect("/sign/%s/%s/done" % (request_id, access_token))

    # ── Refuse to sign ─────────────────────────────────────────────────────────
    @route("/sign/<int:request_id>/<access_token>/refuse", type="http",
           auth="public", methods=["POST"], csrf=False)
    def sign_refuse(self, request_id, access_token, **post):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        if signer.state == "signed":
            return request.redirect("/sign/%s/%s/done" % (request_id, access_token))
        reason = (post.get("reason") or "").strip()[:1000]
        try:
            req_sudo.register_signer_refusal(
                signer, reason=reason, ip=_client_ip(), user_agent=_user_agent())
        except Exception as exc:  # noqa: BLE001
            _logger.warning("bf_sign: refusal failed for %s: %s", req_sudo.name, exc)
        return request.render("bf_sign.sign_refused", {"req": req_sudo, "signer": signer})

    @staticmethod
    def _strip_data_url(value):
        if value and "," in value:
            return value.split(",", 1)[1]
        return value or ""

    # ── Confirmation page ──────────────────────────────────────────────────────
    @route("/sign/<int:request_id>/<access_token>/done", type="http",
           auth="public", methods=["GET"], csrf=False)
    def sign_done(self, request_id, access_token, **kw):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer:
            return request.not_found()
        return request.render("bf_sign.sign_done", {
            "req": req_sudo, "signer": signer, "access_token": access_token})

    # ── Download the signed bundle (only once fully signed) ────────────────────
    @route("/sign/<int:request_id>/<access_token>/download", type="http",
           auth="public", methods=["GET"], csrf=False)
    def sign_download(self, request_id, access_token, **kw):
        req_sudo, signer = self._resolve_signer(request_id, access_token)
        if not signer or req_sudo.state != "signed" or not req_sudo.signed_attachment_id:
            return request.not_found()
        att = req_sudo.signed_attachment_id
        pdf = base64.b64decode(att.datas)
        try:
            req_sudo.env["bf.sign.log"]._append(
                req_sudo, "downloaded", actor=signer.email,
                ip_address=_client_ip(), user_agent=_user_agent(),
                identity_method="email_link_token")
        except Exception:  # noqa: BLE001
            pass
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", http.content_disposition(att.name)),
            ("Content-Length", len(pdf))])
