# ui/theme.py — Konstanta warna dan fungsi theming tkinter
# Salin dari ui_theme.py lama — hanya bagian konstanta & fungsi tema.
# Fungsi render (render_bgr_to_label_*, dll) dipindah ke ui/widgets/preview_helpers.py

import tkinter as tk
from tkinter import ttk


# ── Palet warna utama ─────────────────────────────────────────────────────────
MIXED_THEME = {
    "bg_root":      "#06162B",
    "bg_surface":   "#0B1F38",
    "bg_panel":     "#102847",
    "bg_input":     "#0D223C",
    "bg_button":    "#1F4E7A",
    "fg_primary":   "#EAF2FF",
    "fg_muted":     "#C4D4E8",
    "fg_on_accent": "#F8FAFC",
    "accent":       "#4FA3FF",
    "preview_bg":   "#0A1D33",
}

# ── Ukuran preview per window ─────────────────────────────────────────────────
PREVIEW_PROFILES = {
    "default": {
        "live":      (720, 405),
        "result":    (560, 315),
        "histogram": (560, 315),
    },
    "camera_window": {
        "live":      (860, 484),
        "result":    (640, 360),
        "histogram": (560, 315),
    },
    "camera_color_window": {
        "live":      (960, 540),
        "result":    (560, 315),
        "histogram": (560, 315),
    },
    "conversion_window": {
        "live":      (760, 428),
        "result":    (620, 349),
        "histogram": (560, 315),
    },
    "analisis_filter": {
        "live":      (760, 428),
        "result":    (620, 349),
        "histogram": (420, 260),
    },
    "image_analysis_window": {
        "live":      (760, 428),
        "result":    (620, 349),
        "histogram": (620, 300),
    },
    "analisis_warna": {
        "live":      (760, 428),
        "result":    (620, 349),
        "histogram": (560, 315),
    },
}

LIVE_PREVIEW_W, LIVE_PREVIEW_H     = PREVIEW_PROFILES["default"]["live"]
RESULT_PREVIEW_W, RESULT_PREVIEW_H = PREVIEW_PROFILES["default"]["result"]


# ── Helper: nilai default yang perlu di-override ──────────────────────────────
_LIGHT_BG_VALUES = {
    "#ecf0f1", "#f4f6f7", "#d0d3d4", "#d9e2ee", "#e3eaf3",
    "#e9eef5", "#f4f7fb", "#ffffff", "white", "systembuttonface",
}
_LIGHT_FG_VALUES = {
    "#111111", "#1f2937", "#1f4d7a", "#2c3e50", "#333333",
    "#4b5563", "#7f8c8d", "#b45309", "black",
}


def _normalize_color(value):
    if not value:
        return ""
    return str(value).strip().lower()


def _get(widget, option):
    try:
        return widget.cget(option)
    except Exception:
        return None


def _set(widget, **kwargs):
    try:
        widget.configure(**kwargs)
    except Exception:
        pass


def _apply_widget_colors(widget, theme):
    """Terapkan warna tema ke satu widget berdasarkan tipe widget."""
    cls = widget.winfo_class()
    bg  = _normalize_color(_get(widget, "bg"))
    fg  = _normalize_color(_get(widget, "fg"))

    if cls in {"Toplevel", "Tk"}:
        _set(widget, bg=theme["bg_root"])
        return

    if cls in {"Frame", "Labelframe", "LabelFrame"}:
        if bg in _LIGHT_BG_VALUES:
            _set(widget, bg=theme["bg_surface"])
        if fg in _LIGHT_FG_VALUES:
            _set(widget, fg=theme["fg_primary"])
        return

    if cls == "Label":
        if bg in _LIGHT_BG_VALUES:
            _set(widget, bg=theme["bg_surface"])
        if fg in _LIGHT_FG_VALUES:
            _set(widget, fg=theme["fg_primary"])
        return

    if cls in {"Entry", "Text", "Listbox"}:
        if bg in _LIGHT_BG_VALUES:
            _set(widget, bg=theme["bg_input"])
        if fg in _LIGHT_FG_VALUES:
            _set(widget, fg=theme["fg_primary"])
        _set(widget, insertbackground=theme["fg_primary"])
        return

    if cls in {"Checkbutton", "Radiobutton", "Scale"}:
        if bg in _LIGHT_BG_VALUES:
            _set(widget, bg=theme["bg_surface"])
        if fg in _LIGHT_FG_VALUES:
            _set(widget, fg=theme["fg_primary"])
        _set(widget, highlightthickness=0)
        if cls in {"Checkbutton", "Radiobutton"}:
            _set(widget, selectcolor=theme["bg_input"],
                 activeforeground=theme["fg_primary"])
        return

    if cls == "Button":
        # Button berwarna custom dibiarkan tetap seperti semula
        if bg in _LIGHT_BG_VALUES:
            _set(
                widget,
                bg=theme["bg_button"],
                fg=theme["fg_on_accent"],
                activebackground=theme["accent"],
                activeforeground=theme["fg_on_accent"],
                bd=1,
            )
        elif fg in _LIGHT_FG_VALUES and bg in {"", "systembuttonface"}:
            _set(widget, fg=theme["fg_primary"])
        return

    if cls == "Canvas" and bg in _LIGHT_BG_VALUES:
        _set(widget, bg=theme["bg_input"])
        return


def _apply_ttk_theme(widget, theme):
    """Terapkan style tema ke widget ttk (Treeview, Scrollbar)."""
    try:
        style = ttk.Style(widget)
        style.theme_use("clam")
    except Exception:
        return

    style.configure(
        "Treeview",
        background=theme["bg_input"],
        fieldbackground=theme["bg_input"],
        foreground=theme["fg_primary"],
        bordercolor=theme["bg_panel"],
        lightcolor=theme["bg_panel"],
        darkcolor=theme["bg_panel"],
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", theme["accent"])],
        foreground=[("selected", "white")],
    )
    style.configure(
        "Treeview.Heading",
        background=theme["bg_panel"],
        foreground=theme["fg_primary"],
        bordercolor=theme["bg_panel"],
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", theme["bg_button"])])
    style.configure(
        "TScrollbar",
        background=theme["bg_panel"],
        troughcolor=theme["bg_root"],
        arrowcolor=theme["fg_primary"],
    )


def apply_mixed_theme(root_widget, theme=None):
    """
    Terapkan tema gelap ke seluruh pohon widget secara rekursif.
    Dipanggil setelah semua widget dibuat.
    """
    palette = theme or MIXED_THEME
    stack = [root_widget]
    while stack:
        node = stack.pop()
        _apply_widget_colors(node, palette)
        try:
            stack.extend(node.winfo_children())
        except Exception:
            continue
    _apply_ttk_theme(root_widget, palette)


def apply_dark_blue_theme(root_widget, theme=None):
    """Alias backward-compatible untuk apply_mixed_theme."""
    apply_mixed_theme(root_widget, theme=theme)


# ── Re-export dari preview_helpers (backward-compat) ─────────────────────────
# analisis_warna_window.py dan window lain yang import resize_cover_rgb
# dari ui_theme lama bisa tetap berfungsi tanpa perubahan.
from ui.widgets.preview_helpers import (  # noqa: E402
    resize_cover_rgb,
    render_bgr_to_label_cover,
    render_bgr_to_label_stable,
    render_gray_to_label_cover,
    get_widget_target_size,
    create_preview_stage,
    bind_preview_card,
)
