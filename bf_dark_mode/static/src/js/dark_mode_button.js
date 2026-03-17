/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { cookie } from "@web/core/browser/cookie";

class BFDarkModeSystray extends Component {
    static props = {};

    _applyTheme() {
        if (this.state.color_scheme === "dark") {
            document.body.classList.add("bf_dark_mode");
        } else {
            document.body.classList.remove("bf_dark_mode");
        }
    }

    _onClick() {
        this.state.color_scheme =
            this.state.color_scheme === "light" ? "dark" : "light";
        cookie.set("bf_color_scheme", this.state.color_scheme);
        this._applyTheme();
    }

    setup() {
        this.state = useState({ color_scheme: "light" });
        super.setup();
        const stored = cookie.get("bf_color_scheme");
        if (stored) {
            this.state.color_scheme = stored;
        } else {
            cookie.set("bf_color_scheme", this.state.color_scheme);
        }
        this._applyTheme();
        onWillUpdateProps(() => this._applyTheme());
    }
}
BFDarkModeSystray.template = "bf_dark_mode.SystrayItem";

export const systrayItem = {
    Component: BFDarkModeSystray,
    isDisplayed: () => true,
};

registry
    .category("systray")
    .add("BFDarkModeSystrayItem", systrayItem, { sequence: 1 });
