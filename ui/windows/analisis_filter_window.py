import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.repository import AppRepository
from services import camera_service
from services.filter_service import FILTER_MAP


class AnalisisFilterWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.use_internal = use_internal
        self.camera_url = camera_url or "0"

        self.source_image = None
        self.result_image = None
        self.current_filter = None
        self.last_opened_path = ""

        self.camera = None
        self.is_camera_running = False
        self.last_live_frame = None
        self._filter_job = None

        self.colors = {
            "bg_root": "#0B1D36",
            "bg_main": "#0E2744",
            "bg_sidebar": "#112A46",
            "bg_sidebar_btn": "#1B3B63",
            "bg_panel": "#143457",
            "bg_panel_inner": "#0F2A48",
            "bg_desc": "#143457",
            "fg_primary": "#EAF2FF",
            "fg_muted": "#B8CBE2",
            "accent_blue": "#2D9CDB",
            "accent_orange": "#F2994A",
            "btn_active": "#26517F",
        }
        self.padding = {"outer": 10, "gap": 6, "row": 4}

        self.title("Analisis Filter")
        self.geometry("1480x820")
        self.configure(bg=self.colors["bg_root"])
        self.minsize(1280, 700)
        try:
            self.state("zoomed")
        except:
            pass

        self.threshold_var = tk.IntVar(value=127)
        self.status_var = tk.StringVar(value="Status: Siap. Buka gambar atau aktifkan kamera.")
        self.threshold_enabled_filters = {"Canny"}

        self._build_ui()
        self._update_threshold_label()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        root = tk.Frame(self, bg=self.colors["bg_root"])
        root.pack(
            fill="both",
            expand=True,
            padx=self.padding["outer"],
            pady=self.padding["outer"],
        )
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        self._build_left_menu(root)
        self._build_main_area(root)

    def _build_left_menu(self, parent):
        left_menu = tk.Frame(parent, bg=self.colors["bg_sidebar"], width=160, relief="solid", bd=1)
        left_menu.grid(row=0, column=0, sticky="nsw", padx=(0, self.padding["gap"]))
        left_menu.grid_propagate(False)

        tk.Label(
            left_menu,
            text="ANALISIS FILTER",
            bg=self.colors["bg_sidebar"],
            fg=self.colors["fg_primary"],
            font=("Segoe UI", 11, "bold"),
        ).pack(fill="x", padx=8, pady=(10, 8))

        buttons = [
            ("Open", self.open_image),
            ("Save", self.save_result_image),
            ("Camera", self.start_camera),
            ("Roberts", lambda: self.apply_filter("Roberts")),
            ("Prewitt", lambda: self.apply_filter("Prewitt")),
            ("Sobel", lambda: self.apply_filter("Sobel")),
            ("Frei-Chen", lambda: self.apply_filter("Frei-Chen")),
            ("Canny", lambda: self.apply_filter("Canny")),
            ("Otsu", lambda: self.apply_filter("Otsu")),
            ("Kirsch", lambda: self.apply_filter("Kirsch")),
            ("Segmentasi Warna", lambda: self.apply_filter("Segmentasi Warna")),
            ("Dwi Aras", lambda: self.apply_filter("Dwi Aras")),
            ("Aras Jamak", lambda: self.apply_filter("Aras Jamak")),
            ("Exit", self.close),
        ]

        for text, cmd in buttons:
            tk.Button(
                left_menu,
                text=text,
                command=cmd,
                font=("Segoe UI", 9, "bold"),
                bg=self.colors["bg_sidebar_btn"],
                fg=self.colors["fg_primary"],
                activebackground=self.colors["btn_active"],
                activeforeground=self.colors["fg_primary"],
                width=16,
                relief="raised",
                bd=1,
                cursor="hand2",
            ).pack(fill="x", padx=8, pady=2, ipady=1)

    def _build_main_area(self, parent):
        main = tk.Frame(parent, bg=self.colors["bg_main"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=0)  # image panels — fixed height
        main.grid_rowconfigure(1, weight=1)  # histogram — expands
        main.grid_rowconfigure(2, weight=0)  # camera controls
        main.grid_rowconfigure(3, weight=0)  # threshold
        main.grid_rowconfigure(4, weight=0)  # status
        main.grid_columnconfigure(0, weight=1)

        # ── Image panels (2 columns, standard fixed height) ──
        image_wrap = tk.Frame(main, bg=self.colors["bg_main"], height=480)
        image_wrap.grid(row=0, column=0, sticky="ew", pady=(self.padding["gap"], 4))
        image_wrap.grid_propagate(False)
        image_wrap.grid_rowconfigure(0, weight=1)
        image_wrap.grid_columnconfigure(0, weight=1, uniform="panel")
        image_wrap.grid_columnconfigure(1, weight=1, uniform="panel")

        self.original_label = self._make_panel(image_wrap, 0, 0, 1, "Original", "Belum ada gambar")
        self.result_label = self._make_panel(image_wrap, 0, 1, 1, "Hasil Filter", "Belum ada hasil")

        # ── Histogram (full width, larger) ──
        hist_wrap = tk.Frame(main, bg=self.colors["bg_main"])
        hist_wrap.grid(row=1, column=0, sticky="nsew", pady=(2, 2))
        hist_wrap.grid_rowconfigure(0, weight=1)
        hist_wrap.grid_columnconfigure(0, weight=1)

        self.hist_label = self._make_panel(hist_wrap, 0, 0, 1, "Histogram", "Histogram belum tersedia")

        self.original_label.bind("<Configure>", self._on_original_resize)
        self.result_label.bind("<Configure>", self._on_result_resize)
        self.hist_label.bind("<Configure>", self._on_hist_resize)

        # ── Camera controls ──
        camera_controls = tk.Frame(main, bg=self.colors["bg_main"])
        camera_controls.grid(row=2, column=0, sticky="ew", pady=(self.padding["row"], self.padding["row"]))
        for i in range(4):
            camera_controls.grid_columnconfigure(i, weight=1)

        self.capture_btn = tk.Button(
            camera_controls, text="Capture", 
            command=self.capture_camera, state="disabled",
            bg="#2980b9", fg="white", font=("Segoe UI", 10, "bold"), relief="raised", bd=1,
            activebackground="#2471a3", activeforeground="white"
        )
        self.capture_btn.grid(row=0, column=0, padx=4, sticky="ew", ipady=3)

        self.save_capture_btn = tk.Button(
            camera_controls, text="Simpan Capture", 
            command=self.save_camera_capture, state="disabled",
            bg="#27AE60", fg="white", font=("Segoe UI", 10, "bold"), relief="raised", bd=1,
            activebackground="#239B56", activeforeground="white"
        )
        self.save_capture_btn.grid(row=0, column=1, padx=4, sticky="ew", ipady=3)

        self.delete_capture_btn = tk.Button(
            camera_controls, text="Hapus Data", 
            command=self.delete_capture, state="normal",
            bg="#E67E22", fg="white", font=("Segoe UI", 10, "bold"), relief="raised", bd=1,
            activebackground="#D35400", activeforeground="white"
        )
        self.delete_capture_btn.grid(row=0, column=2, padx=4, sticky="ew", ipady=3)

        self.close_camera_btn = tk.Button(
            camera_controls, text="Tutup Kamera", 
            command=self.close_camera, state="disabled",
            bg="#E74C3C", fg="white", font=("Segoe UI", 10, "bold"), relief="raised", bd=1,
            activebackground="#C0392B", activeforeground="white"
        )
        self.close_camera_btn.grid(row=0, column=3, padx=4, sticky="ew", ipady=3)

        # ── Threshold ──
        threshold_box = tk.LabelFrame(
            main,
            text="Threshold",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["bg_panel"],
            fg=self.colors["fg_primary"],
            bd=1,
            relief="solid",
        )
        threshold_box.grid(row=3, column=0, sticky="ew", pady=(2, 2))

        self.threshold_value_label = tk.Label(
            threshold_box, text="127", bg=self.colors["bg_panel"], fg=self.colors["fg_primary"], 
            width=5, anchor="w", font=("Segoe UI", 10, "bold")
        )
        self.threshold_value_label.pack(side="left", padx=8, pady=4)

        self.threshold_scale = tk.Scale(
            threshold_box,
            from_=0,
            to=255,
            orient="horizontal",
            variable=self.threshold_var,
            command=self.on_threshold_change,
            length=700,
            bg=self.colors["bg_panel"],
            fg=self.colors["fg_primary"],
            troughcolor=self.colors["bg_panel_inner"],
            highlightthickness=0,
            state="disabled",
            showvalue=0,
        )
        self.threshold_scale.pack(side="left", fill="x", expand=True, padx=8, pady=4)

        # ── Status ──
        tk.Label(
            main,
            textvariable=self.status_var,
            anchor="w",
            bg=self.colors["bg_main"],
            fg=self.colors["fg_muted"],
            font=("Segoe UI", 9, "italic"),
        ).grid(row=4, column=0, sticky="ew", pady=(2, 0))

    def _make_panel(self, parent, row, col, colspan, title, empty_text):
        panel = tk.LabelFrame(
            parent,
            text=title,
            bg=self.colors["bg_panel"],
            fg=self.colors["fg_primary"],
            font=("Segoe UI", 10, "bold"),
            bd=1,
            relief="solid",
        )
        panel.grid(
            row=row,
            column=col,
            columnspan=colspan,
            sticky="nsew",
            padx=(0 if col == 0 else self.padding["gap"]/2, 0 if col == 1 or colspan == 2 else self.padding["gap"]/2),
            pady=(0 if row == 0 else self.padding["gap"], 0),
        )
        # Re-enable propagation lock for "standart" fixed container size
        panel.grid_propagate(False)

        label = tk.Label(
            panel,
            text=empty_text,
            bg=self.colors["bg_panel"], # Use theme blue instead of darker inner blue
            fg=self.colors["fg_primary"],
            anchor="center",
            font=("Segoe UI", 10),
        )
        label.pack(fill="both", expand=True)
        return label

    def set_status(self, text):
        self.status_var.set(f"Status: {text}")

    def open_image(self):
        file_path = filedialog.askopenfilename(
            title="Pilih gambar",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"), ("All Files", "*.*")],
        )
        if not file_path:
            return
        self._load_source_from_path(file_path)

    def _load_source_from_path(self, path):
        if self.is_camera_running:
            self.close_camera()

        bgr = self._imread_unicode(path)
        if bgr is None:
            messagebox.showerror("Error", "Gagal membaca file gambar.")
            return
        self.last_opened_path = path
        self.source_image = bgr
        self.result_image = bgr.copy()
        self.current_filter = None
        self._update_threshold_state(None)
        self.show_image(self.original_label, self.source_image)
        self.show_image(self.result_label, self.result_image)
        self.show_histogram(self.result_image)
        self.save_capture_btn.configure(state="normal")
        self.set_status(f"Gambar dibuka: {os.path.basename(path)}")

    def save_result_image(self):
        if self.result_image is None:
            messagebox.showwarning("Info", "Belum ada hasil filter untuk disimpan.")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filter_name = (self.current_filter or "original").lower().replace(" ", "_")
        save_path = filedialog.asksaveasfilename(
            title="Simpan hasil filter",
            initialdir=self.drive_folder,
            initialfile=f"hasil_{filter_name}_{ts}.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All Files", "*.*")],
        )
        if not save_path:
            return

        ok = self._imwrite_unicode(save_path, self.result_image)
        if not ok:
            messagebox.showerror("Error", "Gagal menyimpan hasil filter.")
            return
        self.set_status(f"Hasil filter disimpan: {os.path.basename(save_path)}")

    def start_camera(self):
        if self.is_camera_running:
            self.set_status("Kamera sudah aktif.")
            return
        try:
            self.camera = camera_service.open_camera(self.use_internal, self.camera_url)
        except Exception as e:
            messagebox.showerror("Error", f"Kamera tidak dapat dibuka: {e}")
            self.camera = None
            return

        self.is_camera_running = True
        self.capture_btn.configure(state="normal")
        self.close_camera_btn.configure(state="normal")
        self.set_status("Kamera aktif. Klik Capture untuk ambil gambar.")
        self._update_camera_loop()

    def _update_camera_loop(self):
        if not self.is_camera_running or self.camera is None:
            return

        ret, frame = self.camera.read()
        if ret and frame is not None:
            self.last_live_frame = frame.copy()
            self.show_image(self.original_label, frame)

        self.after(30, self._update_camera_loop)

    def capture_camera(self):
        if self.last_live_frame is None:
            messagebox.showwarning("Info", "Belum ada frame kamera.")
            return

        self.source_image = self.last_live_frame.copy()
        self.result_image = self.source_image.copy()
        self.show_image(self.original_label, self.source_image)
        self.show_image(self.result_label, self.result_image)
        self.show_histogram(self.result_image)
        self.save_capture_btn.configure(state="normal")

        if self.current_filter:
            self.apply_filter(self.current_filter)

        self.set_status("Capture berhasil. Kamu bisa pilih filter.")

    def save_camera_capture(self):
        if self.source_image is None:
            messagebox.showwarning("Info", "Belum ada capture untuk disimpan.")
            return

        os.makedirs(self.drive_folder, exist_ok=True)
        fname = f"capture_analisis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(self.drive_folder, fname)
        ok = self._imwrite_unicode(save_path, self.source_image)
        if not ok:
            messagebox.showerror("Error", "Gagal menyimpan capture kamera.")
            return
        self.set_status(f"Capture kamera disimpan: {fname}")

    def delete_capture(self):
        self.source_image = None
        self.result_image = None
        self.current_filter = None
        self._update_threshold_state(None)

        self.original_label.configure(image="", text="Belum ada gambar")
        self.original_label.image = None
        self.result_label.configure(image="", text="Belum ada hasil")
        self.result_label.image = None
        self.hist_label.configure(image="", text="Histogram belum tersedia")
        self.hist_label.image = None

        if self.is_camera_running:
            self.set_status("Capture dihapus. Kamera tetap aktif.")
        else:
            self.set_status("Data gambar dibersihkan.")

    def close_camera(self):
        self.is_camera_running = False
        self.last_live_frame = None
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None

        self.capture_btn.configure(state="disabled")
        self.close_camera_btn.configure(state="disabled")
        self.set_status("Kamera ditutup.")

        if self.source_image is not None:
            self.show_image(self.original_label, self.source_image)
        else:
            self.original_label.configure(image="", text="Belum ada gambar")
            self.original_label.image = None

    def on_threshold_change(self, _value):
        self._update_threshold_label()
        # Fast debounce (30ms) to prevent RecursionError on rapid slider movement
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(30, self._apply_filter_direct)

    def _apply_filter_direct(self):
        self._filter_job = None
        if self.source_image is not None and self.current_filter is not None:
            self.apply_filter(self.current_filter)

    def _update_threshold_label(self):
        self.threshold_value_label.configure(text=str(self.threshold_var.get()))

    def apply_filter(self, filter_name):
        if self.source_image is None:
            messagebox.showwarning("Info", "Silakan buka/capture gambar dulu.")
            return

        self.current_filter = filter_name
        self._update_threshold_state(filter_name)
        t = int(self.threshold_var.get()) if filter_name in self.threshold_enabled_filters else 127

        fn = FILTER_MAP.get(filter_name)
        if fn is None:
            messagebox.showerror("Error", f"Filter '{filter_name}' tidak dikenal.")
            return

        try:
            result = fn(self.source_image, t)
            self.result_image = result
            self.show_image(self.result_label, self.result_image)
            self.show_histogram(self.result_image)
            self.set_status(f"Filter {filter_name} diterapkan.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menerapkan filter {filter_name}.\n{e}")

    def _update_threshold_state(self, filter_name):
        if filter_name in self.threshold_enabled_filters:
            self.threshold_scale.configure(state="normal")
        else:
            self.threshold_scale.configure(state="disabled")

    def _get_label_size(self, label_widget, fallback_w, fallback_h):
        # Removed update_idletasks() to prevent RecursionError in nested event loops
        width = max(1, int(label_widget.winfo_width()))
        height = max(1, int(label_widget.winfo_height()))
        if width <= 1 or height <= 1:
            return fallback_w, fallback_h
        return width, height

    def show_image(self, label_widget, image_data):
        if image_data is None:
            label_widget.configure(image="", text="Tidak ada gambar")
            label_widget.image = None
            return

        if image_data.ndim == 2:
            rgb = cv2.cvtColor(image_data, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)

        target_w, target_h = self._get_label_size(label_widget, 390, 300)
        rendered = self._resize_cover(rgb, target_w, target_h)
        photo = ImageTk.PhotoImage(Image.fromarray(rendered))
        label_widget.configure(image=photo, text="")
        label_widget.image = photo

    def show_histogram(self, image_data):
        if image_data is None:
            self.hist_label.configure(image="", text="Histogram belum tersedia")
            self.hist_label.image = None
            return

        target_w, target_h = self._get_label_size(self.hist_label, 600, 350)
        hist_img = self._create_histogram_image(image_data, target_w, target_h)
        photo = ImageTk.PhotoImage(Image.fromarray(hist_img))
        self.hist_label.configure(image=photo, text="")
        self.hist_label.image = photo

    def _create_histogram_image(self, image_data, width, height):
        """Create detailed histogram with axis labels, gridlines, peak values"""
        width = max(400, int(width))
        height = max(250, int(height))

        # Dark themed background
        bg_color = (15, 42, 72)  # #0F2A48
        canvas = np.full((height, width, 3), bg_color[0], dtype=np.uint8)
        canvas[:, :, 0] = bg_color[0]
        canvas[:, :, 1] = bg_color[1]
        canvas[:, :, 2] = bg_color[2]

        # Margins for axis labels
        left_margin = max(60, int(width * 0.07))
        right_margin = max(20, int(width * 0.02))
        top_margin = max(30, int(height * 0.10))
        bottom_margin = max(50, int(height * 0.16))

        plot_left = left_margin
        plot_top = top_margin
        plot_right = width - right_margin
        plot_bottom = height - bottom_margin
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top

        if plot_w < 50 or plot_h < 50:
            return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)

        # Draw plot area background
        cv2.rectangle(canvas, (plot_left, plot_top), (plot_right, plot_bottom), (20, 50, 82), -1)
        cv2.rectangle(canvas, (plot_left, plot_top), (plot_right, plot_bottom), (60, 90, 130), 1)

        # Calculate histograms
        if image_data.ndim == 2:
            channels = [(image_data, (200, 200, 200), "Gray")]
        else:
            bgr = image_data if image_data.shape[2] == 3 else image_data[:, :, :3]
            channels = [
                (bgr[:, :, 2], (80, 80, 230), "Red"),
                (bgr[:, :, 1], (80, 200, 80), "Green"),
                (bgr[:, :, 0], (230, 150, 80), "Blue"),
            ]

        histograms = []
        for channel_data, color, name in channels:
            hist = cv2.calcHist([channel_data], [0], None, [256], [0, 256]).flatten()
            peak_idx = int(np.argmax(hist))
            peak_val = int(hist[peak_idx])
            histograms.append((hist, color, name, peak_idx, peak_val))

        max_val = max(float(np.max(h)) for h, _, _, _, _ in histograms)
        if max_val <= 0:
            max_val = 1.0

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.35, min(0.55, width / 1100))
        label_color = (180, 200, 220)
        grid_color = (40, 65, 100)

        # ── Y-axis labels & horizontal gridlines ──
        y_ticks = 5
        for i in range(y_ticks + 1):
            frac = i / y_ticks
            y = plot_bottom - int(frac * plot_h)
            val = int(frac * max_val)

            # Dashed gridline
            if 0 < i < y_ticks:
                for x in range(plot_left, plot_right, 5):
                    cv2.line(canvas, (x, y), (min(x + 2, plot_right), y), grid_color, 1)

            # Tick mark
            cv2.line(canvas, (plot_left - 4, y), (plot_left, y), label_color, 1)

            # Label
            if val >= 10000:
                label_text = f"{val / 1000:.0f}k"
            elif val >= 1000:
                label_text = f"{val / 1000:.1f}k"
            else:
                label_text = str(val)
            text_size = cv2.getTextSize(label_text, font, font_scale, 1)[0]
            cv2.putText(canvas, label_text, (plot_left - text_size[0] - 8, y + 4),
                        font, font_scale, label_color, 1, cv2.LINE_AA)

        # ── X-axis labels & vertical gridlines ──
        x_ticks = [0, 32, 64, 96, 128, 160, 192, 224, 255]
        for val in x_ticks:
            x = plot_left + int(val * plot_w / 255)

            # Dashed gridline
            if 0 < val < 255:
                for y in range(plot_top, plot_bottom, 5):
                    cv2.line(canvas, (x, y), (x, min(y + 2, plot_bottom)), grid_color, 1)

            # Tick mark
            cv2.line(canvas, (x, plot_bottom), (x, plot_bottom + 4), label_color, 1)

            # Label
            text = str(val)
            text_size = cv2.getTextSize(text, font, font_scale, 1)[0]
            cv2.putText(canvas, text, (x - text_size[0] // 2, plot_bottom + 18),
                        font, font_scale, label_color, 1, cv2.LINE_AA)

        # ── Draw histogram lines with peak dot+label ON the line ──
        for hist, color, name, peak_idx, peak_val in histograms:
            points = []
            for i in range(256):
                x = plot_left + int(i * plot_w / 255)
                y = plot_bottom - int((hist[i] / max_val) * plot_h)
                y = max(plot_top, min(plot_bottom, y))
                points.append((x, y))
            for i in range(1, len(points)):
                cv2.line(canvas, points[i - 1], points[i], color, 2, cv2.LINE_AA)

            # Peak marker: circle dot at the peak point on the line
            peak_x = plot_left + int(peak_idx * plot_w / 255)
            peak_y = plot_bottom - int((hist[peak_idx] / max_val) * plot_h)
            peak_y = max(plot_top, min(plot_bottom, peak_y))
            cv2.circle(canvas, (peak_x, peak_y), 5, color, -1, cv2.LINE_AA)
            cv2.circle(canvas, (peak_x, peak_y), 6, (255, 255, 255), 1, cv2.LINE_AA)

            # Peak label next to the dot
            peak_text = f"{name[0]}:{peak_idx}"
            label_x = peak_x + 8
            label_y = peak_y - 6
            
            # Offset labels per channel to help prevent overlap
            if name == "Red": label_y -= 12
            if name == "Blue": label_y += 12
                
            # Ensure label stays within plot bounds
            if label_x + 40 > plot_right:
                label_x = peak_x - 45
            if label_y < plot_top + 10:
                label_y = peak_y + 16
            if label_y > height - bottom_margin - 5:
                label_y = peak_y - 12
                
            cv2.putText(canvas, peak_text, (label_x, label_y),
                        font, font_scale, color, 1, cv2.LINE_AA)

        # ── Axis titles ──
        x_title = "Pixel Intensity (0 - 255)"
        text_size = cv2.getTextSize(x_title, font, font_scale, 1)[0]
        cv2.putText(canvas, x_title, (plot_left + plot_w // 2 - text_size[0] // 2, height - 8),
                    font, font_scale, label_color, 1, cv2.LINE_AA)

        return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)

    def _resize_contain(self, rgb_image, target_w, target_h):
        src_h, src_w = rgb_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return rgb_image

        ratio = min(target_w / float(src_w), target_h / float(src_h))
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))

        resized = cv2.resize(rgb_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Create theme-colored canvas instead of black
        # hex #143457 -> BGR (87, 52, 20)
        canvas = np.full((target_h, target_w, 3), (87, 52, 20), dtype=np.uint8)
        
        # Center the resized image
        y_off = (target_h - new_h) // 2
        x_off = (target_w - new_w) // 2
        
        canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
        return canvas

    def _resize_cover(self, rgb_image, target_w, target_h):
        src_h, src_w = rgb_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return rgb_image

        ratio = max(target_w / float(src_w), target_h / float(src_h))
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        
        interp = cv2.INTER_CUBIC if ratio > 1.0 else cv2.INTER_AREA
        resized = cv2.resize(rgb_image, (new_w, new_h), interpolation=interp)
        
        x0 = (new_w - target_w) // 2
        y0 = (new_h - target_h) // 2
        
        cropped = resized[y0:y0+target_h, x0:x0+target_w]
        if cropped.shape[1] != target_w or cropped.shape[0] != target_h:
            cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_AREA)
        return cropped

    def _on_original_resize(self, _event):
        if self.is_camera_running and self.last_live_frame is not None and self.source_image is None:
            self.show_image(self.original_label, self.last_live_frame)
        elif self.source_image is not None:
            self.show_image(self.original_label, self.source_image)

    def _on_result_resize(self, _event):
        if self.result_image is not None:
            self.show_image(self.result_label, self.result_image)

    def _on_hist_resize(self, _event):
        if self.result_image is not None:
            self.show_histogram(self.result_image)

    def _imread_unicode(self, path):
        try:
            data = np.fromfile(path, dtype=np.uint8)
            if data.size == 0:
                return None
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            return img
        except Exception:
            return None

    def _imwrite_unicode(self, path, image_data):
        try:
            ext = os.path.splitext(path)[1].lower() or ".png"
            if ext not in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"]:
                ext = ".png"
                path = path + ".png"
            ok, enc = cv2.imencode(ext, image_data)
            if not ok:
                return False
            enc.tofile(path)
            return True
        except Exception:
            return False

    def close(self):
        self.close_camera()
        self.destroy()


if __name__ == "__main__":
    app_repo = AppRepository()
    root = tk.Tk()
    root.withdraw()
    win = AnalisisFilterWindow(root, app_repo.get_drive_folder())
    win.focus_force()
    root.mainloop()

