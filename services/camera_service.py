# services/camera_service.py — Logika buka/baca/tutup kamera
# Dikumpulkan dari CameraWindow, CameraColorWindow, dan window-window lain.
# Window class tinggal memanggil fungsi ini — bukan berisi logika kamera sendiri.

import cv2
import numpy as np


def open_camera(use_internal: bool, camera_url: str):
    """
    Buka koneksi kamera. Kembalikan objek cv2.VideoCapture.
    Raise Exception jika gagal terhubung.

    Logika diambil dari CameraWindow.start_camera() dan window lainnya.
    """
    if use_internal:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            # Fallback ke DSHOW di Windows untuk kamera internal
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        # Coba deteksi apakah URL sebenarnya adalah index integer
        target = camera_url
        try:
            if isinstance(target, str) and target.isdigit():
                target = int(target)
        except Exception:
            pass
        camera = cv2.VideoCapture(target)

    # Kurangi buffer agar frame lebih fresh (latency rendah)
    try:
        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    if not camera.isOpened():
        raise Exception("Tidak dapat terhubung ke kamera")

    return camera


def read_frame(camera) -> tuple:
    """
    Baca satu frame dari kamera.
    Return (ret, frame) — sama seperti camera.read().
    """
    if camera is None:
        return False, None
    return camera.read()


def normalize_frame_to_bgr(frame: np.ndarray) -> np.ndarray:
    """
    Normalisasi frame ke BGR 3-channel.
    Menangani frame grayscale (2D) dan BGRA (4-channel).
    Diambil dari logika update_camera() di berbagai window.
    """
    if frame is None:
        return frame
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def release_camera(camera) -> None:
    """Tutup kamera dengan aman (tidak raise exception)."""
    if camera is not None:
        try:
            camera.release()
        except Exception:
            pass
