# ui/windows/camera_window.py — KAMERA LIVE & CAPTURE
# FIX: kamera fill penuh container menggunakan winfo_width/height yang dibaca aktual,
#      window tidak auto-zoom, layout clean dengan 2 panel sejajar.

import tkinter as tk
from PIL import Image, ImageTk
import cv2
import os
from datetime import datetime
import numpy as np

from services import camera_service


class CameraWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder   = drive_folder
        self.camera         = None
        self.is_running     = False
        self.captured_frame = None
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

        self.title("Window Buka Kamera")

        # ── Ukuran awal: 80% layar, tidak zoom ──
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = min(1280, int(sw * 0.85)), min(760, int(sh * 0.85))
        x, y   = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(800, 540)
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

        tk.Label(hdr, text="KAMERA LIVE & CAPTURE",
                 font=("Segoe UI", 15, "bold"),
                 bg=C["bg"], fg=C["fg"]).pack()

        bar = tk.Frame(hdr, bg=C["bg"])
        bar.pack(pady=(4, 0))
        tk.Label(bar, text="IP Camera URL:", font=("Segoe UI", 9, "bold"),
                 bg=C["bg"], fg=C["muted"]).pack(side="left", padx=4)
        self.url_entry = tk.Entry(bar, width=40, font=("Segoe UI", 10),
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

        # ── Main: dua panel kamera ──
        main = tk.Frame(wrap, bg=C["main"])
        main.grid(row=1, column=0, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)
        main.rowconfigure(2, weight=0)

        cam_area = tk.Frame(main, bg=C["main"])
        cam_area.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        cam_area.rowconfigure(0, weight=1)
        cam_area.columnconfigure(0, weight=1, uniform="cam")
        cam_area.columnconfigure(1, weight=1, uniform="cam")

        self.live_label    = self._panel(cam_area, 0, "KAMERA LIVE",    "Menghubungkan...")
        self.capture_label = self._panel(cam_area, 1, "HASIL CAPTURE",  "Belum ada capture")

        # ── Log ──
        self.log_lbl = tk.Label(main, text="", font=("Segoe UI", 10, "bold"),
                                bg=C["main"], fg=C["green"], height=2)
        self.log_lbl.grid(row=1, column=0, sticky="ew")

        # ── Tombol ──
        btn_row = tk.Frame(main, bg=C["main"])
        btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 8))
        for i in range(4):
            btn_row.columnconfigure(i, weight=1)

        for col, (txt, cmd, bg) in enumerate([
            ("📸 Capture",    self.capture_image,  "#2980B9"),
            ("💾 Simpan",     self.save_image,      "#27AE60"),
            ("🗑️ Hapus",      self.delete_capture,  "#E74C3C"),
            ("Tutup Halaman", self.close,            C["panel"]),
        ]):
            tk.Button(btn_row, text=txt, command=cmd,
                      font=("Segoe UI", 10, "bold"), bg=bg, fg="white",
                      relief="raised", bd=1, cursor="hand2"
                      ).grid(row=0, column=col,
                             padx=(0 if col == 0 else 5, 0),
                             sticky="ew", ipady=6)

    def _panel(self, parent, col, title, placeholder):
        """Buat LabelFrame panel kamera — label fill penuh via pack."""
        C = self.C
        frm = tk.LabelFrame(parent, text=title,
                             bg=C["panel"], fg=C["fg"],
                             font=("Segoe UI", 10, "bold"),
                             bd=1, relief="solid")
        frm.grid(row=0, column=col, sticky="nsew",
                 padx=(0 if col == 0 else 6, 0), pady=0)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        lbl = tk.Label(frm, bg=C["inner"], fg=C["muted"],
                       text=placeholder, font=("Segoe UI", 10))
        # KUNCI: fill="both" expand=True → lbl selalu fill frame
        lbl.pack(fill="both", expand=True, padx=4, pady=4)
        return lbl

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
        """Loop kamera — render frame ke ukuran aktual label."""
        if not self.is_running or self.camera is None:
            return
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                bgr = _to_bgr(frame)
                _render(self.live_label, bgr)
            self.after(33, self._loop)
        except Exception as e:
            print(f"loop: {e}")
            self.is_running = False

    # ─────────────────── Actions ──────────────────────────────────────────────
    def capture_image(self):
        if not (self.camera and self.camera.isOpened()):
            self.show_log("⚠️ Kamera tidak aktif!", "#E67E22"); return
        ret, frame = self.camera.read()
        if ret and frame is not None:
            self.captured_frame = _to_bgr(frame)
            _render(self.capture_label, self.captured_frame)
            self.show_log("✅ Gambar berhasil di-capture!", "#2ECC71")
        else:
            self.show_log("❌ Gagal mengambil frame", "#E74C3C")

    def save_image(self):
        if self.captured_frame is None:
            self.show_log("⚠️ Belum ada capture!", "#E67E22"); return
        os.makedirs(self.drive_folder, exist_ok=True)
        fname = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        cv2.imwrite(os.path.join(self.drive_folder, fname), self.captured_frame)
        self.show_log(f"✅ Disimpan: {fname}", "#2ECC71")

    def delete_capture(self):
        if self.captured_frame is None:
            self.show_log("ℹ️ Tidak ada capture", "#3498DB"); return
        self.captured_frame = None
        self.capture_label.configure(image="", text="Belum ada capture")
        self.capture_label.image = None
        self.show_log("✅ Capture dihapus!", "#2ECC71")

    def reconnect_camera(self):
        self.is_running = False
        if self.camera:
            try: self.camera.release()
            except Exception: pass
            self.camera = None
        val = self.url_entry.get()
        self.use_internal = val.startswith("KAMERA INTERNAL")
        if not self.use_internal:
            self.camera_url = val.strip()
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


# ─────────────────── Helper (shared) ─────────────────────────────────────────
def _to_bgr(frame: np.ndarray) -> np.ndarray:
    """Normalisasi frame ke BGR 3-channel."""
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def _resize_cover(rgb: np.ndarray, tw: int, th: int) -> np.ndarray:
    """Resize dengan mode COVER — gambar fill penuh tw x th."""
    sh_, sw_ = rgb.shape[:2]
    if sh_ <= 0 or sw_ <= 0:
        return rgb
    ratio  = max(tw / sw_, th / sh_)
    nw, nh = max(1, int(sw_ * ratio)), max(1, int(sh_ * ratio))
    interp = cv2.INTER_CUBIC if ratio > 1 else cv2.INTER_AREA
    res    = cv2.resize(rgb, (nw, nh), interpolation=interp)
    x0      = max(0, (nw - tw) // 2)
    y0      = max(0, (nh - th) // 2)
    crop   = res[y0:y0 + th, x0:x0 + tw]
    if crop.shape[1] != tw or crop.shape[0] != th:
        crop = cv2.resize(crop, (tw, th), interpolation=cv2.INTER_AREA)
    return crop


def _render(label: tk.Label, bgr: np.ndarray):
    """Render bgr ke label — ukuran = ukuran aktual label (winfo)."""
    label.update_idletasks()
    tw = label.winfo_width()
    th = label.winfo_height()
    if tw < 10 or th < 10:
        return
    rgb      = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rendered = _resize_cover(rgb, tw, th)
    photo    = ImageTk.PhotoImage(Image.fromarray(rendered))
    label.configure(image=photo, text="")
    label.image = photo  # cegah GC
