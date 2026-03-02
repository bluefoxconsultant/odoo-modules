import base64

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request, content_disposition

from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalHourBank(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'hour_bank_count' in counters:
            partner = request.env.user.partner_id.commercial_partner_id
            count = request.env['hour.bank.client'].sudo().search_count(
                [('partner_id', '=', partner.id)]
            )
            values['hour_bank_count'] = count
        return values

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------

    @http.route(
        ['/my/hour-banks', '/my/hour-banks/page/<int:page>'],
        type='http', auth='user', website=True,
    )
    def portal_my_hour_banks(self, page=1, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        HourBank = request.env['hour.bank.client'].sudo()
        domain = [('partner_id', '=', partner.id)]
        hour_banks = HourBank.search(domain, order='name asc')
        values = self._prepare_portal_layout_values()
        values.update({
            'hour_banks': hour_banks,
            'page_name': 'hour_banks',
            'default_url': '/my/hour-banks',
        })
        return request.render('bf_hour_bank.portal_my_hour_banks', values)

    # ------------------------------------------------------------------
    # Detail view
    # ------------------------------------------------------------------

    @http.route(
        ['/my/hour-banks/<int:hour_bank_id>'],
        type='http', auth='user', website=True,
    )
    def portal_hour_bank_detail(self, hour_bank_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        hour_bank = request.env['hour.bank.client'].sudo().search([
            ('id', '=', hour_bank_id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if not hour_bank:
            return request.redirect('/my/hour-banks')

        data = hour_bank._get_report_data()
        values = self._prepare_portal_layout_values()
        values.update({
            'hour_bank': hour_bank,
            'data': data,
            'page_name': 'hour_bank_detail',
        })
        return request.render('bf_hour_bank.portal_hour_bank_page', values)

    # ------------------------------------------------------------------
    # PDF download
    # ------------------------------------------------------------------

    @http.route(
        ['/my/hour-banks/<int:hour_bank_id>/pdf'],
        type='http', auth='user', website=True,
    )
    def portal_hour_bank_pdf(self, hour_bank_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        hour_bank = request.env['hour.bank.client'].sudo().search([
            ('id', '=', hour_bank_id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if not hour_bank:
            return request.redirect('/my/hour-banks')

        pdf_data = hour_bank._get_pdf_binary()
        filename = "Banque_heures_%s.pdf" % hour_bank.partner_id.name.replace(' ', '_')
        return request.make_response(
            pdf_data,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

    # ------------------------------------------------------------------
    # Excel download
    # ------------------------------------------------------------------

    @http.route(
        ['/my/hour-banks/<int:hour_bank_id>/xlsx'],
        type='http', auth='user', website=True,
    )
    def portal_hour_bank_xlsx(self, hour_bank_id, **kw):
        partner = request.env.user.partner_id.commercial_partner_id
        hour_bank = request.env['hour.bank.client'].sudo().search([
            ('id', '=', hour_bank_id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if not hour_bank:
            return request.redirect('/my/hour-banks')

        xlsx_data = hour_bank._generate_xlsx_binary()
        filename = "Banque_heures_%s.xlsx" % hour_bank.partner_id.name.replace(' ', '_')
        return request.make_response(
            xlsx_data,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )
