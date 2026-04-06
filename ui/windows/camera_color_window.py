# ui/windows/camera_color_window.py — KAMERA WARNA + DETEKSI WARNA REAL-TIME
# FIX: kamera fill penuh, panel warna fixed 260px di kanan, tidak auto-zoom.

import tkinter as tk
from PIL import Image, ImageTk
import cv2
import os
from datetime import datetime
import numpy as np

# Import helper dari camera_window agar konsisten
from ui.windows.camera_window import _to_bgr, _resize_cover, _render
from services import camera_service, color_analysis_service


class CameraColorWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder   = drive_folder
        self.camera         = None
        self.is_running     = False
        self.captured_frame = None
        self.is_frozen      = False
        self.use_internal   = use_internal
        self.camera_url     = camera_url or "http://172.29.241.86:8081/video"

        self.C = {
            "bg":      "#0B1D36",
            "main":    "#0E2744",
            "panel":   "#143457",
            "inner":   "#0F2A48",
            "fg":      "#EAF2FF",
            "muted":   "#B8CBE2",
            "blue":    "#2D9CDB",
            "green":   "#27AE60",
            "red":     "#E74C3C",
        }

        self.color_ranges = color_analysis_service.COLOR_RANGES
        self.color_panels = {}

        self.title("Window Kamera Warna - Deteksi Warna")

        # ── Ukuran awal window ─────────────────────────────────────────────
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = min(1200, int(sw * 0.85)), min(720, int(sh * 0.85))
        x, y   = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(860, 560)
        self.configure(bg=self.C["bg"])

        self._build_ui()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ─────────────────── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        C = self.C
        wrap = tk.Frame(self, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
        wrap.rowconfigure(1, weight=1)
        wrap.columnconfigure(0, weight=1)

        # ── Header ──
        hdr = tk.Frame(wrap, bg=C["bg"])
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(hdr, text="KAMERA WARNA – DETEKSI WARNA REAL-TIME",
                 font=("Segoe UI", 14, "bold"), bg=C["bg"], fg=C["fg"]).pack()

        bar = tk.Frame(hdr, bg=C["bg"])
        bar.pack(pady=(4, 0))
        tk.Label(bar, text="IP Camera URL:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=4)
        self.url_entry = tk.Entry(bar, width=38, font=("Segoe UI", 10),
                                  bg=C["inner"], fg=C["fg"],
                                  insertbackground="white", bd=1, relief="solid")
        self.url_entry.insert(0, "KAMERA INTERNAL (index 0)"
                              if self.use_internal else self.camera_url)
        if self.use_internal:
            self.url_entry.configure(state="disabled")
        self.url_entry.pack(side="left", padx=4)
        tk.Button(bar, text="🔄 Hubungkan Ulang",
                  command=self.reconnect_camera,
                  font=("Segoe UI", 9, "bold"),
                  bg="#8E44AD", fg="white", cursor="hand2", bd=1).pack(side="left", padx=4)

        # ── Main ──
        main = tk.Frame(wrap, bg=C["main"])
        main.grid(row=1, column=0, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)
        main.rowconfigure(2, weight=0)
        main.columnconfigure(0, weight=1)

        # ── Middle: kamera (fill) + panel warna (fixed 260px) ──
        mid = tk.Frame(main, bg=C["main"])
        mid.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)   # kamera: isi sisa ruang
        mid.columnconfigure(1, weight=0)   # warna: tidak stretch

        # ── Panel Kiri: Kamera ──
        left = tk.Frame(mid, bg=C["panel"], bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self.cam_hdr = tk.Label(left, text="KAMERA LIVE (DETEKSI WARNA)",
                                font=("Segoe UI", 10, "bold"),
                                bg=C["inner"], fg=C["blue"], pady=6)
        self.cam_hdr.grid(row=0, column=0, sticky="ew")

        # Label kamera — fill penuh agar _render bisa baca ukuran aktual
        self.live_label = tk.Label(left, bg=C["inner"], fg=C["muted"],
                                   text="Memuat kamera...", font=("Segoe UI", 10))
        self.live_label.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        tk.Label(left, text="ROI (kotak merah di tengah) = area deteksi warna",
                 font=("Segoe UI", 8, "italic"),
                 bg=C["panel"], fg=C["muted"],
                 ).grid(row=2, column=0, pady=(2, 4))

        # ── Panel Kanan: Deteksi Warna (fixed 260px) ──
        right = tk.Frame(mid, bg=C["panel"], bd=1, relief="solid",
                         width=260)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="DETEKSI WARNA",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["inner"], fg=C["fg"],
                 pady=6).grid(row=0, column=0, sticky="ew")

        # Scroll canvas untuk daftar warna (kalau layar kecil)
        color_wrap = tk.Frame(right, bg=C["panel"])
        color_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=6)
        color_wrap.columnconfigure(0, weight=1)

        for name, info in self.color_ranges.items():
            self._make_color_row(color_wrap, name, info["rgb"])

        # ── Log ──
        self.log_lbl = tk.Label(main, text="", font=("Segoe UI", 9, "bold"),
                                bg=C["main"], fg=C["green"])
        self.log_lbl.grid(row=1, column=0, sticky="ew", pady=2)

        # ── Tombol ──
        btn_row = tk.Frame(main, bg=C["main"])
        btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 8))
        for i in range(4):
            btn_row.columnconfigure(i, weight=1)

        for col, (txt, cmd, bg) in enumerate([
            ("📸 Capture",    self.capture_image,  "#2980B9"),
            ("💾 Simpan",     self.save_image,      "#27AE60"),
            ("🗑️ Hapus",      self.delete_capture,  "#E74C3C"),
            ("Tutup Halaman", self.close,            self.C["panel"]),
        ]):
            tk.Button(btn_row, text=txt, command=cmd,
                      font=("Segoe UI", 10, "bold"), bg=bg, fg="white",
                      relief="raised", bd=1, cursor="hand2"
                      ).grid(row=0, column=col,
                             padx=(0 if col == 0 else 5, 0),
                             sticky="ew", ipady=6)

    def _make_color_row(self, parent, name, rgb):
        C = self.C
        row = tk.Frame(parent, bg=C["inner"])
        row.pack(fill="x", pady=1, ipady=3)
        tk.Label(row, text=name, font=("Segoe UI", 9, "bold"),
                 bg=C["inner"], fg=C["fg"], anchor="w",
                 width=9).pack(side="left", padx=8)
        canvas = tk.Canvas(row, width=50, height=18,
                           bg=C["inner"], highlightthickness=0)
        canvas.pack(side="right", padx=8)
        rect = canvas.create_rectangle(1, 1, 49, 17,
                                       fill=C["inner"],
                                       outline="#4A6A8A", width=1)
        self.color_panels[name] = {"canvas": canvas, "rect": rect,
                                   "rgb": rgb, "lbl": row}

    # ─────────────────── Kamera ───────────────────────────────────────────────
    def start_camera(self):
        try:
            self.show_log("🔄 Menghubungkan...", "#3498DB")
            self.camera     = camera_service.open_camera(self.use_internal, self.camera_url)
            self.is_running = True
            self.show_log("✅ Terhubung!", "#2ECC71")
            self.update_idletasks()
            self._loop()
        except Exception as e:
            self.live_label.configure(text=f"Gagal: {e}", fg="#E74C3C")
            self.show_log(f"❌ {e}", "#E74C3C")

    def _loop(self):
        if not self.is_running or self.camera is None:
            return
        if self.is_frozen:
            self.after(100, self._loop)
            return
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                bgr = _to_bgr(frame)

                # Gambar kotak ROI di tengah frame
                h, w = bgr.shape[:2]
                r = 100
                cx, cy = w // 2, h // 2
                disp = bgr.copy()
                cv2.rectangle(disp,
                              (cx - r//2, cy - r//2),
                              (cx + r//2, cy + r//2),
                              (0, 0, 255), 3)

                # Deteksi warna di ROI
                roi = bgr[cy-r//2:cy+r//2, cx-r//2:cx+r//2]
                self._detect(roi)

                # Render ke label — fill penuh
                _render(self.live_label, disp)
            self.after(33, self._loop)
        except Exception as e:
            print(f"loop: {e}")
            self.is_running = False

    def _detect(self, roi_bgr: np.ndarray):
        detected_colors = color_analysis_service.detect_colors_hsv(roi_bgr, threshold_pct=5.0)
        
        for name, p in self.color_panels.items():
            if name in detected_colors:
                r2, g2, b2 = p["rgb"]
                hx = "#{:02x}{:02x}{:02x}".format(r2, g2, b2)
                p["canvas"].itemconfig(p["rect"], fill=hx, outline="white", width=2)
            else:
                p["canvas"].itemconfig(p["rect"],
                                       fill=self.C["inner"],
                                       outline="#4A6A8A", width=1)

    # ─────────────────── Actions ──────────────────────────────────────────────
    def capture_image(self):
        if not (self.camera and self.camera.isOpened()):
            self.show_log("⚠️ Kamera tidak aktif!", "#E67E22"); return
        ret, frame = self.camera.read()
        if ret and frame is not None:
            self.captured_frame = _to_bgr(frame)
            self.is_frozen = True
            disp = self.captured_frame.copy()
            h, w = disp.shape[:2]
            r = 100; cx, cy = w//2, h//2
            cv2.rectangle(disp,(cx-r//2,cy-r//2),(cx+r//2,cy+r//2),(0,0,255),3)
            cv2.putText(disp,"CAPTURED",(20,40),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2)
            _render(self.live_label, disp)
            self.cam_hdr.configure(text="📷 CAPTURED (Diam)", fg="#F39C12")
            self.show_log("✅ Captured! Klik Hapus untuk kembali ke live.", "#2ECC71")
        else:
            self.show_log("❌ Gagal mengambil frame", "#E74C3C")

    def save_image(self):
        if self.captured_frame is None:
            self.show_log("⚠️ Belum ada capture!", "#E67E22"); return
        os.makedirs(self.drive_folder, exist_ok=True)
        fname = f"capture_color_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(os.path.join(self.drive_folder, fname), self.captured_frame)
        self.show_log(f"✅ Disimpan: {fname}", "#2ECC71")

    def delete_capture(self):
        if not self.is_frozen and self.captured_frame is None:
            self.show_log("ℹ️ Tidak ada capture", "#3498DB"); return
        self.captured_frame = None
        self.is_frozen = False
        self.cam_hdr.configure(text="KAMERA LIVE (DETEKSI WARNA)", fg=self.C["blue"])
        self.show_log("✅ Capture dihapus. Kembali ke live.", "#2ECC71")

    def reconnect_camera(self):
        self.is_running = False
        self.is_frozen = False
        self.captured_frame = None
        if self.camera:
            try: self.camera.release()
            except Exception: pass
            self.camera = None
        val = self.url_entry.get()
        self.use_internal = val.startswith("KAMERA INTERNAL")
        if not self.use_internal:
            self.camera_url = val.strip()
        self.cam_hdr.configure(text="KAMERA LIVE (DETEKSI WARNA)", fg=self.C["blue"])
        self.live_label.configure(image="", text="Menghubungkan ulang...")
        self.live_label.image = None
        self.after(500, self.start_camera)

    def show_log(self, msg, color="#2ECC71"):
        self.log_lbl.configure(text=msg, fg=color)
        self.after(5000, lambda: self.log_lbl.configure(text=""))

    def close(self):
        self.is_running = False
        if self.camera:
            try: self.camera.release()
            except Exception: pass
        self.destroy()
