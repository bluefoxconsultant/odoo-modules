from odoo import api, fields, models


class AppointmentIntakeField(models.Model):
    _name = "appointment.intake.field"
    _description = "Appointment Intake Form Field"
    _order = "sequence, id"

    type_id = fields.Many2one(
        "resource.booking.type",
        string="Booking Type",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Label", required=True, translate=True)
    field_type = fields.Selection(
        [
            ("text", "Text"),
            ("textarea", "Text (multi-line)"),
            ("email", "Email"),
            ("phone", "Phone"),
            ("number", "Number"),
            ("select", "Dropdown"),
        ],
        string="Type",
        default="text",
        required=True,
    )
    required = fields.Boolean(default=False)
    placeholder = fields.Char(translate=True)
    select_options = fields.Text(
        string="Options (one per line)",
        help="For dropdown fields, enter one option per line.",
    )
    sequence = fields.Integer(default=10)


class AppointmentIntakeAnswer(models.Model):
    _name = "appointment.intake.answer"
    _description = "Appointment Intake Form Answer"

    booking_id = fields.Many2one(
        "resource.booking",
        string="Booking",
        required=True,
        ondelete="cascade",
    )
    field_id = fields.Many2one(
        "appointment.intake.field",
        string="Field",
        required=True,
        ondelete="cascade",
    )
    value = fields.Text(string="Answer")
    field_name = fields.Char(related="field_id.name", string="Question")
