import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk


MIXED_THEME = {
    "bg_root": "#06162B",
    "bg_surface": "#0B1F38",
    "bg_panel": "#102847",
    "bg_input": "#0D223C",
    "bg_button": "#1F4E7A",
    "fg_primary": "#EAF2FF",
    "fg_muted": "#C4D4E8",
    "fg_on_accent": "#F8FAFC",
    "accent": "#4FA3FF",
    "preview_bg": "#0A1D33",
}

PREVIEW_PROFILES = {
    "default": {
        "live": (720, 405),
        "result": (560, 315),
        "histogram": (560, 315),
    },
    "camera_window": {
        "live": (860, 484),
        "result": (640, 360),
        "histogram": (560, 315),
    },
    "camera_color_window": {
        "live": (960, 540),
        "result": (560, 315),
        "histogram": (560, 315),
    },
    "conversion_window": {
        "live": (760, 428),
        "result": (620, 349),
        "histogram": (560, 315),
    },
    "analisis_filter": {
        "live": (760, 428),
        "result": (620, 349),
        "histogram": (420, 260),
    },
    "image_analysis_window": {
        "live": (760, 428),
        "result": (620, 349),
        "histogram": (620, 300),
    },
    "analisis_warna": {
        "live": (760, 428),
        "result": (620, 349),
        "histogram": (560, 315),
    },
}

LIVE_PREVIEW_W, LIVE_PREVIEW_H = PREVIEW_PROFILES["default"]["live"]
RESULT_PREVIEW_W, RESULT_PREVIEW_H = PREVIEW_PROFILES["default"]["result"]

_LIGHT_BG_VALUES = {
    "#ecf0f1",
    "#f4f6f7",
    "#d0d3d4",
    "#d9e2ee",
    "#e3eaf3",
    "#e9eef5",
    "#f4f7fb",
    "#ffffff",
    "white",
    "systembuttonface",
}
_LIGHT_FG_VALUES = {
    "#111111",
    "#1f2937",
    "#1f4d7a",
    "#2c3e50",
    "#333333",
    "#4b5563",
    "#7f8c8d",
    "#b45309",
    "black",
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
    cls = widget.winfo_class()
    bg = _normalize_color(_get(widget, "bg"))
    fg = _normalize_color(_get(widget, "fg"))

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
            _set(widget, selectcolor=theme["bg_input"], activeforeground=theme["fg_primary"])
        return

    if cls == "Button":
        # Biarkan button berwarna custom tetap seperti semula.
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
    # Backward-compatible alias.
    apply_mixed_theme(root_widget, theme=theme)


def get_widget_target_size(widget, default_w=640, default_h=420, min_w=220, min_h=160):
    try:
        widget.update_idletasks()
        w = int(widget.winfo_width())
        h = int(widget.winfo_height())
    except Exception:
        w, h = default_w, default_h
    if w <= 1:
        w = default_w
    if h <= 1:
        h = default_h
    return max(min_w, w), max(min_h, h)


def resize_cover_rgb(rgb_image, target_w, target_h):
    src_h, src_w = rgb_image.shape[:2]
    if src_h <= 0 or src_w <= 0:
        return rgb_image

    ratio = max(target_w / float(src_w), target_h / float(src_h))
    ratio = max(ratio, 1e-6)
    new_w = max(1, int(src_w * ratio))
    new_h = max(1, int(src_h * ratio))
    interp = cv2.INTER_CUBIC if ratio > 1.0 else cv2.INTER_AREA
    resized = cv2.resize(rgb_image, (new_w, new_h), interpolation=interp)

    x0 = max(0, (new_w - target_w) // 2)
    y0 = max(0, (new_h - target_h) // 2)
    x1 = min(new_w, x0 + target_w)
    y1 = min(new_h, y0 + target_h)
    cropped = resized[y0:y1, x0:x1]
    if cropped.shape[1] != target_w or cropped.shape[0] != target_h:
        cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_AREA)
    return cropped


def _autocrop_dark_borders_bgr(bgr_image, threshold=10):
    if bgr_image is None:
        return bgr_image

    h, w = bgr_image.shape[:2]
    if h < 60 or w < 60:
        return bgr_image

    try:
        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    except Exception:
        return bgr_image

    active = gray > int(threshold)
    if not np.any(active):
        return bgr_image

    row_ratio = active.mean(axis=1)
    col_ratio = active.mean(axis=0)
    min_active_ratio = 0.02
    valid_rows = np.where(row_ratio > min_active_ratio)[0]
    valid_cols = np.where(col_ratio > min_active_ratio)[0]
    if valid_rows.size == 0 or valid_cols.size == 0:
        return bgr_image

    top = int(valid_rows[0])
    bottom = int(valid_rows[-1]) + 1
    left = int(valid_cols[0])
    right = int(valid_cols[-1]) + 1

    trim_top = top
    trim_bottom = h - bottom
    trim_left = left
    trim_right = w - right
    total_trim = trim_top + trim_bottom + trim_left + trim_right
    min_total_trim = max(16, int(min(h, w) * 0.06))
    if total_trim < min_total_trim:
        return bgr_image

    crop_h = bottom - top
    crop_w = right - left
    if crop_h < int(h * 0.55) or crop_w < int(w * 0.55):
        return bgr_image

    border_regions = []
    if trim_top > 0:
        border_regions.append(gray[:top, :])
    if trim_bottom > 0:
        border_regions.append(gray[bottom:, :])
    if trim_left > 0:
        border_regions.append(gray[:, :left])
    if trim_right > 0:
        border_regions.append(gray[:, right:])

    if not border_regions:
        return bgr_image

    border_pixels = np.concatenate([r.ravel() for r in border_regions if r.size > 0])
    if border_pixels.size == 0:
        return bgr_image
    if float(np.mean(border_pixels)) > 35.0:
        return bgr_image

    return bgr_image[top:bottom, left:right]


def render_bgr_to_label_cover(label_widget, bgr_image, default_w=640, default_h=420, trim_black=True):
    if bgr_image is None:
        return

    if bgr_image.ndim == 2:
        bgr = cv2.cvtColor(bgr_image, cv2.COLOR_GRAY2BGR)
    elif bgr_image.ndim == 3 and bgr_image.shape[2] == 4:
        bgr = cv2.cvtColor(bgr_image, cv2.COLOR_BGRA2BGR)
    else:
        bgr = bgr_image

    if trim_black:
        bgr = _autocrop_dark_borders_bgr(bgr)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    tw, th = get_widget_target_size(label_widget, default_w=default_w, default_h=default_h)
    rendered = resize_cover_rgb(rgb, tw, th)
    photo = ImageTk.PhotoImage(Image.fromarray(rendered))
    try:
        label_widget.configure(image=photo, text="")
        label_widget.image = photo
    except Exception:
        pass


def render_bgr_to_label_stable(
    label_widget,
    bgr_image,
    base_w=LIVE_PREVIEW_W,
    base_h=LIVE_PREVIEW_H,
    trim_black=True,
    allow_upscale=False,
    neutral_bg="#243447",
):
    if bgr_image is None:
        return

    if bgr_image.ndim == 2:
        bgr = cv2.cvtColor(bgr_image, cv2.COLOR_GRAY2BGR)
    elif bgr_image.ndim == 3 and bgr_image.shape[2] == 4:
        bgr = cv2.cvtColor(bgr_image, cv2.COLOR_BGRA2BGR)
    else:
        bgr = bgr_image

    if trim_black:
        bgr = _autocrop_dark_borders_bgr(bgr)

    widget_w, widget_h = get_widget_target_size(
        label_widget,
        default_w=base_w,
        default_h=base_h,
        min_w=120,
        min_h=90,
    )

    if allow_upscale:
        target_w = widget_w
        target_h = widget_h
    else:
        target_w = min(widget_w, max(120, int(base_w)))
        target_h = min(widget_h, max(90, int(base_h)))

    target_w = max(120, int(target_w))
    target_h = max(90, int(target_h))

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rendered = resize_cover_rgb(rgb, target_w, target_h)
    photo = ImageTk.PhotoImage(Image.fromarray(rendered))

    try:
        label_widget.configure(image=photo, text="", anchor="center", bg=neutral_bg)
        label_widget.image = photo
    except Exception:
        pass


def render_gray_to_label_cover(label_widget, gray_image, default_w=640, default_h=420, trim_black=True):
    if gray_image is None:
        return
    if gray_image.ndim != 2:
        gray = cv2.cvtColor(gray_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = gray_image
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    render_bgr_to_label_cover(
        label_widget,
        bgr,
        default_w=default_w,
        default_h=default_h,
        trim_black=trim_black,
    )


def bind_preview_card(stage_widget, card_widget, base_w, base_h, margin=8, min_w=120, min_h=90):
    """
    Keep a preview card centered in its stage.
    Card never grows above base size; it only shrinks if stage gets smaller.
    """

    def _relayout(_event=None):
        try:
            stage_widget.update_idletasks()
            stage_w = max(1, int(stage_widget.winfo_width()) - (2 * int(margin)))
            stage_h = max(1, int(stage_widget.winfo_height()) - (2 * int(margin)))
        except Exception:
            stage_w, stage_h = int(base_w), int(base_h)

        try:
            bw = max(1, int(base_w))
            bh = max(1, int(base_h))
            scale = min(stage_w / float(bw), stage_h / float(bh), 1.0)
        except Exception:
            scale = 1.0
            bw, bh = int(base_w), int(base_h)

        target_w = max(int(min_w), int(round(bw * scale)))
        target_h = max(int(min_h), int(round(bh * scale)))

        try:
            card_widget.place(relx=0.5, rely=0.5, anchor="center", width=target_w, height=target_h)
        except Exception:
            pass

    try:
        stage_widget.bind("<Configure>", _relayout)
        stage_widget.after(10, _relayout)
    except Exception:
        pass


def create_preview_stage(
    parent,
    base_w,
    base_h,
    stage_bg="#173A5E",
    card_bg="#243447",
    empty_text="Belum ada gambar",
    fg="#F8FAFC",
    font=("Arial", 10),
    margin=8,
):
    stage = tk.Frame(
        parent,
        bg=stage_bg,
        width=max(1, int(base_w) + (2 * int(margin))),
        height=max(1, int(base_h) + (2 * int(margin))),
    )
    try:
        stage.pack_propagate(False)
        stage.grid_propagate(False)
    except Exception:
        pass
    card = tk.Frame(stage, bg=card_bg, bd=1, relief="solid")
    label = tk.Label(card, bg=card_bg, fg=fg, text=empty_text, anchor="center", font=font)
    label.pack(fill="both", expand=True)
    bind_preview_card(stage, card, base_w=base_w, base_h=base_h, margin=margin)
    return stage, label
