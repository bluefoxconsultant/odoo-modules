import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class BfUniversalSearch(models.Model):
    _name = "bf.universal.search"
    _description = "Recherche universelle"
    _auto = False

    @api.model
    def search_all(self, query, model_filters=None, limit=5):
        """Search across all configured models, respecting ACLs.

        Returns a list of groups:
        [
            {
                "model": "res.partner",
                "model_label": "Contacts",
                "icon": "fa fa-users",
                "category": "search_contacts",
                "results": [
                    {"id": 42, "name": "Blue Fox Inc", "detail": "info@example.com"},
                    ...
                ],
            },
            ...
        ]
        """
        if not query or len(query) < 2:
            return []

        configs = self.env["bf.universal.search.config"].search([
            ("active", "=", True),
        ])

        if model_filters:
            configs = configs.filtered(
                lambda c: c.model_name in model_filters
            )

        groups = []
        for config in configs:
            model_name = config.model_name
            # Skip models that are not installed
            if model_name not in self.env:
                continue

            # Check read access
            try:
                self.env["ir.model.access"].check(model_name, "read")
            except Exception:
                continue

            search_limit = config.limit or limit
            search_field_names = [
                f.strip() for f in config.search_fields.split(",") if f.strip()
            ]
            if not search_field_names:
                continue

            # Validate fields exist on the model
            Model = self.env[model_name]
            valid_fields = [
                f for f in search_field_names if f in Model._fields
            ]
            if not valid_fields:
                continue

            # Build OR domain across all search fields
            domain = [
                "|" if i > 0 else ""
                for i in range(len(valid_fields) - 1)
            ]
            # Filter out empty strings and build proper domain
            domain = []
            if len(valid_fields) > 1:
                for _i in range(len(valid_fields) - 1):
                    domain.append("|")
            for field_name in valid_fields:
                domain.append((field_name, "ilike", query))

            try:
                # Determine fields to read
                read_fields = list(set(valid_fields + ["display_name"]))
                records = Model.search_read(
                    domain,
                    fields=read_fields,
                    limit=search_limit,
                )
            except Exception:
                _logger.warning(
                    "Universal search: error searching %s",
                    model_name,
                    exc_info=True,
                )
                continue

            if not records:
                continue

            # Build result list
            results = []
            for rec in records:
                name = rec.get("display_name") or rec.get(valid_fields[0]) or ""
                # Detail = first non-name field that has a value
                detail = ""
                for field_name in valid_fields:
                    if field_name == "name":
                        continue
                    val = rec.get(field_name)
                    if val and isinstance(val, str):
                        detail = val
                        break

                results.append({
                    "id": rec["id"],
                    "name": name,
                    "detail": detail,
                })

            groups.append({
                "model": model_name,
                "model_label": config.name,
                "icon": config.icon or "fa fa-search",
                "category": config.category,
                "results": results,
            })

        return groups
