# ui/widgets/preview_helpers.py — Helper render frame OpenCV ke widget tkinter Label
# Dipindahkan dari ui_theme.py. Fungsi-fungsi tema (warna, dsb.) ada di ui/theme.py.

import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk


# ── Ukuran default ────────────────────────────────────────────────────────────
_DEFAULT_W = 640
_DEFAULT_H = 420


def get_widget_target_size(widget, default_w=_DEFAULT_W, default_h=_DEFAULT_H,
                           min_w=220, min_h=160) -> tuple[int, int]:
    """
    Baca ukuran widget yang sudah di-render.
    Fallback ke default_w / default_h jika widget belum di-render.
    """
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


def resize_cover_rgb(rgb_image: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """
    Resize gambar RGB dengan mode COVER (fill + center crop).
    Gambar mengisi penuh area target tanpa letterbox.
    """
    src_h, src_w = rgb_image.shape[:2]
    if src_h <= 0 or src_w <= 0:
        return rgb_image

    ratio  = max(target_w / float(src_w), target_h / float(src_h))
    ratio  = max(ratio, 1e-6)
    new_w  = max(1, int(src_w * ratio))
    new_h  = max(1, int(src_h * ratio))
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


def _autocrop_dark_borders_bgr(bgr_image: np.ndarray, threshold: int = 10) -> np.ndarray:
    """
    Potong border gelap dari gambar BGRsecara otomatis.
    Hanya memotong jika border cukup gelap dan luas.
    """
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

    top    = int(valid_rows[0])
    bottom = int(valid_rows[-1]) + 1
    left   = int(valid_cols[0])
    right  = int(valid_cols[-1]) + 1

    trim_top    = top
    trim_bottom = h - bottom
    trim_left   = left
    trim_right  = w - right
    total_trim  = trim_top + trim_bottom + trim_left + trim_right
    min_total_trim = max(16, int(min(h, w) * 0.06))
    if total_trim < min_total_trim:
        return bgr_image

    crop_h = bottom - top
    crop_w = right - left
    if crop_h < int(h * 0.55) or crop_w < int(w * 0.55):
        return bgr_image

    border_regions = []
    if trim_top    > 0: border_regions.append(gray[:top,   :])
    if trim_bottom > 0: border_regions.append(gray[bottom:, :])
    if trim_left   > 0: border_regions.append(gray[:,   :left])
    if trim_right  > 0: border_regions.append(gray[:, right:])

    if not border_regions:
        return bgr_image
    border_pixels = np.concatenate([r.ravel() for r in border_regions if r.size > 0])
    if border_pixels.size == 0 or float(np.mean(border_pixels)) > 35.0:
        return bgr_image

    return bgr_image[top:bottom, left:right]


def render_bgr_to_label_cover(label_widget, bgr_image: np.ndarray,
                               default_w: int = _DEFAULT_W, default_h: int = _DEFAULT_H,
                               trim_black: bool = True) -> None:
    """
    Render gambar BGR ke tkinter Label dengan mode COVER.
    Label akan diisi penuh oleh gambar (crop jika perlu).
    """
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


def render_bgr_to_label_stable(label_widget, bgr_image: np.ndarray,
                                base_w: int = None, base_h: int = None,
                                trim_black: bool = True, allow_upscale: bool = False,
                                neutral_bg: str = "#243447") -> None:
    """
    Render gambar BGR ke tkinter Label dengan ukuran stabil (tidak melampaui base size).
    Cocok untuk preview yang harus tetap proporsional meski window di-resize.
    """
    from ui.theme import LIVE_PREVIEW_W, LIVE_PREVIEW_H
    if base_w is None:
        base_w = LIVE_PREVIEW_W
    if base_h is None:
        base_h = LIVE_PREVIEW_H

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
        label_widget, default_w=base_w, default_h=base_h, min_w=120, min_h=90
    )
    if allow_upscale:
        target_w, target_h = widget_w, widget_h
    else:
        target_w = min(widget_w, max(120, int(base_w)))
        target_h = min(widget_h, max(90,  int(base_h)))

    target_w = max(120, int(target_w))
    target_h = max(90,  int(target_h))

    rgb      = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rendered = resize_cover_rgb(rgb, target_w, target_h)
    photo    = ImageTk.PhotoImage(Image.fromarray(rendered))
    try:
        label_widget.configure(image=photo, text="", anchor="center", bg=neutral_bg)
        label_widget.image = photo
    except Exception:
        pass


def render_gray_to_label_cover(label_widget, gray_image: np.ndarray,
                                default_w: int = _DEFAULT_W, default_h: int = _DEFAULT_H,
                                trim_black: bool = True) -> None:
    """Render gambar grayscale ke tkinter Label (konversi ke BGR dulu)."""
    if gray_image is None:
        return
    if gray_image.ndim != 2:
        gray = cv2.cvtColor(gray_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = gray_image
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    render_bgr_to_label_cover(label_widget, bgr,
                              default_w=default_w, default_h=default_h,
                              trim_black=trim_black)


def bind_preview_card(stage_widget, card_widget, base_w, base_h,
                      margin: int = 8, min_w: int = 120, min_h: int = 90) -> None:
    """
    Pertahankan card preview terpusat di dalam stage-nya.
    Card tidak akan melebihi ukuran base; hanya mengecil jika stage lebih kecil.
    """
    def _relayout(_event=None):
        try:
            stage_widget.update_idletasks()
            stage_w = max(1, int(stage_widget.winfo_width())  - (2 * int(margin)))
            stage_h = max(1, int(stage_widget.winfo_height()) - (2 * int(margin)))
        except Exception:
            stage_w, stage_h = int(base_w), int(base_h)

        try:
            bw    = max(1, int(base_w))
            bh    = max(1, int(base_h))
            scale = min(stage_w / float(bw), stage_h / float(bh), 1.0)
        except Exception:
            scale = 1.0
            bw, bh = int(base_w), int(base_h)

        target_w = max(int(min_w), int(round(bw * scale)))
        target_h = max(int(min_h), int(round(bh * scale)))
        try:
            card_widget.place(relx=0.5, rely=0.5, anchor="center",
                              width=target_w, height=target_h)
        except Exception:
            pass

    try:
        stage_widget.bind("<Configure>", _relayout)
        stage_widget.after(10, _relayout)
    except Exception:
        pass


def create_preview_stage(parent, base_w, base_h,
                         stage_bg: str = "#173A5E", card_bg: str = "#243447",
                         empty_text: str = "Belum ada gambar",
                         fg: str = "#F8FAFC", font: tuple = ("Arial", 10),
                         margin: int = 8):
    """
    Buat frame stage + card + label kosong untuk area preview.
    Return (stage, label) — label adalah target untuk render gambar.
    """
    stage = tk.Frame(
        parent, bg=stage_bg,
        width =max(1, int(base_w) + (2 * int(margin))),
        height=max(1, int(base_h) + (2 * int(margin))),
    )
    try:
        stage.pack_propagate(False)
        stage.grid_propagate(False)
    except Exception:
        pass

    card  = tk.Frame(stage, bg=card_bg, bd=1, relief="solid")
    label = tk.Label(card, bg=card_bg, fg=fg, text=empty_text,
                     anchor="center", font=font)
    label.pack(fill="both", expand=True)
    bind_preview_card(stage, card, base_w=base_w, base_h=base_h, margin=margin)
    return stage, label
