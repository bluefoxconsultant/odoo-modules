from odoo import models, api
import re


class MailMail(models.Model):
    _inherit = 'mail.mail'

    # Old Odoo default colors to replace with the company's brand primary
    OLD_COLORS = [
        '#875A7B',  # Odoo purple (hex)
        '#875a7b',  # lowercase
        'rgb(135,90,123)',  # Odoo purple (rgb)
        'rgb(135, 90, 123)',  # with spaces
        '#714B67',  # Another Odoo purple variant
        '#714b67',  # lowercase
    ]

    def _get_brand_button_color(self):
        """Soft-coded brand primary from res.company field (owned by bluefox_branding since 18.0.2)."""
        return (self.env.company.report_brand_primary or '#714B67')

    def _get_brand_button_color_rgb(self):
        """rgb() variant of brand primary, derived from the hex value."""
        h = self._get_brand_button_color().lstrip('#')
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f'rgb({r},{g},{b})'
        except (ValueError, IndexError):
            return 'rgb(41,171,226)'

    def _replace_button_colors(self, html_content):
        """Replace old Odoo button colors with brand colors in HTML content."""
        if not html_content:
            return html_content

        result = html_content
        brand_color = self._get_brand_button_color()
        brand_color_rgb = self._get_brand_button_color_rgb()
        for old_color in self.OLD_COLORS:
            if old_color.startswith('#'):
                pattern = re.compile(re.escape(old_color), re.IGNORECASE)
                result = pattern.sub(brand_color, result)
            else:
                result = result.replace(old_color, brand_color_rgb)
        return result

    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None, **kwargs):
        """Override to replace button colors in email body before sending."""
        for mail in self:
            if mail.body_html:
                mail.body_html = self._replace_button_colors(mail.body_html)
        return super()._send(
            auto_commit=auto_commit,
            raise_exception=raise_exception,
            smtp_session=smtp_session,
            **kwargs
        )

    @api.model_create_multi
    def create(self, vals_list):
        """Override to replace button colors when mail is created."""
        for vals in vals_list:
            if vals.get('body_html'):
                vals['body_html'] = self._replace_button_colors(vals['body_html'])
            if vals.get('body'):
                vals['body'] = self._replace_button_colors(vals['body'])
        return super().create(vals_list)

    def write(self, vals):
        """Override to replace button colors when mail is updated."""
        if vals.get('body_html'):
            vals['body_html'] = self._replace_button_colors(vals['body_html'])
        if vals.get('body'):
            vals['body'] = self._replace_button_colors(vals['body'])
        return super().write(vals)
