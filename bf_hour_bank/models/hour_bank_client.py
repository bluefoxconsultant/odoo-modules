import base64
import io
import logging
from collections import defaultdict
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    _logger.warning("openpyxl not installed — Excel generation disabled")
    openpyxl = None


class HourBankClient(models.Model):
    _name = 'hour.bank.client'
    _description = "Configuration de banque d'heures client"
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        compute='_compute_name', store=True, string="Nom",
    )
    partner_id = fields.Many2one(
        'res.partner', required=True, string="Client",
        tracking=True,
    )
    project_ids = fields.Many2many(
        'project.project', string="Projets inclus",
    )
    product_filter_mode = fields.Selection([
        ('all', 'Toutes les lignes de facture'),
        ('include', 'Inclure seulement ces produits'),
        ('exclude', 'Exclure ces produits'),
    ], string="Filtre produits", default='all', required=True)
    filter_product_ids = fields.Many2many(
        'product.product', string="Produits",
    )
    company_filter_mode = fields.Selection([
        ('all', 'Toutes les sociétés'),
        ('include', 'Inclure seulement ces sociétés'),
        ('exclude', 'Exclure ces sociétés'),
    ], string="Filtre sociétés", default='all', required=True)
    filter_company_ids = fields.Many2many(
        'res.company', string="Sociétés",
    )
    invoice_partner_ids = fields.Many2many(
        'res.partner', 'hour_bank_invoice_partner_rel',
        string="Partenaires de facturation",
        help="Si renseigné, seules les factures émises à ces partenaires seront comptées. "
             "Sinon, toutes les factures du partenaire commercial seront incluses.",
    )
    extra_invoice_ids = fields.Many2many(
        'account.move', string="Factures additionnelles",
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted')]",
    )
    adjustment_ids = fields.One2many(
        'hour.bank.adjustment', 'hour_bank_id',
        string="Ajustements manuels",
    )
    recipient_ids = fields.Many2many(
        'res.partner', 'hour_bank_recipient_rel',
        string="Destinataires du rapport",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )
    current_balance = fields.Float(
        compute='_compute_balance', string="Solde actuel",
    )
    last_report_date = fields.Datetime(
        string="Dernier rapport", tracking=True,
    )
    auto_send = fields.Boolean(
        string="Envoi automatique", default=False, tracking=True,
    )
    send_frequency = fields.Selection([
        ('weekly', 'Hebdomadaire (lundi)'),
        ('biweekly', 'Aux deux semaines (lundi)'),
        ('monthly', 'Mensuel (1er du mois)'),
    ], string="Fréquence d'envoi", default='weekly')

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends('partner_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.partner_id.name or _("Nouveau")

    def _compute_balance(self):
        for rec in self:
            data = rec._get_report_data()
            rec.current_balance = data['balance']

    # ------------------------------------------------------------------
    # Core: build report data
    # ------------------------------------------------------------------

    def _get_report_data(self, date_from=None, date_to=None):
        """Build the full hour-bank dataset (debits + credits) for self.

        Returns dict with keys:
            entries: list of dicts sorted date ASC
            balance: final cumulative balance
            summary_by_project: {project_name: total_hours}
            summary_by_month: {(year, month): {project_name: hours}}
            last_update: datetime
        """
        self.ensure_one()

        if not self.project_ids:
            return {
                'entries': [],
                'balance': 0.0,
                'summary_by_project': {},
                'summary_by_month': {},
                'last_update': fields.Datetime.now(),
            }

        project_ids = tuple(self.project_ids.ids)
        partner_id = self.partner_id.commercial_partner_id.id or self.partner_id.id

        # ---- Debits: timesheets ----
        ts_where = "aal.project_id IN %s"
        ts_params = [project_ids]
        if date_from:
            ts_where += " AND aal.date >= %s"
            ts_params.append(date_from)
        if date_to:
            ts_where += " AND aal.date <= %s"
            ts_params.append(date_to)

        ts_sql = f"""
            SELECT
                aal.date AS entry_date,
                -aal.unit_amount AS hours,
                aal.name AS description,
                pp.name->>'en_US' AS project_name,
                pt.name AS task_name,
                'debit' AS entry_type,
                aal.id AS source_id
            FROM account_analytic_line aal
            JOIN project_project pp ON pp.id = aal.project_id
            LEFT JOIN project_task pt ON pt.id = aal.task_id
            WHERE {ts_where}
        """

        # ---- Credits: posted customer invoices ----
        inv_where = """
            am.move_type = 'out_invoice'
            AND am.state = 'posted'
        """
        inv_params = []

        # Company filter
        if self.filter_company_ids and self.company_filter_mode == 'include':
            inv_where += " AND am.company_id IN %s"
            inv_params.append(tuple(self.filter_company_ids.ids))
        elif self.filter_company_ids and self.company_filter_mode == 'exclude':
            inv_where += " AND am.company_id NOT IN %s"
            inv_params.append(tuple(self.filter_company_ids.ids))

        # Partner filter: specific partners or commercial partner fallback
        extra_ids = tuple(self.extra_invoice_ids.ids) if self.extra_invoice_ids else ()
        if self.invoice_partner_ids:
            partner_filter_ids = tuple(self.invoice_partner_ids.ids)
            if extra_ids:
                inv_where += " AND (am.partner_id IN %s OR am.id IN %s)"
                inv_params += [partner_filter_ids, extra_ids]
            else:
                inv_where += " AND am.partner_id IN %s"
                inv_params.append(partner_filter_ids)
        else:
            if extra_ids:
                inv_where += " AND (am.commercial_partner_id = %s OR am.id IN %s)"
                inv_params += [partner_id, extra_ids]
            else:
                inv_where += " AND am.commercial_partner_id = %s"
                inv_params.append(partner_id)

        if self.filter_product_ids and self.product_filter_mode == 'include':
            inv_where += " AND aml.product_id IN %s"
            inv_params.append(tuple(self.filter_product_ids.ids))
        elif self.filter_product_ids and self.product_filter_mode == 'exclude':
            inv_where += " AND (aml.product_id IS NULL OR aml.product_id NOT IN %s)"
            inv_params.append(tuple(self.filter_product_ids.ids))

        if date_from:
            inv_where += " AND am.invoice_date >= %s"
            inv_params.append(date_from)
        if date_to:
            inv_where += " AND am.invoice_date <= %s"
            inv_params.append(date_to)

        inv_sql = f"""
            SELECT
                am.invoice_date AS entry_date,
                aml.quantity AS hours,
                am.name AS description,
                'Heures factur\u00e9es' AS project_name,
                NULL AS task_name,
                'credit' AS entry_type,
                aml.id AS source_id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE {inv_where}
              AND aml.quantity > 0
              AND aml.display_type = 'product'
        """

        # ---- Adjustments: manual entries ----
        adj_where = "hba.hour_bank_id = %s"
        adj_params = [self.id]
        if date_from:
            adj_where += " AND hba.date >= %s"
            adj_params.append(date_from)
        if date_to:
            adj_where += " AND hba.date <= %s"
            adj_params.append(date_to)

        adj_sql = f"""
            SELECT
                hba.date AS entry_date,
                hba.hours AS hours,
                hba.description AS description,
                'Ajustement' AS project_name,
                NULL AS task_name,
                CASE WHEN hba.hours >= 0 THEN 'credit' ELSE 'debit' END AS entry_type,
                hba.id + 1000000000 AS source_id
            FROM hour_bank_adjustment hba
            WHERE {adj_where}
        """

        # ---- Union + order ----
        sql = f"""
            SELECT * FROM (
                ({ts_sql})
                UNION ALL
                ({inv_sql})
                UNION ALL
                ({adj_sql})
            ) combined
            ORDER BY entry_date ASC, entry_type DESC, source_id ASC
        """
        params = ts_params + inv_params + adj_params
        self.env.cr.execute(sql, params)
        rows = self.env.cr.dictfetchall()

        # ---- Build entries with cumulative balance ----
        entries = []
        balance = 0.0
        summary_by_project = defaultdict(float)
        # summary_by_month: {(year, month): {project: hours}}
        summary_by_month = defaultdict(lambda: defaultdict(float))

        for row in rows:
            balance += row['hours']
            entry = {
                'date': row['entry_date'],
                'hours': row['hours'],
                'cumulative': balance,
                'description': row['description'] or '',
                'project': row['project_name'] or '',
                'task': row['task_name'] or '',
                'entry_type': row['entry_type'],
            }
            entries.append(entry)

            # Summaries
            summary_by_project[entry['project']] += row['hours']
            dt = row['entry_date']
            summary_by_month[(dt.year, dt.month)][entry['project']] += row['hours']

        # Reverse for display (most recent first)
        entries.reverse()

        return {
            'entries': entries,
            'balance': balance,
            'summary_by_project': dict(summary_by_project),
            'summary_by_month': {k: dict(v) for k, v in summary_by_month.items()},
            'last_update': fields.Datetime.now(),
        }

    # ------------------------------------------------------------------
    # PDF generation
    # ------------------------------------------------------------------

    def action_generate_pdf(self):
        """Generate the PDF report and return download action."""
        self.ensure_one()
        return self.env.ref(
            'bf_hour_bank.action_report_hour_bank'
        ).report_action(self)

    def _get_pdf_binary(self):
        """Generate PDF as binary for attachment purposes."""
        self.ensure_one()
        pdf_content, _content_type = self.env['ir.actions.report']._render_qweb_pdf(
            'bf_hour_bank.action_report_hour_bank', self.ids,
        )
        return pdf_content

    # ------------------------------------------------------------------
    # Excel generation
    # ------------------------------------------------------------------

    def action_generate_xlsx(self):
        """Generate Excel and return download action."""
        self.ensure_one()
        xlsx_data = self._generate_xlsx_binary()
        filename = "Banque_heures_%s_%s.xlsx" % (
            self.partner_id.name.replace(' ', '_'),
            fields.Date.today().isoformat(),
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'new',
        }

    def _generate_xlsx_binary(self):
        """Build a 4-sheet .xlsx and return raw bytes."""
        self.ensure_one()
        if not openpyxl:
            raise UserError(_("La biblioth\u00e8que openpyxl n'est pas install\u00e9e."))

        data = self._get_report_data()
        wb = openpyxl.Workbook()

        # Styles
        header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
        header_fill = PatternFill(start_color='2E3132', end_color='2E3132', fill_type='solid')
        credit_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
        number_fmt = '#,##0.00'
        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9'),
        )

        def style_header(ws, cols):
            for idx, col in enumerate(cols, 1):
                cell = ws.cell(row=1, column=idx, value=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center')
                cell.border = thin_border

        # ─── Sheet 1: Feuilles de temps ───
        ws1 = wb.active
        ws1.title = "Feuilles de temps"
        cols1 = ["Date", "Nombre d'heures", "Solde cumulatif", "Description", "Projet", "Tâche"]
        style_header(ws1, cols1)

        for i, entry in enumerate(data['entries'], 2):
            ws1.cell(row=i, column=1, value=entry['date']).number_format = 'YYYY-MM-DD'
            ws1.cell(row=i, column=2, value=entry['hours']).number_format = number_fmt
            ws1.cell(row=i, column=3, value=entry['cumulative']).number_format = number_fmt
            ws1.cell(row=i, column=4, value=entry['description'])
            ws1.cell(row=i, column=5, value=entry['project'])
            ws1.cell(row=i, column=6, value=entry['task'])
            for c in range(1, 7):
                ws1.cell(row=i, column=c).border = thin_border
            if entry['entry_type'] == 'credit':
                for c in range(1, 7):
                    ws1.cell(row=i, column=c).fill = credit_fill

        # Auto-width
        for col_idx in range(1, 7):
            ws1.column_dimensions[get_column_letter(col_idx)].width = (
                [14, 16, 16, 40, 25, 25][col_idx - 1]
            )

        # ─── Sheet 2: Sommaire par projet ───
        ws2 = wb.create_sheet("Sommaire par projet")
        cols2 = ["Projet", "Heures totales"]
        style_header(ws2, cols2)
        row = 2
        for project, hours in sorted(data['summary_by_project'].items()):
            ws2.cell(row=row, column=1, value=project).border = thin_border
            cell = ws2.cell(row=row, column=2, value=hours)
            cell.number_format = number_fmt
            cell.border = thin_border
            row += 1
        ws2.column_dimensions['A'].width = 40
        ws2.column_dimensions['B'].width = 18

        # ─── Sheet 3: Synth\u00e8se par mois ───
        ws3 = wb.create_sheet("Synth\u00e8se par mois")
        # Collect all projects for column headers
        all_projects = sorted(set(
            p for month_data in data['summary_by_month'].values()
            for p in month_data
        ))
        cols3 = ["Mois"] + all_projects + ["Total"]
        style_header(ws3, cols3)

        row = 2
        for (year, month), proj_hours in sorted(data['summary_by_month'].items()):
            ws3.cell(row=row, column=1, value=f"{year}-{month:02d}").border = thin_border
            month_total = 0.0
            for col_idx, proj in enumerate(all_projects, 2):
                val = proj_hours.get(proj, 0.0)
                cell = ws3.cell(row=row, column=col_idx, value=val)
                cell.number_format = number_fmt
                cell.border = thin_border
                month_total += val
            cell = ws3.cell(row=row, column=len(all_projects) + 2, value=month_total)
            cell.number_format = number_fmt
            cell.border = thin_border
            cell.font = Font(bold=True)
            row += 1

        ws3.column_dimensions['A'].width = 14
        for idx in range(2, len(all_projects) + 3):
            ws3.column_dimensions[get_column_letter(idx)].width = 20

        # ─── Sheet 4: \u00c0 facturer ───
        ws4 = wb.create_sheet("\u00c0 facturer")
        cols4 = ["Date", "Heures", "Description", "Projet", "T\u00e2che"]
        style_header(ws4, cols4)

        # Entries since last credit (invoice)
        unbilled = []
        for entry in reversed(data['entries']):
            if entry['entry_type'] == 'credit':
                break
            unbilled.insert(0, entry)

        row = 2
        total_unbilled = 0.0
        for entry in unbilled:
            ws4.cell(row=row, column=1, value=entry['date']).number_format = 'YYYY-MM-DD'
            ws4.cell(row=row, column=2, value=entry['hours']).number_format = number_fmt
            ws4.cell(row=row, column=3, value=entry['description'])
            ws4.cell(row=row, column=4, value=entry['project'])
            ws4.cell(row=row, column=5, value=entry['task'])
            for c in range(1, 6):
                ws4.cell(row=row, column=c).border = thin_border
            total_unbilled += entry['hours']
            row += 1

        # Total row
        ws4.cell(row=row, column=1, value="TOTAL").font = Font(bold=True)
        ws4.cell(row=row, column=1).border = thin_border
        total_cell = ws4.cell(row=row, column=2, value=total_unbilled)
        total_cell.number_format = number_fmt
        total_cell.font = Font(bold=True)
        total_cell.border = thin_border

        ws4.column_dimensions['A'].width = 14
        ws4.column_dimensions['B'].width = 14
        ws4.column_dimensions['C'].width = 40
        ws4.column_dimensions['D'].width = 25
        ws4.column_dimensions['E'].width = 25

        # Write to buffer
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Open send wizard
    # ------------------------------------------------------------------

    def action_open_send_wizard(self):
        """Open the email-send wizard with pre-generated attachments."""
        self.ensure_one()
        wizard = self.env['hour.bank.send.wizard'].create({
            'hour_bank_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Envoyer le rapport"),
            'res_model': 'hour.bank.send.wizard',
            'res_id': wizard.id,
            'views': [[False, 'form']],
            'target': 'new',
        }

    # ------------------------------------------------------------------
    # Automated sending (cron)
    # ------------------------------------------------------------------

    def _send_report_to_recipients(self):
        """Generate and send branded report email to recipients.

        Used by both the cron and can be called programmatically.
        """
        self.ensure_one()
        if not self.recipient_ids:
            _logger.info("Hour bank %s: no recipients configured, skipping", self.name)
            return

        WizardModel = self.env['hour.bank.send.wizard']

        partner_name = self.partner_id.name.replace(' ', '_')
        date_str = fields.Date.today().isoformat()

        # Generate PDF
        pdf_data = self._get_pdf_binary()
        pdf_att = self.env['ir.attachment'].create({
            'name': "Banque_heures_%s_%s.pdf" % (partner_name, date_str),
            'type': 'binary',
            'datas': base64.b64encode(pdf_data),
            'mimetype': 'application/pdf',
            'res_model': self._name,
            'res_id': self.id,
        })

        # Generate Excel
        xlsx_data = self._generate_xlsx_binary()
        xlsx_att = self.env['ir.attachment'].create({
            'name': "Banque_heures_%s_%s.xlsx" % (partner_name, date_str),
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })

        # Build branded body
        inner_body = (
            '<p style="font-size:16px;line-height:26px;color:#374151;'
            'margin:0 0 16px 0;">Bonjour,</p>'
            '<p style="font-size:16px;line-height:26px;color:#374151;'
            'margin:0 0 20px 0;">Veuillez trouver ci-joint '
            "l'&#233;tat des banques d'heures pour "
            "<strong>%s</strong>.</p>"
            '<p style="font-size:16px;line-height:26px;color:#374151;'
            'margin:0 0 20px 0;">Les fichiers PDF et Excel sont '
            "en pi&#232;ces jointes.</p>"
            '<p style="font-size:16px;line-height:26px;color:#374151;'
            'margin:0;">Cordialement,<br/>Blue Fox</p>'
        ) % self.partner_id.name

        body_html = WizardModel.new({})._wrap_branded_body(inner_body)

        subject = "État des banques d'heures — %s" % self.partner_id.name
        sender = self.company_id.email or self.env.user.email_formatted

        for partner in self.recipient_ids:
            if not partner.email:
                continue
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body_html,
                'email_from': sender,
                'email_to': partner.email_formatted or partner.email,
                'recipient_ids': [(4, partner.id)],
                'attachment_ids': [(6, 0, [pdf_att.id, xlsx_att.id])],
            })
            mail.send()

        self.write({'last_report_date': fields.Datetime.now()})

        recipient_names = ', '.join(self.recipient_ids.mapped('name'))
        self.message_post(
            body=_("Rapport automatique envoyé à %s") % recipient_names,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
            attachment_ids=[pdf_att.id, xlsx_att.id],
        )
        _logger.info("Hour bank %s: report sent to %s", self.name, recipient_names)

    @api.model
    def _cron_send_reports(self):
        """Cron job: send reports for all active auto-send hour banks."""
        today = fields.Date.today()
        weekday = today.weekday()  # 0=Monday
        day = today.day

        banks = self.search([('auto_send', '=', True), ('active', '=', True)])
        for bank in banks:
            try:
                send = False
                if bank.send_frequency == 'weekly' and weekday == 0:
                    send = True
                elif bank.send_frequency == 'biweekly' and weekday == 0:
                    # Send on even ISO weeks
                    if today.isocalendar()[1] % 2 == 0:
                        send = True
                elif bank.send_frequency == 'monthly' and day == 1:
                    send = True

                if send:
                    bank._send_report_to_recipients()
            except Exception:
                _logger.exception(
                    "Hour bank cron: failed to send report for %s", bank.name
                )
