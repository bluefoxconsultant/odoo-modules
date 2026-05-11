from odoo import models, api
import re


class MailRenderMixin(models.AbstractModel):
    _inherit = 'mail.render.mixin'

    # Old Odoo default colors to replace with the company's brand primary
    OLD_COLORS = [
        '#875A7B',  # Odoo purple (hex)
        '#875a7b',  # lowercase
        'rgb(135,90,123)',  # Odoo purple (rgb)
        'rgb(135, 90, 123)',  # with spaces
        '#714B67',  # Another Odoo purple variant
        '#714b67',  # lowercase
    ]

    @api.model
    def _get_brand_button_color(self):
        return (self.env.company.report_brand_primary or '#714B67')

    @api.model
    def _get_brand_button_color_rgb(self):
        h = self._get_brand_button_color().lstrip('#')
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f'rgb({r},{g},{b})'
        except (ValueError, IndexError):
            return 'rgb(113,75,103)'

    @api.model
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

    @api.model
    def _render_template(self, template_src, model, res_ids, engine='inline_template',
                         add_context=None, options=None):
        """Override to replace button colors in rendered email templates."""
        result = super()._render_template(
            template_src, model, res_ids, engine=engine,
            add_context=add_context, options=options
        )

        # Replace colors in all rendered results
        if isinstance(result, dict):
            for res_id, content in result.items():
                if isinstance(content, str):
                    result[res_id] = self._replace_button_colors(content)
        elif isinstance(result, str):
            result = self._replace_button_colors(result)

        return result
