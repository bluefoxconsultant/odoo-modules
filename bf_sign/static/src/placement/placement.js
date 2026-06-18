/** @odoo-module **/

import { Component, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DISPLAY_W = 680; // page render width in px
const COLORS = ["#29ABE1", "#E67E22", "#27AE60", "#8E44AD", "#E74C3C", "#16A085"];
const TYPE_LABELS = { signature: "Signature", initials: "Paraphe", date: "Date", text: "Texte" };
const DEFAULT_SIZE = {
    signature: { width: 0.28, height: 0.07 },
    initials: { width: 0.12, height: 0.06 },
    date: { width: 0.18, height: 0.04 },
    text: { width: 0.18, height: 0.04 },
};
// Default fill mode per type when a pad is placed.
const FILL_DEFAULT = { date: "auto", text: "signer" };

/**
 * Backend drag-and-drop widget to place signature pads on a PDF.
 * Renders the document with PDF.js and persists each placed pad as a
 * bf.sign.field (coordinates stored as fractions of the page, top-left origin).
 */
export class BfSignPlacement extends Component {
    static template = "bf_sign.Placement";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.state = useState({
            message: "",
            pages: [],
            signers: [],
            fields: [],
            activeSignerId: null,
            armedType: null,
            templates: [],
            selectedTemplate: "",
        });
        this._drag = null;
        // signerId → signer, rebuilt on each data load (cheap O(1) lookups).
        this._signerById = new Map();
        // Identity of the document currently rasterized into state.pages, so a
        // data reload (arm / save / apply template) does not re-render the PDF.
        this._renderedKey = null;
        this._docSig = 0;

        onWillStart(async () => {
            try {
                await this.loadData();
            } catch (e) {
                console.error("bf_sign placement: chargement échoué", e);
                this.state.message =
                    "Impossible de charger l'aperçu du document. Enregistrez la demande, " +
                    "puis utilisez « Recharger ».";
            }
        });
    }

    get resId() {
        return this.props.record && this.props.record.resId;
    }

    // ── Data + render ───────────────────────────────────────────────────────
    // loadData() refreshes the ORM data and (re)rasterizes the PDF only when the
    // document actually changed, so toolbar/template actions stay instant.
    async loadData() {
        await this._loadData();
        await this._renderPdfIfNeeded();
    }

    async _loadData() {
        const id = this.resId;
        this.state.message = "";
        this.state.fields = [];
        this.state.signers = [];
        this._signerById = new Map();
        if (!id) {
            this.state.pages = [];
            this._renderedKey = null;
            this._docSig = 0;
            this.state.message = "Enregistrez la demande avant de placer les pavés.";
            return;
        }
        this.state.templates = await this.orm.searchRead(
            "bf.sign.field.template", [], ["name"]);
        // Presence + change-signature come from the already-loaded form record
        // (no heavy binary round-trip); PDF.js streams the bytes separately. The
        // base64 length changes whenever the document is replaced.
        const data = (this.props.record && this.props.record.data) || {};
        this._docSig = (data.document_file || "").length;
        if (!data.document_file) {
            this.state.pages = [];
            this._renderedKey = null;
            this.state.message = "Téléversez un document PDF, puis enregistrez.";
            return;
        }
        this.state.signers = (await this.orm.searchRead(
            "bf.sign.signer", [["request_id", "=", id]], ["name", "email"]
        )).map((s, i) => ({ ...s, color: COLORS[i % COLORS.length] }));
        this._signerById = new Map(this.state.signers.map((s) => [s.id, s]));
        if (!this.state.signers.length) {
            this.state.pages = [];
            this._renderedKey = null;
            this.state.message = "Ajoutez au moins un signataire, puis enregistrez.";
            return;
        }
        // Keep the current active signer across reloads when still valid.
        if (!this._signerById.has(this.state.activeSignerId)) {
            this.state.activeSignerId = this.state.signers[0].id;
        }

        const raw = await this.orm.searchRead(
            "bf.sign.field", [["request_id", "=", id]],
            ["signer_id", "field_type", "page", "pos_x", "pos_y", "width", "height", "fill_mode"]
        );
        this.state.fields = raw.map((f) => ({
            ...f,
            signerId: Array.isArray(f.signer_id) ? f.signer_id[0] : f.signer_id,
        }));
    }

    async _renderPdfIfNeeded() {
        const id = this.resId;
        if (!id || !this._docSig) {
            return;
        }
        const key = `${id}|${this._docSig}`;
        if (this._renderedKey === key && this.state.pages.length) {
            return; // already rasterized this document — reuse cached pages
        }
        await this._renderPdf(key);
    }

    // Render each PDF page to an OFFSCREEN canvas → data URL, shown as the page
    // background <img>. Done once per document; markers are drawn reactively
    // from state.fields on top of the cached pages.
    async _renderPdf(key) {
        const id = this.resId;
        const pages = [];
        try {
            const pdfjsLib = await this._pdfjs();
            const url = `/web/content/bf.sign.request/${id}/document_file`;
            const pdf = await pdfjsLib.getDocument(url).promise;
            for (let n = 1; n <= pdf.numPages; n++) {
                const page = await pdf.getPage(n);
                const base = page.getViewport({ scale: 1 });
                const scale = DISPLAY_W / base.width;
                const vp = page.getViewport({ scale });
                const canvas = document.createElement("canvas");
                canvas.width = vp.width;
                canvas.height = vp.height;
                await page.render({
                    canvasContext: canvas.getContext("2d"), viewport: vp,
                }).promise;
                pages.push({
                    num: n, w: vp.width, h: vp.height, img: canvas.toDataURL("image/png"),
                });
            }
            this.state.pages = pages;
            this._renderedKey = key;
        } catch (e) {
            console.error("bf_sign placement: rendu PDF échoué", e);
            this.state.pages = [];
            this._renderedKey = null;
            this.state.message =
                "Le document n'a pas pu être affiché (" + (e && e.message ? e.message : e) + ").";
        }
    }

    // Odoo ships pdf.js as an ES module: rely on the global if the web client
    // already set it, otherwise import the module on demand (a classic loadJS
    // would silently fail on its top-level `export`).
    async _pdfjs() {
        if (window.pdfjsLib) {
            return window.pdfjsLib;
        }
        const lib = await import("/web/static/lib/pdfjs/build/pdf.js");
        try {
            lib.GlobalWorkerOptions.workerSrc =
                "/web/static/lib/pdfjs/build/pdf.worker.js";
        } catch (e) {
            /* worker optional */
        }
        return lib;
    }

    // ── Reload / dirty guard ────────────────────────────────────────────────
    async reload() {
        // Re-fetch data; the PDF is re-rasterized only if the document changed.
        await this.loadData();
    }

    async forceReload() {
        // Manual "Recharger": drop the page cache and re-render from scratch
        // (e.g. after replacing the uploaded document).
        this._renderedKey = null;
        this.state.pages = [];
        await this.loadData();
    }

    get isDirty() {
        return Boolean(this.props.record && this.props.record.isDirty);
    }

    // Pads can only be placed/edited while the request is a draft (mirrors the
    // model-side lock). When locked, existing pads stay visible but read-only.
    get isLocked() {
        const data = this.props.record && this.props.record.data;
        return Boolean(data && data.state && data.state !== "draft");
    }

    // ── Toolbar ──────────────────────────────────────────────────────────────
    // Pads/templates are persisted immediately (orm) and need a saved parent.
    // Auto-save the form first (transparently) so it works right from creation.
    // Returns false if the record still can't be used (validation error / missing
    // document or signers).
    async _ensureSaved() {
        if (!this.resId || this.isDirty) {
            try {
                await this.props.record.save();
            } catch {
                return false;
            }
            await this.reload();
            if (this.state.message) {
                return false;
            }
        }
        return true;
    }

    async arm(type) {
        if (this.isLocked) {
            this.notification.add(
                "La demande n'est plus en brouillon : les pavés sont verrouillés.",
                { type: "warning" });
            return;
        }
        if (!(await this._ensureSaved())) {
            return;
        }
        this.state.armedType = this.state.armedType === type ? null : type;
    }

    // ── Field-layout templates ───────────────────────────────────────────────
    onTemplateChange(ev) {
        this.state.selectedTemplate = ev.target.value;
    }

    async applyTemplate() {
        if (!this.state.selectedTemplate) {
            this.notification.add("Choisissez un modèle.", { type: "warning" });
            return;
        }
        if (!(await this._ensureSaved())) {
            return;
        }
        if (this.state.fields.length &&
            !window.confirm("Remplacer les pavés actuels par ceux du modèle ?")) {
            return;
        }
        const res = await this.orm.call("bf.sign.request", "apply_field_template",
            [this.resId, parseInt(this.state.selectedTemplate, 10)]);
        await this.reload();
        let msg = `${res.created} pavé(s) placé(s)`;
        if (res.skipped) {
            msg += ` — ${res.skipped} ignoré(s) (pas assez de signataires)`;
        }
        this.notification.add(msg, { type: "success" });
    }

    async saveTemplate() {
        if (!(await this._ensureSaved())) {
            return;
        }
        if (!this.state.fields.length) {
            this.notification.add("Placez d'abord des pavés à enregistrer.", { type: "warning" });
            return;
        }
        const name = window.prompt("Nom du modèle :", "");
        if (name === null) {
            return;
        }
        await this.orm.call("bf.sign.request", "save_field_template", [this.resId, name || ""]);
        this.state.templates = await this.orm.searchRead(
            "bf.sign.field.template", [], ["name"]);
        this.notification.add("Modèle enregistré.", { type: "success" });
    }

    async setFillMode(f, mode) {
        const prev = f.fill_mode;
        f.fill_mode = mode;
        try {
            await this.orm.write("bf.sign.field", [f.id], { fill_mode: mode });
        } catch (e) {
            f.fill_mode = prev;
            this.notification.add(
                "Échec de l'enregistrement du mode de remplissage.", { type: "danger" });
        }
    }
    onSignerChange(ev) {
        this.state.activeSignerId = parseInt(ev.target.value, 10);
    }
    signerColor(signerId) {
        const s = this._signerById.get(signerId);
        return s ? s.color : "#888";
    }
    activeColor() {
        return this.signerColor(this.state.activeSignerId);
    }
    signerName(signerId) {
        const s = this._signerById.get(signerId);
        return s ? s.name : "";
    }
    labelFor(f) {
        return `${TYPE_LABELS[f.field_type] || f.field_type} · ${this.signerName(f.signerId)}`;
    }

    // ── Rendering helpers ──────────────────────────────────────────────────────
    fieldsForPage(num) {
        return this.state.fields.filter((f) => f.page === num);
    }
    boxStyle(f, pg) {
        const color = this.signerColor(f.signerId);
        return (
            `left:${f.pos_x * pg.w}px;top:${f.pos_y * pg.h}px;` +
            `width:${f.width * pg.w}px;height:${f.height * pg.h}px;` +
            `border-color:${color};background:${color}22;`
        );
    }

    // ── Placement ──────────────────────────────────────────────────────────────
    async onPageClick(ev, pg) {
        if (this.isLocked || !this.state.armedType || !this.state.activeSignerId) {
            return;
        }
        if (ev.target.closest && ev.target.closest(".bf-box")) {
            return;
        }
        const rect = ev.currentTarget.getBoundingClientRect();
        const fracX = (ev.clientX - rect.left) / rect.width;
        const fracY = (ev.clientY - rect.top) / rect.height;
        const size = DEFAULT_SIZE[this.state.armedType];
        const posX = Math.min(Math.max(fracX - size.width / 2, 0), 1 - size.width);
        const posY = Math.min(Math.max(fracY - size.height / 2, 0), 1 - size.height);
        const fillMode = FILL_DEFAULT[this.state.armedType] || "signer";
        const vals = {
            request_id: this.resId,
            signer_id: this.state.activeSignerId,
            field_type: this.state.armedType,
            page: pg.num,
            pos_x: posX,
            pos_y: posY,
            width: size.width,
            height: size.height,
            fill_mode: fillMode,
        };
        let id;
        try {
            [id] = await this.orm.create("bf.sign.field", [vals]);
        } catch (e) {
            this.notification.add("Échec de la création du pavé.", { type: "danger" });
            return;
        }
        this.state.fields.push({
            id,
            field_type: vals.field_type,
            page: pg.num,
            pos_x: posX,
            pos_y: posY,
            width: size.width,
            height: size.height,
            fill_mode: fillMode,
            signerId: this.state.activeSignerId,
        });
        this.state.armedType = null;
    }

    async removeField(f) {
        if (this.isLocked) {
            return;
        }
        try {
            await this.orm.unlink("bf.sign.field", [f.id]);
        } catch (e) {
            this.notification.add("Échec de la suppression du pavé.", { type: "danger" });
            return;
        }
        const idx = this.state.fields.indexOf(f);
        if (idx >= 0) {
            this.state.fields.splice(idx, 1);
        }
    }

    // ── Drag & resize ──────────────────────────────────────────────────────────
    startDrag(ev, f, pg) {
        if (this.isLocked) {
            return;
        }
        ev.preventDefault();
        this._drag = {
            f, pg, mode: "move",
            startX: ev.clientX, startY: ev.clientY,
            origX: f.pos_x, origY: f.pos_y,
        };
        this._bindDragEvents();
    }
    startResize(ev, f, pg) {
        if (this.isLocked) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this._drag = {
            f, pg, mode: "resize",
            startX: ev.clientX, startY: ev.clientY,
            origX: f.pos_x, origY: f.pos_y,
            origW: f.width, origH: f.height,
        };
        this._bindDragEvents();
    }
    _bindDragEvents() {
        this._onMove = (e) => this._onDragMove(e);
        this._onUp = (e) => this._onDragUp(e);
        window.addEventListener("pointermove", this._onMove);
        window.addEventListener("pointerup", this._onUp);
    }
    _onDragMove(e) {
        if (!this._drag) {
            return;
        }
        const { f, pg, mode } = this._drag;
        const dx = (e.clientX - this._drag.startX) / pg.w;
        const dy = (e.clientY - this._drag.startY) / pg.h;
        if (mode === "move") {
            f.pos_x = Math.min(Math.max(this._drag.origX + dx, 0), 1 - f.width);
            f.pos_y = Math.min(Math.max(this._drag.origY + dy, 0), 1 - f.height);
        } else {
            f.width = Math.min(Math.max(this._drag.origW + dx, 0.04), 1 - f.pos_x);
            f.height = Math.min(Math.max(this._drag.origH + dy, 0.02), 1 - f.pos_y);
        }
    }
    async _onDragUp() {
        window.removeEventListener("pointermove", this._onMove);
        window.removeEventListener("pointerup", this._onUp);
        const drag = this._drag;
        this._drag = null;
        if (!drag) {
            return;
        }
        const f = drag.f;
        try {
            await this.orm.write("bf.sign.field", [f.id], {
                pos_x: f.pos_x, pos_y: f.pos_y, width: f.width, height: f.height,
            });
        } catch (e) {
            // Revert to the pre-drag geometry so the UI matches the DB.
            f.pos_x = drag.origX;
            f.pos_y = drag.origY;
            if (drag.mode === "resize") {
                f.width = drag.origW;
                f.height = drag.origH;
            }
            this.notification.add(
                "Échec de l'enregistrement du pavé (position non sauvegardée).",
                { type: "danger" });
        }
    }
}

registry.category("view_widgets").add("bf_sign_placement", {
    component: BfSignPlacement,
});
