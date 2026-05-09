import base64
import logging

import werkzeug

from odoo import _, http
from odoo.http import request
from odoo.tools import plaintext2html

_logger = logging.getLogger(__name__)


class BFHelpdeskPublicForm(http.Controller):
    """Per-team public support form at /support/<slug>.

    Anonymous-friendly: visitors enter name/email; the ticket is created
    with channel = web (helpdesk_mgmt.helpdesk_ticket_channel_web) and the
    matching team_id.
    """

    def _team_by_slug(self, slug):
        if not slug:
            return False
        return request.env["helpdesk.ticket.team"].sudo().search([
            ("slug", "=", slug),
            ("active", "=", True),
            ("public_form_enabled", "=", True),
        ], limit=1)

    @http.route(["/support/<string:slug>"], type="http", auth="public", website=True, sitemap=True)
    def public_form(self, slug, **kw):
        team = self._team_by_slug(slug)
        if not team:
            return request.not_found()
        prefill = {
            "name": "",
            "email": "",
            "subject": "",
            "description": "",
        }
        if not request.env.user._is_public():
            prefill["name"] = request.env.user.partner_id.name or ""
            prefill["email"] = request.env.user.partner_id.email or ""
        return request.render("bf_helpdesk.public_form_page", {
            "team": team,
            "prefill": prefill,
            "tags": team.public_form_tag_ids,
            "max_upload_size": request.env["ir.http"].session_info().get(
                "max_file_upload_size", 25 * 1024 * 1024,
            ),
        })

    @http.route(["/support/<string:slug>/submit"], type="http", auth="public",
                website=True, methods=["POST"], csrf=True)
    def public_form_submit(self, slug, **kw):
        team = self._team_by_slug(slug)
        if not team:
            return request.not_found()

        subject = (kw.get("subject") or "").strip()
        description = (kw.get("description") or "").strip()
        name = (kw.get("name") or "").strip()
        email = (kw.get("email") or "").strip()

        # Tag selection (optional or required per team config)
        tag_id_raw = (kw.get("tag_id") or "").strip()
        selected_tag_id = False
        if tag_id_raw:
            try:
                tid = int(tag_id_raw)
                if tid in team.public_form_tag_ids.ids:
                    selected_tag_id = tid
            except ValueError:
                selected_tag_id = False

        missing_required = (
            not subject or not description or not email
            or (team.public_form_tag_required and not selected_tag_id)
        )
        if missing_required:
            return request.render("bf_helpdesk.public_form_page", {
                "team": team,
                "tags": team.public_form_tag_ids,
                "prefill": {"name": name, "email": email,
                            "subject": subject, "description": description,
                            "tag_id": tag_id_raw},
                "error": _("Sujet, description et courriel sont requis."),
                "max_upload_size": request.env["ir.http"].session_info().get(
                    "max_file_upload_size", 25 * 1024 * 1024,
                ),
            })

        Ticket = request.env["helpdesk.ticket"].sudo()
        partner_id = False
        if not request.env.user._is_public():
            partner_id = request.env.user.partner_id.id

        channel = request.env.ref(
            "helpdesk_mgmt.helpdesk_ticket_channel_web", raise_if_not_found=False,
        )

        vals = {
            "name": subject,
            "description": plaintext2html(description),
            "partner_name": name or email,
            "partner_email": email,
            "team_id": team.id,
            "channel_id": channel.id if channel else False,
            "company_id": team.company_id.id or request.env.company.id,
        }
        if partner_id:
            vals["partner_id"] = partner_id
        if selected_tag_id:
            vals["tag_ids"] = [(4, selected_tag_id)]
        # Set initial stage to ensure mail tracking template fires
        vals["stage_id"] = team._get_applicable_stages()[:1].id

        ticket = Ticket.create(vals)

        # Attachments
        attachment_files = request.httprequest.files.getlist("attachment")
        for c_file in attachment_files:
            if not c_file or not c_file.filename:
                continue
            data = c_file.read()
            if not data:
                continue
            request.env["ir.attachment"].sudo().create({
                "name": c_file.filename,
                "datas": base64.b64encode(data),
                "res_model": "helpdesk.ticket",
                "res_id": ticket.id,
            })

        if partner_id:
            ticket.message_subscribe(partner_ids=[partner_id])

        # Redirect logged-in users to portal; anonymous to a thank-you page
        if partner_id:
            return werkzeug.utils.redirect(f"/my/ticket/{ticket.id}")
        return request.render("bf_helpdesk.public_form_thanks", {
            "team": team,
            "ticket": ticket,
        })
