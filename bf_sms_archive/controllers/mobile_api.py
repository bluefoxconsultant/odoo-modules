"""API mobile de la messagerie SMS — consommée par l'app Android native.

Contrat REST/JSON propre (pas le JSON-RPC ``call_kw`` d'Odoo) sous
``/bf_sms_archive/mobile/v1/``. Auth par jeton porteur :

  1. POST /login {login, password}  → { token, ... }  (jeton d'appareil)
  2. Requêtes suivantes : en-tête ``Authorization: Bearer <token>``.

Chaque requête authentifiée s'exécute DANS le contexte de l'utilisateur de
l'appareil (``request.update_env(user=…)``), donc les règles d'accès par
propriétaire des fils s'appliquent telles quelles.
"""
import functools
import json
import logging
import urllib.parse

from werkzeug.utils import redirect as wz_redirect

from odoo import fields, http
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

BASE = "/bf_sms_archive/mobile/v1"
SMS_USER_GROUP = "bf_sms_archive.group_sms_user"
REDIRECT_SCHEMES_PARAM = "bf_sms_archive.mobile_redirect_schemes"
DEFAULT_REDIRECT_SCHEMES = "odoosms://"  # BF ajoute son schéma via l'ICP


def _push_config():
    """Config push retournée à l'app : base ntfy + jeton de lecture pour le
    distributeur EMBARQUÉ (repli quand aucune app ntfy n'est installée). Vide si
    non configuré → l'app se rabat sur le distributeur externe seulement."""
    icp = request.env["ir.config_parameter"].sudo()
    return {
        "ntfy_base_url": icp.get_param("bf_sms_archive.ntfy_base_url") or "",
        "ntfy_read_token": icp.get_param("bf_sms_archive.ntfy_read_token") or "",
    }


def _allowed_redirect(redirect):
    """Vrai si l'URL de redirection commence par un schéma d'app autorisé
    (anti open-redirect / exfiltration de code)."""
    schemes = (request.env["ir.config_parameter"].sudo().get_param(
        REDIRECT_SCHEMES_PARAM) or DEFAULT_REDIRECT_SCHEMES)
    allowed = tuple(s.strip() for s in schemes.split(",") if s.strip())
    return bool(redirect) and redirect.startswith(allowed)


def _json(data, status=200):
    return request.make_response(
        json.dumps(data, default=str),
        headers=[("Content-Type", "application/json; charset=utf-8")],
        status=status,
    )


def _body():
    try:
        raw = request.httprequest.get_data(as_text=True) or "{}"
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def _authed(fn):
    """Résout le jeton porteur → charge l'appareil → bascule l'env sur son
    utilisateur. 401 si absent/invalide."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kw):
        header = request.httprequest.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else None
        device = request.env["sms.archive.mobile.device"]._resolve(token)
        if not device:
            return _json({"error": "unauthorized"}, 401)
        device.sudo().write({"last_seen": fields.Datetime.now()})
        request.update_env(user=device.user_id.id)
        try:
            return fn(self, device, *args, **kw)
        except UserError as exc:
            return _json({"error": str(exc)}, 400)
        except Exception:  # noqa: BLE001
            _logger.exception("Mobile API : erreur inattendue")
            return _json({"error": "server_error"}, 500)
    return wrapper


class BfSmsMobileApi(http.Controller):

    # ── Auth ──────────────────────────────────────────────────────────
    @http.route(f"{BASE}/login", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    def login(self, **kw):
        data = _body()
        login = (data.get("login") or "").strip()
        password = data.get("password") or ""
        if not login or not password:
            return _json({"error": "missing_credentials"}, 400)
        credential = {"type": "password", "login": login, "password": password}
        try:
            auth_info = request.env["res.users"].sudo().authenticate(
                request.db, credential, {"interactive": False})
        except AccessDenied:
            return _json({"error": "invalid_credentials"}, 401)
        uid = auth_info["uid"] if isinstance(auth_info, dict) else auth_info
        user = request.env["res.users"].sudo().browse(uid)
        if not user.has_group(SMS_USER_GROUP):
            return _json({"error": "not_authorized_for_sms"}, 403)
        device = request.env["sms.archive.mobile.device"]._issue(
            uid, name=data.get("device_name"), platform=data.get("platform", "android"))
        request.update_env(user=uid)
        return _json({
            "token": device.device_token,
            "user_id": uid,
            "user_name": user.name,
            "lines": request.env["sms.archive.thread"].get_lines(),
            "config": request.env["sms.archive.thread"].get_messenger_config(),
        })

    # ── Auth par connexion web (capture le login Odoo : mot de passe, SSO
    #    Authentik « les sessions SSO », MFA — tout ce que la page /web/login offre) ──
    @http.route(f"{BASE}/auth/start", type="http", auth="user", methods=["GET"],
                csrf=False)
    def auth_start(self, **kw):
        """Ouverte dans un onglet du navigateur. ``auth='user'`` → si non
        connecté, Odoo redirige vers /web/login (mot de passe OU boutons SSO),
        puis revient ici authentifié. On émet alors un CODE unique et on
        redirige vers le deep-link de l'app. Le vrai jeton n'apparaît jamais ici."""
        redirect = kw.get("redirect") or ""
        state = kw.get("state") or ""
        if not _allowed_redirect(redirect):
            return request.make_response(
                "Redirection non autorisée.", status=400,
                headers=[("Content-Type", "text/plain; charset=utf-8")])
        user = request.env.user
        if not user.has_group(SMS_USER_GROUP):
            return request.make_response(
                "Ce compte n'a pas accès à la messagerie SMS.", status=403,
                headers=[("Content-Type", "text/plain; charset=utf-8")])
        code = request.env["sms.archive.mobile.device"]._issue_pending(
            user.id, name=kw.get("device_name"))
        sep = "&" if "?" in redirect else "?"
        target = "%s%scode=%s&state=%s" % (
            redirect, sep, urllib.parse.quote(code), urllib.parse.quote(state))
        return wz_redirect(target, code=302)

    @http.route(f"{BASE}/auth/exchange", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    def auth_exchange(self, **kw):
        """L'app échange le code unique (reçu par deep-link) contre le jeton
        porteur durable, sur HTTPS."""
        data = _body()
        device = request.env["sms.archive.mobile.device"]._exchange(
            (data.get("code") or "").strip())
        if not device:
            return _json({"error": "invalid_or_expired_code"}, 401)
        if data.get("fcm_token"):
            device.sudo().write({"fcm_token": data["fcm_token"].strip()})
        request.update_env(user=device.user_id.id)
        return _json({
            "token": device.device_token,
            "user_id": device.user_id.id,
            "user_name": device.user_id.name,
            "lines": request.env["sms.archive.thread"].get_lines(),
            "config": request.env["sms.archive.thread"].get_messenger_config(),
            "push": _push_config(),
        })

    @http.route(f"{BASE}/logout", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    @_authed
    def logout(self, device, **kw):
        device.sudo().write({"active": False, "fcm_token": False})
        return _json({"ok": True})

    # ── Bootstrap ─────────────────────────────────────────────────────
    @http.route(f"{BASE}/config", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    @_authed
    def config(self, device, **kw):
        Thread = request.env["sms.archive.thread"]
        return _json({
            "user_name": device.user_id.name,
            "lines": Thread.get_lines(),
            "config": Thread.get_messenger_config(),
            "unread": Thread.get_unread_summary(),
            "push": _push_config(),
        })

    # ── Fils ──────────────────────────────────────────────────────────
    @http.route(f"{BASE}/threads", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    @_authed
    def threads(self, device, **kw):
        archived = kw.get("archived") in ("1", "true", "True")
        line_id = int(kw["line_id"]) if kw.get("line_id") else None
        threads = request.env["sms.archive.thread"].get_messenger_threads(
            archived=archived, search=kw.get("search") or None, line_id=line_id)
        return _json({"threads": threads})

    @http.route(f"{BASE}/conversation", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    @_authed
    def conversation(self, device, **kw):
        thread_id = kw.get("thread_id")
        if not thread_id:
            return _json({"error": "missing_thread_id"}, 400)
        before_id = int(kw["before_id"]) if kw.get("before_id") else None
        data = request.env["sms.archive.thread"].get_conversation(
            int(thread_id), before_id=before_id)
        return _json(data)

    # ── Actions ───────────────────────────────────────────────────────
    @http.route(f"{BASE}/send", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    @_authed
    def send(self, device, **kw):
        data = _body()
        body = data.get("body") or ""
        line_id = data.get("line_id")
        Thread = request.env["sms.archive.thread"]
        Msg = request.env["sms.archive.message"]
        if data.get("thread_id"):
            thread = Thread.with_context(active_test=False).browse(int(data["thread_id"]))
            if not thread.exists():
                return _json({"error": "thread_not_found"}, 404)
            thread._check_messenger_access()
            dst = thread.phone_normalized
            if not line_id:
                # ligne par défaut du dernier message du fil, sinon 1re ligne
                last = thread.message_ids.filtered(lambda m: m.line_id)[:1]
                line_id = last.line_id.id if last else (
                    request.env["sms.archive.line"].search(
                        [("owner_id", "=", device.user_id.id)], limit=1).id)
        else:
            dst = data.get("phone")
        if not (dst and line_id):
            return _json({"error": "missing_destination_or_line"}, 400)
        msg_id = Msg.action_send(int(line_id), dst, body)
        msg = Msg.browse(msg_id)
        return _json({
            "ok": True,
            "thread_id": msg.thread_id.id,
            "message": msg._messenger_dict(),
        })

    @http.route(f"{BASE}/mark_read", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    @_authed
    def mark_read(self, device, **kw):
        data = _body()
        if not data.get("thread_id"):
            return _json({"error": "missing_thread_id"}, 400)
        summary = request.env["sms.archive.thread"].mark_thread_read(int(data["thread_id"]))
        return _json({"ok": True, "unread": summary})

    # ── Archivage / épinglage / contacts (parité avec la SPA web) ─────
    @http.route(f"{BASE}/thread/archive", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    @_authed
    def thread_archive(self, device, **kw):
        data = _body()
        if not data.get("thread_id"):
            return _json({"error": "missing_thread_id"}, 400)
        request.env["sms.archive.thread"].messenger_set_archived(
            int(data["thread_id"]), bool(data.get("archived", True)))
        return _json({"ok": True})

    @http.route(f"{BASE}/thread/pin", type="http", auth="public",
                methods=["POST"], csrf=False, save_session=False)
    @_authed
    def thread_pin(self, device, **kw):
        data = _body()
        if not data.get("thread_id"):
            return _json({"error": "missing_thread_id"}, 400)
        pinned = request.env["sms.archive.thread"].messenger_toggle_pin(
            int(data["thread_id"]))
        return _json({"ok": True, "is_pinned": pinned})

    @http.route(f"{BASE}/contacts", type="http", auth="public",
                methods=["GET"], csrf=False, save_session=False)
    @_authed
    def contacts(self, device, **kw):
        """Recherche de contacts pour composer un nouveau SMS."""
        term = (kw.get("q") or "").strip()
        if len(term) < 2:
            return _json({"contacts": []})
        partners = request.env["res.partner"].search_read(
            ["|", "|", ("name", "ilike", term),
             ("phone", "ilike", term), ("mobile", "ilike", term)],
            ["name", "phone", "mobile"], limit=20, order="name")
        return _json({"contacts": partners})

    # ── Push FCM ──────────────────────────────────────────────────────
    @http.route(f"{BASE}/register_push", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    @_authed
    def register_push(self, device, **kw):
        """Enregistre l'endpoint UnifiedPush (ntfy) de l'app pour cet appareil."""
        data = _body()
        endpoint = (data.get("endpoint") or "").strip()
        if not endpoint.startswith(("http://", "https://")):
            return _json({"error": "invalid_endpoint"}, 400)
        device.sudo().write({
            "push_endpoint": endpoint,
            "app_version": data.get("app_version") or device.app_version,
        })
        return _json({"ok": True})

    @http.route(f"{BASE}/register_fcm", type="http", auth="public", methods=["POST"],
                csrf=False, save_session=False)
    @_authed
    def register_fcm(self, device, **kw):
        data = _body()
        token = (data.get("fcm_token") or "").strip()
        if not token:
            return _json({"error": "missing_fcm_token"}, 400)
        device.sudo().write({
            "fcm_token": token,
            "app_version": data.get("app_version") or device.app_version,
        })
        return _json({"ok": True})
