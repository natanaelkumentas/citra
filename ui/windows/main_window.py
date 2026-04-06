# ui/windows/main_window.py — Window utama aplikasi (dashboard menu)
# Update import: semua class dipindah ke ui.windows.* dan core.repository
# Nama class CameraApp tetap sama (backward compatible).

import tkinter as tk

from core.repository import AppRepository
from ui.windows.camera_choice_dialog import CameraChoiceDialog
from ui.windows.image_analysis_window import ImageAnalysisWindow
from ui.windows.analisis_filter_window import AnalisisFilterWindow
from ui.windows.conversi_hull_window import ConversiHullWindow
from ui.windows.file_window import FileWindow
from ui.windows.camera_window import CameraWindow
from ui.windows.camera_color_window import CameraColorWindow
from ui.windows.conversion_window import ConversionWindow
from ui.windows.analisis_warna_window import AnalisisWarnaWindow


class CameraApp:
    """Aplikasi Utama: file, kamera, warna, analisis, konversi, analisis filter."""

    def __init__(self):
        # ── folder lokal ──
        self.repository = AppRepository()
        self.drive_folder = self.repository.get_drive_folder()
        self.gdrive_link  = self.repository.get_gdrive_link()

        # ── root window ──
        self.root = tk.Tk()
        self.root.title("Aplikasi Kamera - Window Utama")
        self.root.geometry("460x660")
        self.root.configure(bg="#2C3E50")

        # ── tracking window ──
        self.file_window           = None
        self.camera_window         = None
        self.camera_color_window   = None
        self.conversion_window     = None
        self.image_analysis_window = None
        self.analisis_filter_window = None
        self.conversi_hull_window  = None
        self.analisis_warna_window = None

        self.setup_main_window()

    # ─────────────────────────────────────────
    # UI: dashboard utama
    # ─────────────────────────────────────────
    def setup_main_window(self):
        main_frame = tk.Frame(self.root, bg="#2C3E50")
        main_frame.pack(expand=True, fill="both", padx=20, pady=15)

        # judul
        tk.Label(
            main_frame, text="APLIKASI KAMERA",
            font=("Arial", 24, "bold"), bg="#2C3E50", fg="white"
        ).pack(pady=(0, 8))

        tk.Label(
            main_frame, text="Pilih Menu:",
            font=("Arial", 12), bg="#2C3E50", fg="#ECF0F1"
        ).pack(pady=(0, 6))

        # ── helper untuk bikin tombol ──
        def make_btn(text, command, color, active_color):
            return tk.Button(
                main_frame, text=text, command=command,
                font=("Arial", 13, "bold"),
                bg=color, fg="white",
                activebackground=active_color, activeforeground="white",
                width=28, height=1,
                cursor="hand2", relief="raised", bd=3
            )

        # ── tombol utama ──
        make_btn("📁  Buka File", self.open_file_window,
                 "#3498DB", "#2980B9").pack(pady=5)

        make_btn("📷  Buka Kamera Simpan",
                 lambda: self.open_camera_choice_window(mode='save'),
                 "#27AE60", "#229954").pack(pady=5)

        make_btn("🎨  Buka Kamera Warna",
                 lambda: self.open_camera_choice_window(mode='color'),
                 "#9B59B6", "#8E44AD").pack(pady=5)

        make_btn("📊  Analisis Citra",
                 self.open_image_analysis_window,
                 "#34495E", "#2C3E50").pack(pady=5)

        make_btn("🧪  Analisis Filter",
                 self.open_analisis_filter_window,
                 "#5D6D7E", "#4D5656").pack(pady=5)

        make_btn("🧭  Conversi hull",
                 self.open_conversi_hull_window,
                 "#1F618D", "#154360").pack(pady=5)

        make_btn("📊  Analisis Warna",
                 self.open_analisis_warna_window,
                 "#2980B9", "#1F618D").pack(pady=5)

        # ── separator ──
        tk.Frame(main_frame, bg="#ECF0F1", height=2).pack(
            fill="x", pady=10, padx=30
        )

        # ── label seksi konversi ──
        tk.Label(
            main_frame, text="— Konversi Citra —",
            font=("Arial", 11, "italic"), bg="#2C3E50", fg="#BDC3C7"
        ).pack(pady=(2, 4))

        # ── tombol konversi ──
        make_btn("🔄  RGB → Grayscale",
                 lambda: self.open_conversion_window(mode='rgb_to_gray'),
                 "#E67E22", "#D35400").pack(pady=5)

        make_btn("🔄  Grayscale → Biner (B/W)",
                 lambda: self.open_conversion_window(mode='gray_to_biner'),
                 "#1ABC9C", "#16A085").pack(pady=5)

        # ── separator ──
        tk.Frame(main_frame, bg="#ECF0F1", height=2).pack(
            fill="x", pady=10, padx=30
        )

        # ── tutup ──
        make_btn("❌  Tutup Aplikasi", self.close_application,
                 "#E74C3C", "#C0392B").pack(pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.close_application)

    # ─────────────────────────────────────────
    # Pembuka window
    # ─────────────────────────────────────────
    def open_file_window(self):
        if self.file_window is not None and self.file_window.winfo_exists():
            self.file_window.lift()
            return
        self.file_window = FileWindow(self.root, self.drive_folder, self.gdrive_link)

    def open_camera_choice_window(self, mode='save'):
        CameraChoiceDialog(
            self.root, mode=mode,
            callback=lambda use_internal, url: self._open_camera_by_choice(mode, use_internal, url)
        )

    def _open_camera_by_choice(self, mode, use_internal, url):
        if mode == 'save':
            if self.camera_window is not None and self.camera_window.winfo_exists():
                self.camera_window.lift()
                return
            self.camera_window = CameraWindow(
                self.root, self.drive_folder,
                use_internal=use_internal, camera_url=url
            )
        else:
            if self.camera_color_window is not None and self.camera_color_window.winfo_exists():
                self.camera_color_window.lift()
                return
            self.camera_color_window = CameraColorWindow(
                self.root, self.drive_folder,
                use_internal=use_internal, camera_url=url
            )

    def open_conversion_window(self, mode='rgb_to_gray'):
        """Buka window konversi citra. Hanya satu instance yang boleh ada."""
        if self.conversion_window is not None and self.conversion_window.winfo_exists():
            if self.conversion_window.conv_mode == mode:
                self.conversion_window.lift()
                return
            else:
                self.conversion_window.close()

        CameraChoiceDialog(
            self.root, mode='conversion',
            callback=lambda use_internal, url: self._launch_conversion(mode, use_internal, url)
        )

    def _launch_conversion(self, mode, use_internal, url):
        self.conversion_window = ConversionWindow(
            self.root, self.drive_folder,
            conv_mode=mode,
            use_internal=use_internal,
            camera_url=url
        )

    def open_image_analysis_window(self):
        CameraChoiceDialog(
            self.root, mode='analysis',
            callback=lambda use_internal, url: self._launch_image_analysis(use_internal, url)
        )

    def _launch_image_analysis(self, use_internal, url):
        if self.image_analysis_window is not None and self.image_analysis_window.winfo_exists():
            self.image_analysis_window.lift()
            return
        self.image_analysis_window = ImageAnalysisWindow(
            self.root,
            self.drive_folder,
            use_internal=use_internal,
            camera_url=url
        )

    def open_analisis_filter_window(self):
        CameraChoiceDialog(
            self.root, mode='analysis',
            callback=lambda use_internal, url: self._launch_analisis_filter(use_internal, url)
        )

    def _launch_analisis_filter(self, use_internal, url):
        if self.analisis_filter_window is not None and self.analisis_filter_window.winfo_exists():
            self.analisis_filter_window.lift()
            return
        self.analisis_filter_window = AnalisisFilterWindow(
            self.root,
            self.drive_folder,
            use_internal=use_internal,
            camera_url=url
        )

    def open_conversi_hull_window(self):
        CameraChoiceDialog(
            self.root, mode='analysis',
            callback=lambda use_internal, url: self._launch_conversi_hull(use_internal, url)
        )

    def _launch_conversi_hull(self, use_internal, url):
        if self.conversi_hull_window is not None and self.conversi_hull_window.winfo_exists():
            self.conversi_hull_window.lift()
            return
        self.conversi_hull_window = ConversiHullWindow(
            self.root,
            self.drive_folder,
            use_internal=use_internal,
            camera_url=url
        )

    def open_analisis_warna_window(self):
        CameraChoiceDialog(
            self.root, mode='analysis',
            callback=lambda use_internal, url: self._launch_analisis_warna(use_internal, url)
        )

    def _launch_analisis_warna(self, use_internal, url):
        if self.analisis_warna_window is not None and self.analisis_warna_window.winfo_exists():
            self.analisis_warna_window.lift()
            return
        self.analisis_warna_window = AnalisisWarnaWindow(
            self.root,
            self.drive_folder,
            use_internal=use_internal,
            camera_url=url
        )

    # ─────────────────────────────────────────
    # Tutup seluruh aplikasi
    # ─────────────────────────────────────────
    def close_application(self):
        for w in (self.file_window, self.camera_window,
                  self.camera_color_window, self.conversion_window,
                  self.image_analysis_window, self.analisis_filter_window,
                  self.conversi_hull_window, self.analisis_warna_window):
            if w is not None and w.winfo_exists():
                w.close()
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
