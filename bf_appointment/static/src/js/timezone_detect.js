/**
 * Timezone detection and form helpers for bf_appointment.
 */
document.addEventListener("DOMContentLoaded", function () {
    // Timezone auto-detection
    const tzField = document.getElementById("bf_appointment_tz");
    if (tzField && !tzField.value) {
        try {
            tzField.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
        } catch (e) {
            // Fallback: leave empty, server will use type's calendar TZ
        }
    }

    // Prevent double-submit on confirm buttons
    document.querySelectorAll(".bf-btn-confirm").forEach(function (btn) {
        btn.closest("form").addEventListener("submit", function () {
            btn.disabled = true;
            btn.style.opacity = "0.5";
            btn.innerHTML = '<i class="fa fa-spinner fa-spin me-1"></i> Confirmation\u2026';
        });
    });
});
