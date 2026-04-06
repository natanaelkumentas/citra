# services/image_service.py — Operasi file gambar: baca, simpan, list
# Ekstrak dari AnalisisFilterWindow dan window-window lain.

import os
import cv2
import numpy as np
from datetime import datetime


def imread_unicode(path: str) -> np.ndarray | None:
    """
    Baca gambar dari path yang mengandung karakter Unicode.
    Diambil dari AnalisisFilterWindow._imread_unicode().
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def imwrite_unicode(path: str, image_data: np.ndarray) -> bool:
    """
    Simpan gambar ke path yang mengandung karakter Unicode.
    Diambil dari AnalisisFilterWindow._imwrite_unicode().
    """
    try:
        ext = os.path.splitext(path)[1].lower()
        ok, buf = cv2.imencode(ext, image_data)
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


def save_capture(drive_folder: str, frame_bgr: np.ndarray, prefix: str = "capture") -> str:
    """
    Simpan frame ke drive_folder dengan timestamp sebagai nama file.
    Return nama file yang disimpan (bukan full path).
    """
    os.makedirs(drive_folder, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{prefix}_{ts}.jpg"
    cv2.imwrite(os.path.join(drive_folder, fname), frame_bgr)
    return fname


def list_image_files(folder: str) -> list[str]:
    """
    Kembalikan daftar full-path gambar di folder,
    diurutkan dari file terbaru (mtime descending).
    Diambil dari FileWindow.load_images().
    """
    if not os.path.exists(folder):
        return []

    extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(extensions)
    ]
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files
