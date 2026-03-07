import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from rembg import remove
import cv2
import os
from datetime import datetime
import webbrowser
import sys
import subprocess
import numpy as np
import json
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import zipfile
from xml.sax.saxutils import escape as xml_escape

class CameraColorWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.camera = None
        self.is_running = False
        self.captured_frame = None

        self.use_internal = use_internal
        self.camera_url = camera_url or "http://172.29.241.86:8081/video"

        self.title("Window Kamera Warna - Deteksi Warna")
        self.geometry("1200x700")
        self.configure(bg="#2C3E50")

        # ── definisi warna HSV ──
        self.color_ranges = {
            'Merah': {
                'lower1': (0, 120, 70), 'upper1': (10, 255, 255),
                'lower2': (170, 120, 70), 'upper2': (180, 255, 255),
                'rgb': (231, 76, 60), 'active': False
            },
            'Orange':  {'lower': (10, 100, 20),  'upper': (25, 255, 255),  'rgb': (230, 120, 0),   'active': False},
            'Kuning':  {'lower': (20, 100, 100), 'upper': (30, 255, 255),  'rgb': (241, 196, 15),  'active': False},
            'Cokelat': {'lower': (8, 100, 20),   'upper': (20, 200, 150),  'rgb': (150, 75, 0),    'active': False},
            'Hijau':   {'lower': (40, 50, 50),   'upper': (80, 255, 255),  'rgb': (46, 204, 113),  'active': False},
            'Cyan':    {'lower': (85, 100, 100), 'upper': (100, 255, 255), 'rgb': (0, 255, 255),   'active': False},
            'Biru':    {'lower': (100, 100, 50), 'upper': (130, 255, 255), 'rgb': (52, 152, 219),  'active': False},
            'Ungu':    {'lower': (130, 50, 50),  'upper': (160, 255, 255), 'rgb': (155, 89, 182),  'active': False},
            'Pink':    {'lower': (145, 30, 80),  'upper': (170, 255, 180), 'rgb': (255, 105, 180), 'active': False},
            'Abu-abu': {'lower': (0, 0, 50),     'upper': (180, 50, 200),  'rgb': (149, 165, 166), 'active': False},
            'Putih':   {'lower': (0, 0, 200),    'upper': (180, 30, 255),  'rgb': (236, 240, 241), 'active': False},
            'Hitam':   {'lower': (0, 0, 0),      'upper': (180, 255, 50),  'rgb': (44, 62, 80),    'active': False},
        }
        self.color_panels = {}

        self.setup_ui()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def setup_ui(self):
        main_frame = tk.Frame(self, bg="#2C3E50")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(main_frame, text="KAMERA WARNA – DETEKSI WARNA REAL-TIME",
                 font=("Arial", 18, "bold"), bg="#2C3E50", fg="white").pack(pady=(0, 5))

        # URL bar
        url_frame = tk.Frame(main_frame, bg="#2C3E50")
        url_frame.pack(pady=5)
        tk.Label(url_frame, text="IP Camera URL:", font=("Arial", 10),
                 bg="#2C3E50", fg="#ECF0F1").pack(side="left", padx=5)
        self.url_entry = tk.Entry(url_frame, font=("Arial", 10), width=40,
                                  bg="#34495E", fg="white", insertbackground="white")
        self.url_entry.insert(0, self.camera_url if not self.use_internal else "KAMERA INTERNAL (index 0)")
        self.url_entry.pack(side="left", padx=5)
        if self.use_internal:
            self.url_entry.configure(state='disabled')
        tk.Button(url_frame, text="🔄 Hubungkan Ulang",
                  command=self.reconnect_camera, font=("Arial", 9, "bold"),
                  bg="#9B59B6", fg="white", cursor="hand2").pack(side="left", padx=5)

        # konten
        content_frame = tk.Frame(main_frame, bg="#2C3E50")
        content_frame.pack(pady=10, fill="both", expand=True)

        # kiri: live
        left_frame = tk.Frame(content_frame, bg="#2C3E50")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left_frame, text="KAMERA LIVE (DETEKSI WARNA)",
                 font=("Arial", 12, "bold"), bg="#2C3E50", fg="#3498DB").pack()
        self.live_label = tk.Label(left_frame, bg="black",
                                   text="Menghubungkan ke Kamera...", fg="white")
        self.live_label.pack(pady=5, fill="both", expand=True)
        tk.Label(left_frame,
                 text="ROI (Region of Interest) ditandai dengan kotak merah di tengah",
                 font=("Arial", 9, "italic"), bg="#2C3E50", fg="#ECF0F1").pack(pady=2)

        # kanan: panel warna
        right_frame = tk.Frame(content_frame, bg="#2C3E50")
        right_frame.pack(side="right", fill="y", padx=(10, 0))
        tk.Label(right_frame, text="DETEKSI WARNA",
                 font=("Arial", 14, "bold"), bg="#2C3E50", fg="white").pack(pady=(0, 10))
        for cn, ci in self.color_ranges.items():
            self.create_color_panel(right_frame, cn, ci['rgb'])

        # log
        self.info_log_label = tk.Label(main_frame, text="", font=("Arial", 11, "bold"),
                                       bg="#2C3E50", fg="#2ECC71", height=2)
        self.info_log_label.pack(pady=5)

        # tombol
        button_frame = tk.Frame(main_frame, bg="#2C3E50")
        button_frame.pack(pady=10)
        for txt, cmd, clr in [("📸 Capture", self.capture_image, "#3498DB"),
                              ("💾 Simpan", self.save_image, "#27AE60"),
                              ("🗑️ Hapus Capture", self.delete_capture, "#E74C3C")]:
            tk.Button(button_frame, text=txt, command=cmd,
                      font=("Arial", 12, "bold"), bg=clr, fg="white",
                      width=15, height=2, cursor="hand2").pack(side="left", padx=10)

        tk.Button(main_frame, text="← Kembali ke Halaman Utama",
                  command=self.close, font=("Arial", 11, "bold"),
                  bg="#95A5A6", fg="white", width=30, height=1,
                  cursor="hand2").pack(pady=10)

    def create_color_panel(self, parent, color_name, rgb_color):
        panel_frame = tk.Frame(parent, bg="#34495E", relief="solid", bd=2)
        panel_frame.pack(pady=5, fill="x")
        name_label = tk.Label(panel_frame, text=color_name,
                              font=("Arial", 11, "bold"), bg="#34495E", fg="white",
                              width=12, anchor="w", padx=10)
        name_label.pack(side="left", pady=5)
        color_canvas = tk.Canvas(panel_frame, width=80, height=40,
                                 bg="#1C2833", highlightthickness=0)
        color_canvas.pack(side="right", padx=10, pady=5)
        rect = color_canvas.create_rectangle(5, 5, 75, 35, fill="#1C2833",
                                             outline="#7F8C8D", width=2)
        self.color_panels[color_name] = {
            'canvas': color_canvas, 'rect': rect,
            'rgb': rgb_color, 'name_label': name_label
        }

    # ── kamera ──
    def start_camera(self):
        try:
            self.show_log("🔄 Menghubungkan ke Kamera...", "#3498DB")
            self.camera = cv2.VideoCapture(0 if self.use_internal else self.camera_url)
            if not self.use_internal:
                try:
                    if self.camera_url.isdigit():
                        self.camera.release()
                        self.camera = cv2.VideoCapture(int(self.camera_url))
                except Exception:
                    pass
            try:
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            if not self.camera.isOpened():
                raise Exception("Tidak dapat terhubung ke Kamera")
            self.is_running = True
            self.show_log("✅ Terhubung ke Kamera!", "#2ECC71")
            self.update_camera()
        except Exception as e:
            self.live_label.configure(
                text="Gagal terhubung.\nPastikan IP Webcam berjalan & jaringan sama.",
                fg="#E74C3C", font=("Arial", 10)
            )
            self.show_log(f"❌ {e}", "#E74C3C")

    def update_camera(self):
        """
        Update live preview untuk CameraColorWindow.
        Normalisasi channel (gray/bgRA -> BGR) agar deteksi HSV tidak error.
        """
        if not self.is_running or self.camera is None:
            return
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                # normalisasi ke BGR 3-channel
                if frame.ndim == 2:
                    display_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.ndim == 3 and frame.shape[2] == 4:
                    display_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    display_frame = frame

                # gambar ROI pada display_frame (sebelum resize)
                h, w = display_frame.shape[:2]
                roi_size = 100
                cx, cy = w // 2, h // 2
                rx1, ry1 = cx - roi_size // 2, cy - roi_size // 2
                rx2, ry2 = cx + roi_size // 2, cy + roi_size // 2
                disp_with_rect = display_frame.copy()
                cv2.rectangle(disp_with_rect, (rx1, ry1), (rx2, ry2), (0, 0, 255), 3)

                # ROI untuk deteksi: pastikan BGR 3-channel
                roi = display_frame[ry1:ry2, rx1:rx2]
                detected = self.detect_color_in_roi(roi)
                self.update_color_panels(detected)

                # resize untuk tampilan
                ratio = min(700 / w, 500 / h)
                nw, nh = int(w * ratio), int(h * ratio)
                rgb = cv2.cvtColor(cv2.resize(disp_with_rect, (nw, nh)), cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.live_label.configure(image=photo, text="")
                self.live_label.image = photo
            self.after(33, self.update_camera)
        except Exception as e:
            print(f"Error updating camera: {e}")
            self.is_running = False

    def detect_color_in_roi(self, roi):
        if roi.size == 0:
            return None
        # roi sudah BGR 3-channel dari normalisasi di update_camera
        try:
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        except Exception:
            # jika masih error, fallback: convert gray->BGR then HSV
            try:
                roi_bgr = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
                hsv_roi = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
            except Exception:
                return None

        color_pct = {}
        for cn, ci in self.color_ranges.items():
            if cn == 'Merah':
                m1 = cv2.inRange(hsv_roi, ci['lower1'], ci['upper1'])
                m2 = cv2.inRange(hsv_roi, ci['lower2'], ci['upper2'])
                mask = cv2.bitwise_or(m1, m2)
            else:
                mask = cv2.inRange(hsv_roi, ci['lower'], ci['upper'])
            color_pct[cn] = (cv2.countNonZero(mask) / mask.size) * 100
        max_c = max(color_pct, key=color_pct.get)
        return max_c if color_pct[max_c] > 15 else None

    def update_color_panels(self, detected_color):
        for cn, pi in self.color_panels.items():
            if cn == detected_color:
                hx = '#{:02x}{:02x}{:02x}'.format(*pi['rgb'])
                pi['canvas'].itemconfig(pi['rect'], fill=hx, outline="white", width=4)
                pi['name_label'].configure(fg="#2ECC71")
            else:
                pi['canvas'].itemconfig(pi['rect'], fill="#1C2833", outline="#7F8C8D", width=2)
                pi['name_label'].configure(fg="white")

    def capture_image(self):
        if self.camera is None or not self.camera.isOpened():
            self.show_log("⚠️ Kamera tidak aktif!", "#E67E22")
            return
        try:
            ret, frame = self.camera.read()
            if ret:
                # normalisasi ke BGR saat menyimpan
                if frame.ndim == 2:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.ndim == 3 and frame.shape[2] == 4:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    bgr_frame = frame.copy()

                self.captured_frame = bgr_frame
                self.show_log("✅ Gambar di-capture (belum disimpan)", "#2ECC71")
            else:
                self.show_log("❌ Gagal mengambil gambar", "#E74C3C")
        except Exception as e:
            self.show_log(f"❌ Error: {e}", "#E74C3C")

    def save_image(self):
        if self.captured_frame is None:
            self.show_log("⚠️ Belum ada gambar yang di-capture!", "#E67E22")
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"capture_color_{ts}.jpg"
            cv2.imwrite(os.path.join(self.drive_folder, fname), self.captured_frame)
            self.show_log(f"✅ Gambar warna disimpan: {fname}", "#2ECC71")
        except Exception as e:
            self.show_log(f"❌ Gagal menyimpan: {e}", "#E74C3C")

    def delete_capture(self):
        if self.captured_frame is None:
            self.show_log("ℹ️ Tidak ada capture untuk dihapus", "#3498DB")
            return
        self.captured_frame = None
        self.show_log("✅ Capture berhasil dihapus!", "#2ECC71")

    def show_log(self, message, color="#2ECC71"):
        self.info_log_label.configure(text=message, fg=color)
        self.after(5000, lambda: self.info_log_label.configure(text=""))

    def reconnect_camera(self):
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        val = self.url_entry.get()
        if val.startswith("KAMERA INTERNAL"):
            self.use_internal = True
        else:
            self.use_internal = False
            self.camera_url = val.strip()
        self.live_label.configure(text="Menghubungkan ulang...", fg="white", font=("Arial", 11))
        self.after(500, self.start_camera)

    def close(self):
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
        self.destroy()


