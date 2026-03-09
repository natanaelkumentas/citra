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

        self.colors = {
            "bg_root": "#0B1D36",
            "bg_main": "#0E2744",
            "bg_panel": "#143457",
            "bg_panel_inner": "#0F2A48",
            "fg_primary": "#EAF2FF",
            "fg_muted": "#B8CBE2",
            "accent_blue": "#2D9CDB",
            "accent_green": "#27AE60",
            "accent_red": "#E74C3C"
        }

        self.title("Window Buka Kamera")
        self.geometry("1100x680")
        self.configure(bg=self.colors["bg_root"])
        try:
            self.state("zoomed")
        except:
            pass

        self.setup_ui()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def setup_ui(self):
        root = tk.Frame(self, bg=self.colors["bg_root"])
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # ── Header ──
        header = tk.Frame(root, bg=self.colors["bg_root"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tk.Label(header, text="KAMERA LIVE & CAPTURE", font=("Segoe UI", 16, "bold"),
                 bg=self.colors["bg_root"], fg=self.colors["fg_primary"]).pack(pady=(0,5))
        
        top_bar = tk.Frame(header, bg=self.colors["bg_root"])
        top_bar.pack()
        tk.Label(top_bar, text="IP Camera URL:", font=("Segoe UI", 10, "bold"),
                 bg=self.colors["bg_root"], fg=self.colors["fg_muted"]).pack(side="left", padx=5)
        self.url_entry = tk.Entry(top_bar, font=("Segoe UI", 10), width=40,
                                  bg=self.colors["bg_panel_inner"], fg=self.colors["fg_primary"], insertbackground="white", bd=1)
        self.url_entry.insert(0, self.camera_url if not self.use_internal else "KAMERA INTERNAL (index 0)")
        self.url_entry.pack(side="left", padx=5)
        if self.use_internal:
            self.url_entry.configure(state='disabled')
        tk.Button(top_bar, text="🔄 Hubungkan Ulang", command=self.reconnect_camera,
                  font=("Segoe UI", 9, "bold"), bg="#8E44AD", fg="white", cursor="hand2", relief="raised", bd=1).pack(side="left", padx=5)

        # ── Main Area ──
        main = tk.Frame(root, bg=self.colors["bg_main"])
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_rowconfigure(0, weight=0)
        main.grid_rowconfigure(1, weight=0)
        main.grid_columnconfigure(0, weight=1)

        # ── Container Kamera Kaku (Fixed Height 500) ──
        preview_wrap = tk.Frame(main, bg=self.colors["bg_main"], height=520)
        preview_wrap.grid(row=0, column=0, sticky="ew", pady=(12, 12))
        preview_wrap.grid_propagate(False)
        preview_wrap.grid_rowconfigure(0, weight=1)
        preview_wrap.grid_columnconfigure(0, weight=1, uniform="panel")
        preview_wrap.grid_columnconfigure(1, weight=1, uniform="panel")

        self.live_label = self._make_panel(preview_wrap, 0, "KAMERA LIVE", "Menghubungkan ke Kamera...")
        self.capture_label = self._make_panel(preview_wrap, 1, "HASIL CAPTURE", "Belum ada capture")

        self.live_label.bind("<Configure>", lambda _e: self._refresh_image_panels())
        self.capture_label.bind("<Configure>", lambda _e: self._refresh_image_panels())

        self.info_log_label = tk.Label(main, text="", font=("Segoe UI", 11, "bold"),
                                       bg=self.colors["bg_main"], fg=self.colors["accent_green"], height=2)
        self.info_log_label.grid(row=1, column=0, sticky="ew", pady=5)

        # ── Tombol Bawah (Serasi) ──
        button_row = tk.Frame(main, bg=self.colors["bg_main"])
        button_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for i in range(4):
            button_row.grid_columnconfigure(i, weight=1)

        tk.Button(button_row, text="📸 Capture", command=self.capture_image,
                  font=("Segoe UI", 11, "bold"), bg="#2980b9", fg="white", activebackground="#2471a3", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=0, padx=(0, 5), sticky="ew", ipady=4)

        tk.Button(button_row, text="💾 Simpan", command=self.save_image,
                  font=("Segoe UI", 11, "bold"), bg="#27AE60", fg="white", activebackground="#239B56", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=1, padx=5, sticky="ew", ipady=4)

        tk.Button(button_row, text="🗑️ Hapus", command=self.delete_capture,
                  font=("Segoe UI", 11, "bold"), bg="#E74C3C", fg="white", activebackground="#C0392B", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=2, padx=5, sticky="ew", ipady=4)

        tk.Button(button_row, text="Tutup Halaman", command=self.close,
                  font=("Segoe UI", 11, "bold"), bg=self.colors["bg_panel"], fg="white", activebackground="#26517F", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=3, padx=(5, 0), sticky="ew", ipady=4)

    def _make_panel(self, parent, col, title, empty_text):
        panel = tk.LabelFrame(parent, text=title, bg=self.colors["bg_panel"], fg=self.colors["fg_primary"], font=("Segoe UI", 11, "bold"), bd=1, relief="solid")
        panel.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
        panel.grid_propagate(False)
        label = tk.Label(panel, text=empty_text, bg=self.colors["bg_panel_inner"], fg=self.colors["fg_primary"], font=("Segoe UI", 10))
        label.pack(fill="both", expand=True)
        return label

    def _refresh_image_panels(self):
        if self.captured_frame is not None:
            self._display_capture()
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

                target_w = max(1, self.live_label.winfo_width())
                target_h = max(1, self.live_label.winfo_height())
                if target_w < 10 or target_h < 10:
                    self.after(33, self.update_camera)
                    return
                
                rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                rendered = self._resize_cover(rgb, target_w, target_h)
                photo = ImageTk.PhotoImage(Image.fromarray(rendered))

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

                self._display_capture()
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

    def _display_capture(self):
        if self.captured_frame is None:
            return
        target_w = max(1, self.capture_label.winfo_width())
        target_h = max(1, self.capture_label.winfo_height())
        if target_w < 10 or target_h < 10:
            return
            
        rgb = cv2.cvtColor(self.captured_frame, cv2.COLOR_BGR2RGB)
        rendered = self._resize_cover(rgb, target_w, target_h)
        photo = ImageTk.PhotoImage(Image.fromarray(rendered))
        self.capture_label.configure(image=photo, text="")
        self.capture_label.image = photo

    def _resize_cover(self, rgb_image, target_w, target_h):
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


