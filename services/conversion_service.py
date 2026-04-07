# services/conversion_service.py — Konversi citra: RGB→Grayscale dan Grayscale→Biner


import cv2
import numpy as np


def rgb_to_gray(bgr_frame: np.ndarray) -> np.ndarray:
    """
    Konversi frame BGR ke Grayscale.
    Return array 2D (single-channel).
    """
    return cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)


def gray_to_biner(bgr_or_gray_frame: np.ndarray, threshold: int = 127) -> np.ndarray:
    """
    Konversi frame ke Biner dengan threshold manual.
    Menerima frame BGR maupun grayscale.
    Return array 2D biner (0 atau 255).
    """
    if bgr_or_gray_frame.ndim == 3:
        gray = cv2.cvtColor(bgr_or_gray_frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = bgr_or_gray_frame

    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    return binary
