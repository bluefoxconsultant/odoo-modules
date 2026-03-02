import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BfTimer(models.Model):
    _name = "bf.timer"
    _description = "Timer de feuille de temps"
    _order = "start_time desc"

    user_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.uid, index=True,
    )
    employee_id = fields.Many2one("hr.employee", required=True)
    project_id = fields.Many2one("project.project", required=True)
    task_id = fields.Many2one(
        "project.task", required=True,
        domain="[('project_id', '=', project_id), ('allow_timesheets', '=', True)]",
    )
    start_time = fields.Datetime(required=True, default=fields.Datetime.now)
    is_active = fields.Boolean(default=True, index=True)
    description = fields.Char()
    claimed_at = fields.Datetime(
        help="Set when a stop wizard claims this timer. Prevents other browser windows from showing the dialog.",
    )

    # -------------------------------------------------------------------------
    # RPC methods called from JS
    # -------------------------------------------------------------------------

    @api.model
    def get_active_timers(self):
        """Return active timers for the current user."""
        timers = self.search([
            ("user_id", "=", self.env.uid),
            ("is_active", "=", True),
        ])
        now = fields.Datetime.now()
        result = []
        for t in timers:
            elapsed = (now - t.start_time).total_seconds()
            result.append({
                "id": t.id,
                "project_name": t.project_id.name,
                "task_name": t.task_id.name,
                "task_id": t.task_id.id,
                "project_id": t.project_id.id,
                "start_time_iso": fields.Datetime.to_string(t.start_time),
                "elapsed_seconds": max(0, elapsed),
                "description": t.description or t.task_id.name,
            })
        return result

    @api.model
    def get_recent_tasks(self, limit=5):
        """Return the top N tasks by most recent timesheet entries.

        Pinned tasks are returned first, then recent tasks, deduplicated.
        """
        today = fields.Date.context_today(self)
        # Fetch pinned task IDs for current user
        pinned_recs = self.env["bf.timer.pinned.task"].search(
            [("user_id", "=", self.env.uid)], order="sequence, id",
        )
        pinned_task_ids = pinned_recs.mapped("task_id").ids

        self.env.cr.execute("""
            SELECT sub.task_id, sub.task_name, sub.project_id, sub.project_name,
                   sub.project_color, sub.stage_name, sub.last_date, sub.state
              FROM (
                SELECT aal.task_id,
                       pt.name AS task_name,
                       aal.project_id,
                       pp.name AS project_name,
                       pp.color AS project_color,
                       ptt.name AS stage_name,
                       pt.state AS state,
                       MAX(aal.date) AS last_date
                  FROM account_analytic_line aal
                  JOIN project_task pt ON pt.id = aal.task_id
                  JOIN project_project pp ON pp.id = aal.project_id
             LEFT JOIN project_task_type ptt ON ptt.id = pt.stage_id
                 WHERE aal.user_id = %s
                   AND aal.task_id IS NOT NULL
                   AND pt.active = true
                   AND pp.allow_timesheets = true
                 GROUP BY aal.task_id, pt.name, aal.project_id, pp.name,
                          pp.color, ptt.name, pt.state
                 ORDER BY last_date DESC
                 LIMIT %s
              ) sub
        """, (self.env.uid, limit))
        rows = self.env.cr.dictfetchall()
        # task_name / project_name / stage_name are JSONB in Odoo 18
        lang = self.env.lang or "en_US"

        def _resolve_jsonb(val):
            if isinstance(val, dict):
                return val.get(lang) or val.get("en_US") or next(iter(val.values()), "")
            return val

        def _build_entry(r, is_pinned):
            tname = _resolve_jsonb(r["task_name"])
            pname = _resolve_jsonb(r["project_name"])
            sname = _resolve_jsonb(r["stage_name"])
            last_date = r["last_date"]
            delta_days = (today - last_date).days if last_date else None
            if delta_days is not None:
                if delta_days == 0:
                    date_label = "aujourd'hui"
                elif delta_days == 1:
                    date_label = "hier"
                else:
                    date_label = f"il y a {delta_days}j"
            else:
                date_label = ""
            state = r.get("state", "")
            return {
                "task_id": r["task_id"],
                "task_name": tname,
                "project_id": r["project_id"],
                "project_name": pname,
                "project_color": r["project_color"] or 0,
                "stage_name": sname or "",
                "date_label": date_label,
                "is_closed": state in ("1_done", "1_canceled"),
                "is_pinned": is_pinned,
            }

        # Build result: pinned tasks first, then recent (deduplicated)
        seen_ids = set()
        result = []
        rows_by_task = {r["task_id"]: r for r in rows}
        # Pinned tasks first (in pinned order)
        for tid in pinned_task_ids:
            if tid in rows_by_task:
                result.append(_build_entry(rows_by_task[tid], True))
                seen_ids.add(tid)
            else:
                # Pinned task not in recent timesheets — fetch directly
                task = self.env["project.task"].browse(tid)
                if task.exists() and task.active:
                    result.append({
                        "task_id": task.id,
                        "task_name": task.name,
                        "project_id": task.project_id.id,
                        "project_name": task.project_id.name,
                        "project_color": task.project_id.color or 0,
                        "stage_name": task.stage_id.name or "",
                        "date_label": "",
                        "is_closed": task.state in ("1_done", "1_canceled"),
                        "is_pinned": True,
                    })
                    seen_ids.add(tid)
        # Then recent tasks (not already pinned)
        for r in rows:
            if r["task_id"] not in seen_ids:
                result.append(_build_entry(r, False))
                seen_ids.add(r["task_id"])
        return result

    @api.model
    def start_timer(self, task_id):
        """Start a new timer for the given task."""
        task = self.env["project.task"].browse(task_id)
        if not task.exists():
            raise UserError("Tâche introuvable.")
        if not task.allow_timesheets:
            raise UserError("Les feuilles de temps ne sont pas activées sur cette tâche.")
        existing = self.search([
            ("user_id", "=", self.env.uid),
            ("task_id", "=", task_id),
            ("is_active", "=", True),
        ], limit=1)
        if existing:
            raise UserError("Un timer est déjà en cours pour cette tâche.")
        employee = self.env.user.employee_id or self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid), ("company_id", "in", self.env.companies.ids)],
            limit=1,
        )
        if not employee:
            raise UserError("Aucun employé associé à votre compte utilisateur.")
        timer = self.create({
            "user_id": self.env.uid,
            "employee_id": employee.id,
            "project_id": task.project_id.id,
            "task_id": task.id,
            "start_time": fields.Datetime.now(),
            "is_active": True,
            "description": task.name,
        })
        return {
            "id": timer.id,
            "project_name": timer.project_id.name,
            "task_name": timer.task_id.name,
            "task_id": timer.task_id.id,
            "project_id": timer.project_id.id,
            "start_time_iso": fields.Datetime.to_string(timer.start_time),
            "elapsed_seconds": 0,
            "description": timer.description,
        }

    @api.model
    def stop_timer(self, timer_id):
        """Stop a timer and return data for the confirmation dialog."""
        timer = self.browse(timer_id)
        if not timer.exists() or timer.user_id.id != self.env.uid:
            raise UserError("Timer introuvable.")
        now = fields.Datetime.now()
        timer.write({"is_active": False, "claimed_at": now})
        elapsed = (now - timer.start_time).total_seconds()
        # Round up to nearest 5 minutes, minimum 5 minutes
        elapsed_minutes = elapsed / 60.0
        if elapsed_minutes < 5:
            suggested_minutes = 5
        else:
            suggested_minutes = math.ceil(elapsed_minutes / 5.0) * 5
        suggested_hours = round(suggested_minutes / 60.0, 4)
        return {
            "timer_id": timer.id,
            "task_name": timer.task_id.name,
            "task_id": timer.task_id.id,
            "project_name": timer.project_id.name,
            "project_id": timer.project_id.id,
            "elapsed_seconds": max(0, elapsed),
            "suggested_hours": suggested_hours,
            "suggested_minutes": suggested_minutes,
            "description": timer.description or timer.task_id.name,
        }

    @api.model
    def confirm_timesheet(self, timer_id, duration_hours, description):
        """Create the timesheet entry from a stopped timer."""
        timer = self.browse(timer_id)
        if not timer.exists() or timer.user_id.id != self.env.uid:
            raise UserError("Timer introuvable.")
        if duration_hours <= 0:
            raise ValidationError("La durée doit être supérieure à 0.")
        self.env["account.analytic.line"].create({
            "name": description or timer.task_id.name,
            "date": timer.start_time.date(),
            "unit_amount": duration_hours,
            "task_id": timer.task_id.id,
            "project_id": timer.project_id.id,
            "employee_id": timer.employee_id.id,
        })
        timer.unlink()
        return True

    @api.model
    def get_pending_timers(self):
        """Return timers that were stopped but not yet confirmed/discarded.

        Skips timers claimed within the last 5 minutes (being handled by a
        wizard in another window). Abandoned wizards become visible again
        after 5 min.
        """
        cutoff = fields.Datetime.now() - timedelta(minutes=5)
        timers = self.search([
            ("user_id", "=", self.env.uid),
            ("is_active", "=", False),
            "|",
            ("claimed_at", "=", False),
            ("claimed_at", "<", cutoff),
        ])
        now = fields.Datetime.now()
        result = []
        for t in timers:
            elapsed = (now - t.start_time).total_seconds()
            elapsed_minutes = elapsed / 60.0
            if elapsed_minutes < 5:
                suggested_minutes = 5
            else:
                suggested_minutes = math.ceil(elapsed_minutes / 5.0) * 5
            result.append({
                "timer_id": t.id,
                "task_name": t.task_id.name,
                "task_id": t.task_id.id,
                "project_name": t.project_id.name,
                "project_id": t.project_id.id,
                "elapsed_seconds": max(0, elapsed),
                "suggested_hours": round(suggested_minutes / 60.0, 4),
                "suggested_minutes": suggested_minutes,
                "description": t.description or t.task_id.name,
            })
        return result

    @api.model
    def reactivate_timer(self, timer_id):
        """Re-activate a timer that was stopped (Cancel in dialog)."""
        timer = self.browse(timer_id)
        if not timer.exists() or timer.user_id.id != self.env.uid:
            raise UserError("Timer introuvable.")
        timer.write({"is_active": True, "claimed_at": False})
        return True

    @api.model
    def discard_timer(self, timer_id):
        """Delete a timer without creating a timesheet."""
        timer = self.browse(timer_id)
        if not timer.exists() or timer.user_id.id != self.env.uid:
            raise UserError("Timer introuvable.")
        timer.unlink()
        return True

    @api.model
    def get_today_total(self):
        """Return total hours logged today by the current user."""
        today = fields.Date.context_today(self)
        self.env.cr.execute("""
            SELECT COALESCE(SUM(unit_amount), 0)
              FROM account_analytic_line
             WHERE user_id = %s AND date = %s AND project_id IS NOT NULL
        """, (self.env.uid, today))
        return self.env.cr.fetchone()[0]

    @api.model
    def get_week_total(self):
        """Return total hours logged this week (Monday-Sunday) by the current user."""
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        self.env.cr.execute("""
            SELECT COALESCE(SUM(unit_amount), 0)
              FROM account_analytic_line
             WHERE user_id = %s AND date >= %s AND date <= %s
               AND project_id IS NOT NULL
        """, (self.env.uid, monday, today))
        return self.env.cr.fetchone()[0]

    @api.model
    def get_description_presets(self):
        """Return active description presets for the stop dialog."""
        presets = self.env["bf.timer.description.preset"].search(
            [("active", "=", True)], order="sequence, id",
        )
        return [{"id": p.id, "name": p.name, "text": p.text} for p in presets]

    @api.model
    def pin_task(self, task_id):
        """Pin a task as favorite for the current user."""
        PinnedTask = self.env["bf.timer.pinned.task"]
        existing = PinnedTask.search([
            ("user_id", "=", self.env.uid),
            ("task_id", "=", task_id),
        ], limit=1)
        if not existing:
            PinnedTask.create({"user_id": self.env.uid, "task_id": task_id})
        return True

    @api.model
    def unpin_task(self, task_id):
        """Unpin a task for the current user."""
        self.env["bf.timer.pinned.task"].search([
            ("user_id", "=", self.env.uid),
            ("task_id", "=", task_id),
        ]).unlink()
        return True


class ProjectTask(models.Model):
    _inherit = "project.task"

    bf_has_active_timer = fields.Boolean(
        compute="_compute_bf_has_active_timer",
        string="Timer actif",
    )

    def _compute_bf_has_active_timer(self):
        active_timer_task_ids = set()
        if self.ids:
            self.env.cr.execute("""
                SELECT DISTINCT task_id FROM bf_timer
                 WHERE user_id = %s AND is_active = true AND task_id = ANY(%s)
            """, (self.env.uid, list(self.ids)))
            active_timer_task_ids = {r[0] for r in self.env.cr.fetchall()}
        for task in self:
            task.bf_has_active_timer = task.id in active_timer_task_ids

    def action_bf_start_timer(self):
        """Start a timer for this task (called from form button)."""
        self.ensure_one()
        return self.env["bf.timer"].start_timer(self.id)

    def action_bf_stop_timer(self):
        """Stop the active timer and open a wizard dialog instantly."""
        self.ensure_one()
        timer = self.env["bf.timer"].search([
            ("user_id", "=", self.env.uid),
            ("task_id", "=", self.id),
            ("is_active", "=", True),
        ], limit=1)
        if not timer:
            raise UserError("Aucun timer actif pour cette tâche.")
        now = fields.Datetime.now()
        timer.write({"is_active": False, "claimed_at": now})
        elapsed = (now - timer.start_time).total_seconds()
        elapsed_minutes = elapsed / 60.0
        if elapsed_minutes < 5:
            suggested_minutes = 5
        else:
            suggested_minutes = math.ceil(elapsed_minutes / 5.0) * 5
        h = int(suggested_minutes // 60)
        m = int(suggested_minutes % 60)
        elapsed_h = int(elapsed // 3600)
        elapsed_m = int((elapsed % 3600) // 60)
        elapsed_s = int(elapsed % 60)
        elapsed_display = f"{elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}"
        wizard = self.env["bf.timer.stop.wizard"].create({
            "timer_id": timer.id,
            "project_name": timer.project_id.name,
            "task_name": timer.task_id.name,
            "elapsed_display": elapsed_display,
            "hours": h,
            "minutes": m,
            "description": timer.description or timer.task_id.name,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Arrêter le timer",
            "res_model": "bf.timer.stop.wizard",
            "res_id": wizard.id,
            "views": [[False, "form"]],
            "target": "new",
        }
