# services/filter_service.py — Semua algoritma filter citra
# Fungsi murni: input numpy array (BGR), output numpy array.
# Diambil dari AnalisisFilterWindow.apply_filter() dan method-method di dalamnya.
# Tidak ada import tkinter di file ini.

import cv2
import numpy as np


# ── Filter Roberts ──────────────────────────────────────────────────────────
def apply_roberts(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan operator Roberts Cross."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    kx = np.array([[1, 0], [0, -1]], dtype=np.float32)
    ky = np.array([[0, 1], [-1, 0]], dtype=np.float32)
    gx = cv2.filter2D(gray, cv2.CV_32F, kx)
    gy = cv2.filter2D(gray, cv2.CV_32F, ky)
    return cv2.convertScaleAbs(np.sqrt(gx * gx + gy * gy))


# ── Filter Prewitt ──────────────────────────────────────────────────────────
def apply_prewitt(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan operator Prewitt."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    kx = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[1, 1, 1], [0, 0, 0], [-1, -1, -1]], dtype=np.float32)
    gx = cv2.filter2D(gray, cv2.CV_32F, kx)
    gy = cv2.filter2D(gray, cv2.CV_32F, ky)
    return cv2.convertScaleAbs(np.sqrt(gx * gx + gy * gy))


# ── Filter Sobel ─────────────────────────────────────────────────────────────
def apply_sobel(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan operator Sobel."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.convertScaleAbs(np.sqrt(gx * gx + gy * gy))


# ── Filter Frei-Chen ─────────────────────────────────────────────────────────
def apply_frei_chen(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan operator Frei-Chen."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    s2 = np.sqrt(2.0)
    kx = np.array([[-1, 0, 1], [-s2, 0, s2], [-1, 0, 1]], dtype=np.float32)
    ky = np.array([[1, s2, 1], [0, 0, 0], [-1, -s2, -1]], dtype=np.float32)
    gx = cv2.filter2D(gray, cv2.CV_32F, kx)
    gy = cv2.filter2D(gray, cv2.CV_32F, ky)
    return cv2.convertScaleAbs(np.sqrt(gx * gx + gy * gy))


# ── Filter Canny ─────────────────────────────────────────────────────────────
def apply_canny(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan Canny. Threshold digunakan sebagai batas bawah."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    low  = max(0, min(254, threshold))
    high = max(low + 1, min(255, threshold * 2))
    return cv2.Canny(gray, low, high)


# ── Filter Otsu ──────────────────────────────────────────────────────────────
def apply_otsu(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Binarisasi otomatis dengan metode Otsu."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, result = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return result


# ── Filter Kirsch ─────────────────────────────────────────────────────────────
def apply_kirsch(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Deteksi tepi dengan operator Kirsch (8 arah)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    kernels = [
        np.array([[5, 5, 5], [-3, 0, -3], [-3, -3, -3]], dtype=np.float32),
        np.array([[5, 5, -3], [5, 0, -3], [-3, -3, -3]], dtype=np.float32),
        np.array([[5, -3, -3], [5, 0, -3], [5, -3, -3]], dtype=np.float32),
        np.array([[-3, -3, -3], [5, 0, -3], [5, 5, -3]], dtype=np.float32),
        np.array([[-3, -3, -3], [-3, 0, -3], [5, 5, 5]], dtype=np.float32),
        np.array([[-3, -3, -3], [-3, 0, 5], [-3, 5, 5]], dtype=np.float32),
        np.array([[-3, -3, 5], [-3, 0, 5], [-3, -3, 5]], dtype=np.float32),
        np.array([[-3, 5, 5], [-3, 0, 5], [-3, -3, -3]], dtype=np.float32),
    ]
    responses = [cv2.filter2D(gray, cv2.CV_32F, k) for k in kernels]
    return cv2.convertScaleAbs(np.max(np.abs(np.stack(responses, axis=0)), axis=0))


# ── Filter Segmentasi Warna ───────────────────────────────────────────────────
def apply_segmentasi_warna(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Segmentasi warna dengan K-Means clustering."""
    k = max(2, min(8, 2 + (threshold // 32)))
    h, w = image_bgr.shape[:2]
    scale = 400.0 / max(w, h, 1)

    if scale < 1.0:
        small = cv2.resize(image_bgr, (int(w * scale), int(h * scale)))
    else:
        small = image_bgr

    pixels = small.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    centers = np.uint8(centers)
    res_small = centers[labels.flatten()].reshape(small.shape)

    if scale < 1.0:
        return cv2.resize(res_small, (w, h), interpolation=cv2.INTER_NEAREST)
    return res_small


# ── Filter Dwi Aras ───────────────────────────────────────────────────────────
def apply_dwi_aras(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Binarisasi manual dengan threshold yang bisa diatur."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    _, result = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return result


# ── Filter Aras Jamak ─────────────────────────────────────────────────────────
def apply_aras_jamak(image_bgr: np.ndarray, threshold: int = 127) -> np.ndarray:
    """Multilevel thresholding: 3 aras (hitam, abu, putih)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    t1 = max(1, min(254, threshold))
    t2 = min(255, t1 + 64)
    result = np.zeros_like(gray)
    result[(gray >= t1) & (gray < t2)] = 127
    result[gray >= t2] = 255
    return result


# ── Peta filter (nama → fungsi) ───────────────────────────────────────────────
# Dipakai oleh AnalisisFilterWindow.apply_filter()
FILTER_MAP = {
    "Roberts":          apply_roberts,
    "Prewitt":          apply_prewitt,
    "Sobel":            apply_sobel,
    "Frei-Chen":        apply_frei_chen,
    "Canny":            apply_canny,
    "Otsu":             apply_otsu,
    "Kirsch":           apply_kirsch,
    "Segmentasi Warna": apply_segmentasi_warna,
    "Dwi Aras":         apply_dwi_aras,
    "Aras Jamak":       apply_aras_jamak,
}
