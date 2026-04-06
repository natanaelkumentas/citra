# services/color_analysis_service.py — Analisis warna ROI
# Diambil dari AnalisisWarnaWindow.analyze_roi() dan CameraColorWindow.
# Tidak ada import tkinter di file ini.

import cv2
import numpy as np
from collections import Counter


def analyze_roi(bgr_frame: np.ndarray, cx: int, cy: int, roi_size: int) -> dict:
    """
    Potong ROI dari frame dan hitung statistik warna.

    Return dict:
    {
        "mean_rgb"      : (R, G, B) float,
        "unique_colors" : int,
        "dominant_rgb"  : (R, G, B) int,
        "dominant_hex"  : str,
        "roi_shape"     : (w, h),
        "description"   : str,
    }

    Logika diambil dari AnalisisWarnaWindow.analyze_roi().
    """
    h, w = bgr_frame.shape[:2]
    x1 = max(0, cx - roi_size // 2)
    y1 = max(0, cy - roi_size // 2)
    x2 = min(w, cx + roi_size // 2)
    y2 = min(h, cy + roi_size // 2)

    roi = bgr_frame[y1:y2, x1:x2]
    if roi.size == 0:
        return {}

    # Mean BGR → mean RGB
    mean_bgr = cv2.mean(roi)[:3]
    mean_rgb  = (round(mean_bgr[2], 2), round(mean_bgr[1], 2), round(mean_bgr[0], 2))

    # Jumlah warna unik
    pixels = roi.reshape(-1, 3)
    unique_colors_cnt = len(np.unique(pixels, axis=0))

    # Warna dominan via kuantisasi 4-bit
    quantized = (pixels // 16) * 16
    pixel_strings = [f"{p[0]}-{p[1]}-{p[2]}" for p in quantized]
    counts = Counter(pixel_strings)
    dom_str = counts.most_common(1)[0][0]
    db, dg, dr = [int(v) for v in dom_str.split("-")]
    dominant_rgb  = (dr, dg, db)
    dominant_hex  = "#{:02x}{:02x}{:02x}".format(*dominant_rgb)
    roi_w = x2 - x1
    roi_h = y2 - y1

    description = (
        f"STATISTIK ROI ({roi_w}x{roi_h} px):\n"
        f"- Rerata Intensitas: R={mean_rgb[0]}, G={mean_rgb[1]}, B={mean_rgb[2]}\n"
        f"- Variasi Warna: Terdeteksi {unique_colors_cnt} kombinasi warna unik.\n"
        f"- Dominansi: Warna hex {dominant_hex} paling sering muncul di area pusat."
    )

    return {
        "mean_rgb":       mean_rgb,
        "unique_colors":  unique_colors_cnt,
        "dominant_rgb":   dominant_rgb,
        "dominant_hex":   dominant_hex,
        "roi_shape":      (roi_w, roi_h),
        "description":    description,
    }


COLOR_RANGES = {
    "Merah":  {"lower1":(0,120,70),"upper1":(10,255,255),
               "lower2":(170,120,70),"upper2":(180,255,255),
               "rgb":(231,76,60)},
    "Orange": {"lower":(10,100,20),"upper":(25,255,255),  "rgb":(230,120,0)},
    "Kuning": {"lower":(20,100,100),"upper":(30,255,255), "rgb":(241,196,15)},
    "Cokelat":{"lower":(8,100,20),"upper":(20,200,150),   "rgb":(150,75,0)},
    "Hijau":  {"lower":(40,50,50),"upper":(80,255,255),   "rgb":(46,204,113)},
    "Cyan":   {"lower":(85,100,100),"upper":(100,255,255),"rgb":(0,255,255)},
    "Biru":   {"lower":(100,100,50),"upper":(130,255,255),"rgb":(52,152,219)},
    "Ungu":   {"lower":(130,50,50),"upper":(160,255,255), "rgb":(155,89,182)},
    "Pink":   {"lower":(145,30,80),"upper":(170,255,180), "rgb":(255,105,180)},
    "Abu-abu":{"lower":(0,0,50),"upper":(180,50,200),     "rgb":(149,165,166)},
    "Putih":  {"lower":(0,0,200),"upper":(180,30,255),    "rgb":(236,240,241)},
    "Hitam":  {"lower":(0,0,0),"upper":(180,255,50),      "rgb":(44,62,80)},
}


def detect_colors_hsv(roi_bgr: np.ndarray, threshold_pct: float = 5.0) -> list:
    """
    Deteksi keberadaan warna spesifik pada ROI menggunakan rentang HSV.
    Return list of string (nama warna yang terdeteksi dengan pct > threshold_pct).
    """
    if roi_bgr is None or roi_bgr.size == 0:
        return []
    try:
        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    except Exception:
        return []

    total_pixels = max(1, roi_bgr.shape[0] * roi_bgr.shape[1])
    detected = []

    for name, info in COLOR_RANGES.items():
        if name == "Merah":
            mask = cv2.bitwise_or(
                cv2.inRange(hsv, info["lower1"], info["upper1"]),
                cv2.inRange(hsv, info["lower2"], info["upper2"])
            )
        else:
            mask = cv2.inRange(hsv, info["lower"], info["upper"])
            
        pct = cv2.countNonZero(mask) / total_pixels * 100
        if pct > threshold_pct:
            detected.append(name)

    return detected
