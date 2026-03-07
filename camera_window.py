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

class CameraWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.camera = None
        self.is_running = False
        self.captured_frame = None

        self.use_internal = use_internal
        self.camera_url = camera_url or "http://172.29.241.86:8081/video"

        self.title("Window Buka Kamera")
        self.geometry("1000x650")
        self.configure(bg="#34495E")

        self.setup_ui()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def setup_ui(self):
        main_frame = tk.Frame(self, bg="#34495E")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(main_frame, text="KAMERA LIVE & CAPTURE",
                 font=("Arial", 18, "bold"), bg="#34495E", fg="white").pack(pady=(0, 5))

        # URL bar
        url_frame = tk.Frame(main_frame, bg="#34495E")
        url_frame.pack(pady=5)
        tk.Label(url_frame, text="IP Camera URL:", font=("Arial", 10),
                 bg="#34495E", fg="#ECF0F1").pack(side="left", padx=5)
        self.url_entry = tk.Entry(url_frame, font=("Arial", 10), width=40,
                                  bg="#2C3E50", fg="white", insertbackground="white")
        self.url_entry.insert(0, self.camera_url if not self.use_internal else "KAMERA INTERNAL (index 0)")
        self.url_entry.pack(side="left", padx=5)
        if self.use_internal:
            self.url_entry.configure(state='disabled')
        tk.Button(url_frame, text="🔄 Hubungkan Ulang",
                  command=self.reconnect_camera, font=("Arial", 9, "bold"),
                  bg="#9B59B6", fg="white", cursor="hand2").pack(side="left", padx=5)

        # ── kiri: live  |  kanan: capture ──
        camera_frame = tk.Frame(main_frame, bg="#34495E")
        camera_frame.pack(pady=10, fill="both", expand=True)

        left_frame = tk.Frame(camera_frame, bg="#34495E")
        left_frame.pack(side="left", padx=10, fill="both", expand=True)
        tk.Label(left_frame, text="KAMERA LIVE", font=("Arial", 12, "bold"),
                 bg="#34495E", fg="#3498DB").pack()
        self.live_label = tk.Label(left_frame, bg="black",
                                   text="Menghubungkan ke Kamera...", fg="white")
        self.live_label.pack(pady=5, fill="both", expand=True)

        right_frame = tk.Frame(camera_frame, bg="#34495E")
        right_frame.pack(side="right", padx=10, fill="both", expand=True)
        tk.Label(right_frame, text="HASIL CAPTURE", font=("Arial", 12, "bold"),
                 bg="#34495E", fg="#E67E22").pack()
        self.capture_label = tk.Label(right_frame, bg="black",
                                      text="Belum ada capture", fg="white")
        self.capture_label.pack(pady=5, fill="both", expand=True)

        # log
        self.info_log_label = tk.Label(main_frame, text="", font=("Arial", 11, "bold"),
                                       bg="#34495E", fg="#2ECC71", height=2)
        self.info_log_label.pack(pady=5)

        # tombol
        button_frame = tk.Frame(main_frame, bg="#34495E")
        button_frame.pack(pady=10)
        for txt, cmd, clr in [("📸 Capture", self.capture_image, "#3498DB"),
                              ("💾 Simpan", self.save_image, "#27AE60"),
                              ("🗑️ Hapus", self.delete_capture, "#E74C3C")]:
            tk.Button(button_frame, text=txt, command=cmd,
                      font=("Arial", 12, "bold"), bg=clr, fg="white",
                      width=15, height=2, cursor="hand2").pack(side="left", padx=10)

        tk.Button(main_frame, text="← Kembali ke Halaman Utama",
                  command=self.close, font=("Arial", 11, "bold"),
                  bg="#95A5A6", fg="white", width=30, height=1,
                  cursor="hand2").pack(pady=10)

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
        Update live preview — tangani frame 1/3/4 channel dengan aman.
        """
        if not self.is_running or self.camera is None:
            return
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                # Normalisasi frame ke BGR 3-channel jika perlu
                if frame.ndim == 2:
                    display_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.ndim == 3 and frame.shape[2] == 4:
                    display_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    display_frame = frame

                h, w = display_frame.shape[:2]
                ratio = min(450 / w, 400 / h)
                nw, nh = int(w * ratio), int(h * ratio)
                rgb = cv2.cvtColor(cv2.resize(display_frame, (nw, nh)), cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.live_label.configure(image=photo, text="")
                self.live_label.image = photo
            self.after(33, self.update_camera)
        except Exception as e:
            print(f"Error updating camera: {e}")
            self.is_running = False

    def capture_image(self):
        if self.camera is None or not self.camera.isOpened():
            self.show_log("⚠️ Kamera tidak aktif!", "#E67E22")
            return
        try:
            ret, frame = self.camera.read()
            if ret:
                # simpan original BGR (jika grayscale, ubah ke BGR agar konsisten disimpan)
                if frame.ndim == 2:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.ndim == 3 and frame.shape[2] == 4:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    bgr_frame = frame.copy()

                self.captured_frame = bgr_frame
                h, w = bgr_frame.shape[:2]
                ratio = min(450 / w, 400 / h)
                rgb = cv2.cvtColor(cv2.resize(bgr_frame, (int(w * ratio), int(h * ratio))), cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(Image.fromarray(rgb))
                self.capture_label.configure(image=photo, text="")
                self.capture_label.image = photo
                self.show_log("✅ Gambar berhasil di-capture!", "#2ECC71")
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
            fname = f"capture_{ts}.jpg"
            cv2.imwrite(os.path.join(self.drive_folder, fname), self.captured_frame)
            self.show_log(f"✅ Gambar berhasil disimpan: {fname}", "#2ECC71")
        except Exception as e:
            self.show_log(f"❌ Gagal menyimpan: {e}", "#E74C3C")

    def delete_capture(self):
        if self.captured_frame is None:
            self.show_log("ℹ️ Tidak ada capture untuk dihapus", "#3498DB")
            return
        self.captured_frame = None
        self.capture_label.configure(image="", text="Belum ada capture",
                                     font=("Arial", 11), fg="white")
        self.capture_label.image = None
        self.show_log("✅ Capture berhasil dihapus!", "#2ECC71")

    def show_log(self, message, color="#2ECC71"):
        self.info_log_label.configure(text=message, fg=color)
        self.after(5000, lambda: self.info_log_label.configure(text=""))

    def reconnect_camera(self):
        self.is_running = False
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
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
            try:
                self.camera.release()
            except Exception:
                pass
        self.destroy()


