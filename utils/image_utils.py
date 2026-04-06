# utils/image_utils.py — Utility fungsi gambar yang bisa dipakai oleh layer mana saja
# Salin persis dari utils_image.py lama. Isi tidak berubah.

import numpy as np


# ─────────────────────────────────────────────
# Utility: deteksi jenis gambar
# Dipakai di FileWindow dan ConversionWindow
# ─────────────────────────────────────────────
def detect_image_type(pil_image):
    """
    Deteksi jenis gambar: 'Color', 'Grayscale', atau 'Black & White'
    - Color      : channel R, G, B berbeda secara signifikan
    - Grayscale  : R, G, B hampir sama
    - Black & White: grayscale dengan sedikit variasi (biner/terbatas)
    """
    try:
        arr = np.array(pil_image)

        # ── single channel (mode "L") ──
        if arr.ndim == 2:
            gray = arr
            is_gray = True

        elif arr.ndim == 3:
            # buang alpha kalau ada
            rgb = arr[..., :3] if arr.shape[2] == 4 else arr

            r = rgb[..., 0].astype(np.int16)
            g = rgb[..., 1].astype(np.int16)
            b = rgb[..., 2].astype(np.int16)

            diff_rg = np.abs(r - g)
            diff_rb = np.abs(r - b)
            diff_gb = np.abs(g - b)

            tol = 10
            gray_mask = (diff_rg <= tol) & (diff_rb <= tol) & (diff_gb <= tol)
            gray_ratio = np.count_nonzero(gray_mask) / gray_mask.size
            is_gray = gray_ratio > 0.98

            gray = r if is_gray else None
        else:
            return "Color"

        if is_gray:
            unique_vals = np.unique(gray)
            return "Black & White" if unique_vals.size <= 8 else "Grayscale"

        return "Color"

    except Exception as e:
        print(f"detect_image_type error: {e}")
        return "Color"


# ─────────────────────────────────────────────
# Utility: format ukuran file ke string human-readable
# ─────────────────────────────────────────────
def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


# ─────────────────────────────────────────────
# Utility: estimasi ukuran gambar dalam bytes
#          dari shape numpy array (width × height × channels)
# ─────────────────────────────────────────────
def estimate_image_bytes(arr):
    """Estimasi ukuran gambar mentah dari shape numpy array."""
    try:
        return int(np.prod(arr.shape))
    except Exception:
        return 0
