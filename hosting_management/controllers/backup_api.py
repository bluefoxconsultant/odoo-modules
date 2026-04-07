# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class BackupAPIController(http.Controller):
    """API endpoint for receiving backup reports from external systems."""

    @http.route(
        "/api/hosting/backup/report",
        type="http",
        auth="api_key",
        methods=["POST"],
        csrf=False,
    )
    def receive_backup_report(self, **kwargs):
        """
        Receive backup report data and create backup run record.

        Expected JSON payload:
        {
            "timestamp": "2026-02-03 17:40:00",
            "hostname": "server1",
            "backup_root": "/path/to/backups",
            "summary": {
                "total": 13,
                "success": 10,
                "failed": 1,
                "skipped": 2
            },
            "results": [
                {
                    "service": "Nextcloud",
                    "status": "success",
                    "duration": "245s",
                    "error": "",
                    "files": [
                        {
                            "name": "backup.zip",
                            "size": "1.2G",
                            "checksum": "abc123...",
                            "verified": true
                        }
                    ]
                }
            ]
        }
        """
        try:
            data = json.loads(request.httprequest.data)
            _logger.info("Received backup report from %s", data.get("hostname", "unknown"))

            # Create the backup run
            run_vals = {
                "hostname": data.get("hostname"),
                "backup_root": data.get("backup_root"),
                "notes": f"Received via API at {data.get('timestamp')}",
            }

            # Parse timestamp if provided
            timestamp = data.get("timestamp")
            if timestamp:
                try:
                    from datetime import datetime
                    run_vals["run_date"] = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            run = request.env["hosting.backup.run"].sudo().create(run_vals)

            # Create backup lines
            results = data.get("results", [])
            for result in results:
                line_vals = {
                    "run_id": run.id,
                    "service_name": result.get("service", "Unknown"),
                    "status": result.get("status", "failed"),
                    "duration": result.get("duration", "-"),
                    "error_message": result.get("error", ""),
                    "container_count": result.get("container_count", 0),
                    "verified_file_count": result.get("verified_count", 0),
                }
                line = request.env["hosting.backup.line"].sudo().create(line_vals)

                # Create file records
                files = result.get("files", [])
                for file_data in files:
                    file_vals = {
                        "line_id": line.id,
                        "name": file_data.get("name", ""),
                        "size": file_data.get("size", ""),
                        "checksum": file_data.get("checksum", ""),
                        "verified": file_data.get("verified", False),
                    }
                    request.env["hosting.backup.file"].sudo().create(file_vals)

            _logger.info("Created backup run %s with %d lines", run.name, len(results))

            # Send the report email
            run.action_send_report()

            return request.make_json_response({
                "success": True,
                "backup_run_id": run.id,
                "backup_run_name": run.name,
                "message": "Backup report created and email sent",
            })

        except Exception:
            _logger.exception("Error processing backup report")
            return request.make_json_response({
                "success": False,
                "error": "Internal server error",
            }, status=500)

    @http.route(
        "/api/hosting/backup/report/public",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_backup_report_public(self, **kwargs):
        """
        Public endpoint with token authentication for backup reports.
        Requires X-Backup-Token header matching system parameter.
        """
        try:
            # Check token
            token = request.httprequest.headers.get("X-Backup-Token")
            expected_token = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("hosting.backup_api_token", "")
            )

            if not expected_token or expected_token == "CHANGE_ME_TO_SECURE_TOKEN":
                return request.make_json_response(
                    {"success": False, "error": "API token not configured"},
                    status=500
                )

            if not token or not hmac.compare_digest(token, expected_token):
                return request.make_json_response(
                    {"success": False, "error": "Invalid API token"},
                    status=401
                )

            # Process the report using the same logic
            return self.receive_backup_report(**kwargs)

        except Exception:
            _logger.exception("Error processing backup report (public)")
            return request.make_json_response({
                "success": False,
                "error": "Internal server error",
            }, status=500)
