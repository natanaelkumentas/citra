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

class ImageAnalysisWindow(tk.Toplevel):
    SUPABASE_URL = "https://lvvaydjnadyywvdbiueu.supabase.co"
    SUPABASE_ANON_KEY = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2dmF5ZGpuYWR5eXd2ZGJpdWV1Iiwicm9sZSI6"
        "ImFub24iLCJpYXQiOjE3NzA3MDQ0ODIsImV4cCI6MjA4NjI4MDQ4Mn0."
        "PjWS-pF5M0nW5WzcI77Ux26OI-_nVt_mRxkFrtgZc68"
    )
    SUPABASE_TABLE = "image_statistics"

    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.use_internal = use_internal
        self.camera_url = camera_url or "http://172.29.241.86:8081/video"

        self.camera = None
        self.is_running = True
        self.is_live = True
        self.last_frame_bgr = None
        self.captured_frame = None
        self.current_stats = None
        self.current_image_name = ""
        self.last_saved_id = None
        self.selected_db_id = None
        self.latest_histogram_image = None

        self.show_red = tk.BooleanVar(value=True)
        self.show_green = tk.BooleanVar(value=True)
        self.show_blue = tk.BooleanVar(value=True)

        self.colors = {
            "bg_root": "#0B1D36",
            "bg_main": "#0E2744",
            "bg_panel": "#143457",
            "bg_panel_inner": "#0F2A48",
            "fg_primary": "#EAF2FF",
            "fg_muted": "#B8CBE2",
            "accent_blue": "#2D9CDB",
            "accent_green": "#27AE60",
            "accent_red": "#E74C3C",
            "accent_orange": "#F2994A"
        }

        self.title("Analisis Citra")
        self.geometry("1400x880")
        self.configure(bg=self.colors["bg_root"])
        try:
            self.state("zoomed")
        except:
            pass

        self.setup_ui()
        self.refresh_db_table()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def setup_ui(self):
        root_frame = tk.Frame(self, bg=self.colors["bg_root"])
        root_frame.pack(fill="both", expand=True, padx=12, pady=12)

        root_frame.grid_columnconfigure(0, weight=1)
        root_frame.grid_rowconfigure(1, weight=2) # top_content (kamera & hist)
        root_frame.grid_rowconfigure(2, weight=0) # stat box
        root_frame.grid_rowconfigure(3, weight=1) # db box
        root_frame.grid_rowconfigure(4, weight=0) # buttons

        # ── HEADER ──
        header = tk.Frame(root_frame, bg=self.colors["bg_root"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(
            header, text="DASHBOARD ANALISIS CITRA",
            font=("Segoe UI", 16, "bold"), bg=self.colors["bg_root"], fg=self.colors["fg_primary"]
        ).pack(anchor="center")

        # ── TOP CONTENT (Live Camera & Histogram) ──
        top_content = tk.Frame(root_frame, bg=self.colors["bg_root"], height=400)
        top_content.grid(row=1, column=0, sticky="nsew", pady=4)
        top_content.grid_propagate(False)
        top_content.grid_rowconfigure(0, weight=1)
        top_content.grid_columnconfigure(0, weight=1, uniform="panel")
        top_content.grid_columnconfigure(1, weight=1, uniform="panel")

        # KIRI (Kamera)
        left = tk.LabelFrame(
            top_content, text="Citra Live / Take Foto", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["accent_blue"], relief="solid", bd=1
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_propagate(False)

        self.live_wrap = tk.Frame(left, bg=self.colors["bg_panel_inner"], bd=1, relief="solid")
        self.live_wrap.pack(fill="both", expand=True, padx=6, pady=6)
        self.live_wrap.pack_propagate(False)

        self.live_label = tk.Label(
            self.live_wrap, bg=self.colors["bg_panel_inner"], fg=self.colors["fg_muted"], font=("Segoe UI", 10),
            text="Menunggu kamera..."
        )
        self.live_label.pack(fill="both", expand=True)

        # KANAN (Histogram)
        hist_box = tk.LabelFrame(
            top_content, text="Histogram beserta Nilai Peak", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg="#E67E22", relief="solid", bd=1
        )
        hist_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        hist_box.grid_propagate(False)

        self.hist_label = tk.Label(
            hist_box, bg=self.colors["bg_panel_inner"], fg=self.colors["fg_muted"], font=("Segoe UI", 10),
            text="Histogram akan tampil setelah capture"
        )
        self.hist_label.pack(fill="both", expand=True, padx=6, pady=(6, 2))

        chk_frame = tk.Frame(hist_box, bg=self.colors["bg_main"])
        chk_frame.pack(anchor="center", padx=6, pady=2)
        tk.Checkbutton(chk_frame, text="Merah (R)", variable=self.show_red, bg=self.colors["bg_main"], fg=self.colors["fg_primary"], selectcolor=self.colors["bg_panel"], activebackground=self.colors["bg_main"], activeforeground=self.colors["fg_primary"], command=self.refresh_histogram_display).pack(side="left", padx=(0, 6))
        tk.Checkbutton(chk_frame, text="Hijau (G)", variable=self.show_green, bg=self.colors["bg_main"], fg=self.colors["fg_primary"], selectcolor=self.colors["bg_panel"], activebackground=self.colors["bg_main"], activeforeground=self.colors["fg_primary"], command=self.refresh_histogram_display).pack(side="left", padx=(0, 6))
        tk.Checkbutton(chk_frame, text="Biru (B)", variable=self.show_blue, bg=self.colors["bg_main"], fg=self.colors["fg_primary"], selectcolor=self.colors["bg_panel"], activebackground=self.colors["bg_main"], activeforeground=self.colors["fg_primary"], command=self.refresh_histogram_display).pack(side="left")

        self.rgb_percent_info = tk.Label(
            hist_box, text="Rasio warna RGB: R - | G - | B -", bg=self.colors["bg_main"], fg=self.colors["fg_primary"], font=("Segoe UI", 9, "bold"), anchor="center"
        )
        self.rgb_percent_info.pack(fill="x", padx=6, pady=(0, 2))

        self.peak_label = tk.Label(
            hist_box, text="Peak keabuan dan RGB: -", justify="left", anchor="w", bg=self.colors["bg_main"], fg=self.colors["fg_muted"], font=("Segoe UI", 9)
        )
        self.peak_label.pack(fill="x", padx=6, pady=(0, 4))

        # ── STATISTIK ──
        stat_box = tk.LabelFrame(
            root_frame, text="Statistik Citra", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["fg_primary"], relief="solid", bd=1
        )
        stat_box.grid(row=2, column=0, sticky="ew", pady=4, ipadx=4, ipady=4)

        self.stat_labels = {}
        fields = [("nama_citra", "Nama Citra"), ("skewness", "Skewness"), ("average", "Average"), ("std", "Std"), ("kurtosis", "Kurtosis")]
        
        # Grid format for statistics for horizontal compactness
        stat_grid = tk.Frame(stat_box, bg=self.colors["bg_main"])
        stat_grid.pack(fill="x", padx=6)
        
        for i, (key, label) in enumerate(fields):
            row = i // 3
            col = (i % 3) * 2
            tk.Label(stat_grid, text=f"{label}:", anchor="w", bg=self.colors["bg_main"], fg=self.colors["fg_primary"], font=("Segoe UI", 9, "bold")).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=2)
            value_lbl = tk.Label(stat_grid, text="-", anchor="w", bg=self.colors["bg_main"], fg=self.colors["fg_muted"], font=("Segoe UI", 9))
            value_lbl.grid(row=row, column=col+1, sticky="ew", padx=(0, 12), pady=2)
            self.stat_labels[key] = value_lbl
            stat_grid.grid_columnconfigure(col+1, weight=1)

        # ── DATABASE ──
        db_box = tk.LabelFrame(
            root_frame, text="Database Supabase (Riwayat Statistik)", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["fg_primary"], relief="solid", bd=1
        )
        db_box.grid(row=3, column=0, sticky="nsew", pady=4)
        
        db_head = tk.Frame(db_box, bg=self.colors["bg_main"])
        db_head.pack(fill="x", padx=12, pady=4)
        tk.Label(db_head, text="Klik baris untuk memilih data", bg=self.colors["bg_main"], fg=self.colors["fg_muted"], font=("Segoe UI", 9, "italic")).pack(side="left")
        tk.Button(db_head, text="🔄 Refresh Data", command=self.refresh_db_table, bg=self.colors["accent_blue"], fg="white", font=("Segoe UI", 9, "bold"), bd=1, relief="raised", cursor="hand2").pack(side="right")

        table_wrap = tk.Frame(db_box, bg=self.colors["bg_main"])
        table_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        columns = ("id", "nama_citra", "average", "std", "skewness", "kurtosis", "created_at")
        self.db_tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=4)
        for col in columns:
            self.db_tree.heading(col, text=col)
        self.db_tree.column("id", width=40, anchor="center", stretch=False)
        self.db_tree.column("nama_citra", width=180, anchor="w")
        self.db_tree.column("average", width=90, anchor="e")
        self.db_tree.column("std", width=90, anchor="e")
        self.db_tree.column("skewness", width=90, anchor="e")
        self.db_tree.column("kurtosis", width=90, anchor="e")
        self.db_tree.column("created_at", width=150, anchor="w")
        self.db_tree.bind("<<TreeviewSelect>>", self.on_db_row_select)

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.db_tree.yview)
        xscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.db_tree.xview)
        self.db_tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.db_tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        # ── BUTTONS ──
        btn_box = tk.Frame(root_frame, bg=self.colors["bg_root"])
        btn_box.grid(row=4, column=0, sticky="ew", pady=(4, 0))

        buttons = [
            ("📸 Capture", self.capture_and_analyze, "#2980b9", "#2471a3"),
            ("💾 Simpan", self.save_to_supabase, "#27AE60", "#239B56"),
            ("📤 Export Excel", self.export_to_excel, "#8E44AD", "#732D91"),
            ("🗑️ Hapus", self.delete_data, "#E74C3C", "#C0392B"),
            ("🖨️ Print Hist", self.print_histogram, "#16A085", "#117A65"),
            ("❌ Tutup", self.close, self.colors["bg_panel"], "#0B1D36"),
        ]

        for i, (txt, cmd, color, act_color) in enumerate(buttons):
            tk.Button(
                btn_box, text=txt, command=cmd,
                font=("Segoe UI", 10, "bold"), cursor="hand2",
                bg=color, fg="white", activebackground=act_color, activeforeground="white",
                relief="raised", bd=1
            ).grid(row=0, column=i, padx=4, pady=2, sticky="ew", ipady=4)
            btn_box.grid_columnconfigure(i, weight=1)

        self.status_label = tk.Label(
            btn_box, text="Status: Menunggu capture...",
            anchor="w", bg=self.colors["bg_root"], fg=self.colors["accent_green"], font=("Segoe UI", 9, "italic")
        )
        self.status_label.grid(row=1, column=0, columnspan=len(buttons), sticky="w", pady=(2, 0))

    def start_camera(self):
        try:
            source = 0 if self.use_internal else self.camera_url
            self.camera = cv2.VideoCapture(source)

            if not self.use_internal and isinstance(self.camera_url, str) and self.camera_url.isdigit():
                self.camera.release()
                self.camera = cv2.VideoCapture(int(self.camera_url))

            if self.camera is None or not self.camera.isOpened():
                messagebox.showerror("Error", "Tidak bisa membuka kamera.")
                self.set_status("Kamera gagal dibuka.")
                return

            self.set_status("Kamera aktif. Silakan capture untuk analisis.")
            self.update_camera()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka kamera: {e}")
            self.set_status(f"Gagal membuka kamera: {e}")

    def update_camera(self):
        if not self.is_running:
            return

        try:
            if self.is_live and self.camera is not None:
                ret, frame = self.camera.read()
                if ret:
                    self.last_frame_bgr = frame
                    self.show_frame(frame)
            self.after(30, self.update_camera)
        except Exception as e:
            print(f"update_camera error: {e}")
            self.after(120, self.update_camera)

    def show_frame(self, bgr_frame):
        if bgr_frame is None:
            return

        target_w = max(1, self.live_label.winfo_width())
        target_h = max(1, self.live_label.winfo_height())
        if target_w < 10 or target_h < 10:
            return

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        rendered = self._resize_cover(rgb, target_w, target_h)

        pil_img = Image.fromarray(rendered)
        photo = ImageTk.PhotoImage(pil_img)
        self.live_label.configure(image=photo, text="")
        self.live_label.image = photo

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

    def capture_and_analyze(self):
        if self.last_frame_bgr is None:
            messagebox.showwarning("Peringatan", "Frame kamera belum tersedia.")
            return

        self.captured_frame = self.last_frame_bgr.copy()
        self.is_live = False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_image_name = f"capture_analisis_{timestamp}.jpg"
        save_path = os.path.join(self.drive_folder, self.current_image_name)
        try:
            cv2.imwrite(save_path, self.captured_frame)
        except Exception as e:
            print(f"Gagal simpan capture lokal: {e}")
        self.current_stats = self.compute_image_statistics(self.captured_frame, self.current_image_name)
        self.last_saved_id = None
        self.selected_db_id = None

        self.show_frame(self.captured_frame)
        self.update_stat_labels()
        self.refresh_histogram_display()
        self.set_status("Capture selesai. Statistik dan histogram sudah dianalisis.")

    def compute_image_statistics(self, bgr_frame, image_name):
        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        gray_flat = gray.astype(np.float64).ravel()

        average = float(np.mean(gray_flat))
        std = float(np.std(gray_flat))

        if std < 1e-12:
            skewness = 0.0
            kurtosis = 0.0
        else:
            z = (gray_flat - average) / std
            skewness = float(np.mean(z ** 3))
            kurtosis = float(np.mean(z ** 4) - 3.0)

        hist_gray = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
        b_ch, g_ch, r_ch = cv2.split(bgr_frame)
        hist_b = cv2.calcHist([b_ch], [0], None, [256], [0, 256]).flatten()
        hist_g = cv2.calcHist([g_ch], [0], None, [256], [0, 256]).flatten()
        hist_r = cv2.calcHist([r_ch], [0], None, [256], [0, 256]).flatten()

        sum_b = float(np.sum(b_ch))
        sum_g = float(np.sum(g_ch))
        sum_r = float(np.sum(r_ch))
        sum_rgb = max(sum_r + sum_g + sum_b, 1.0)
        red_percent = (sum_r / sum_rgb) * 100.0
        green_percent = (sum_g / sum_rgb) * 100.0
        blue_percent = (sum_b / sum_rgb) * 100.0

        peak_gray = int(np.argmax(hist_gray))
        peak_red = int(np.argmax(hist_r))
        peak_green = int(np.argmax(hist_g))
        peak_blue = int(np.argmax(hist_b))

        return {
            "nama_citra": image_name,
            "average": average,
            "std": std,
            "skewness": skewness,
            "kurtosis": kurtosis,
            "hist_gray": hist_gray,
            "hist_r": hist_r,
            "hist_g": hist_g,
            "hist_b": hist_b,
            "red_percent": red_percent,
            "green_percent": green_percent,
            "blue_percent": blue_percent,
            "peak_gray": peak_gray,
            "peak_gray_count": int(hist_gray[peak_gray]),
            "peak_red": peak_red,
            "peak_red_count": int(hist_r[peak_red]),
            "peak_green": peak_green,
            "peak_green_count": int(hist_g[peak_green]),
            "peak_blue": peak_blue,
            "peak_blue_count": int(hist_b[peak_blue]),
        }

    def update_stat_labels(self):
        if not self.current_stats:
            for lbl in self.stat_labels.values():
                lbl.config(text="-")
            self.rgb_percent_info.config(text="Rasio warna RGB: R - | G - | B -")
            self.peak_label.config(text="Peak keabuan dan RGB: -")
            return

        st = self.current_stats
        self.stat_labels["nama_citra"].config(text=st["nama_citra"])
        self.stat_labels["skewness"].config(text=f"{st['skewness']:.6f}")
        self.stat_labels["average"].config(text=f"{st['average']:.6f}")
        self.stat_labels["std"].config(text=f"{st['std']:.6f}")
        self.stat_labels["kurtosis"].config(text=f"{st['kurtosis']:.6f}")
        self.rgb_percent_info.config(
            text=(
                f"Rasio warna RGB: "
                f"R {st['red_percent']:.2f}% | "
                f"G {st['green_percent']:.2f}% | "
                f"B {st['blue_percent']:.2f}%"
            )
        )

        self.peak_label.config(
            text=(
                f"Peak Keabuan: {st['peak_gray']} (count={st['peak_gray_count']})\n"
                f"Peak R: {st['peak_red']} (count={st['peak_red_count']}) | "
                f"Peak G: {st['peak_green']} (count={st['peak_green_count']}) | "
                f"Peak B: {st['peak_blue']} (count={st['peak_blue_count']})"
            )
        )

    def refresh_histogram_display(self):
        if not self.current_stats:
            return

        hist_img = self.generate_histogram_image(
            self.current_stats,
            show_r=self.show_red.get(),
            show_g=self.show_green.get(),
            show_b=self.show_blue.get(),
        )
        self.latest_histogram_image = hist_img

        photo = ImageTk.PhotoImage(hist_img)
        self.hist_label.configure(image=photo, text="")
        self.hist_label.image = photo

    def generate_histogram_image(self, stats, show_r=True, show_g=True, show_b=True):
        width, height = 620, 300
        left_m, right_m, top_m, bot_m = 48, 18, 34, 40
        plot_w = width - left_m - right_m
        plot_h = height - top_m - bot_m

        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)

        draw.rectangle(
            [left_m, top_m, left_m + plot_w, top_m + plot_h],
            outline=(60, 60, 60), width=1
        )

        for i in range(0, 257, 64):
            x = left_m + int((i / 255.0) * plot_w)
            draw.line((x, top_m + plot_h, x, top_m + plot_h + 4), fill=(70, 70, 70), width=1)
            draw.text((x - 8, top_m + plot_h + 8), str(i), fill=(70, 70, 70))

        channels = []
        if show_r:
            channels.append(("R", stats["hist_r"], (220, 38, 38), int(stats["peak_red"])))
        if show_g:
            channels.append(("G", stats["hist_g"], (27, 156, 78), int(stats["peak_green"])))
        if show_b:
            channels.append(("B", stats["hist_b"], (41, 98, 255), int(stats["peak_blue"])))

        if not channels:
            draw.text((left_m + 12, top_m + plot_h // 2), "Pilih minimal satu channel warna.", fill=(100, 100, 100))
            return canvas

        max_val = max(float(np.max(hist)) for _, hist, _, _ in channels)
        max_val = max(max_val, 1.0)

        for _, hist, color, _ in channels:
            points = []
            for i in range(256):
                x = left_m + int((i / 255.0) * plot_w)
                y = top_m + plot_h - int((float(hist[i]) / max_val) * plot_h)
                points.append((x, y))
            draw.line(points, fill=color, width=2)

        gray_peak = int(stats["peak_gray"])
        gray_x = left_m + int((gray_peak / 255.0) * plot_w)
        draw.line((gray_x, top_m, gray_x, top_m + plot_h), fill=(120, 120, 120), width=1)
        draw.text((max(left_m, gray_x - 12), 2), f"Y:{gray_peak}", fill=(90, 90, 90))

        for idx, (name, hist, color, peak_idx) in enumerate(channels):
            peak_x = left_m + int((peak_idx / 255.0) * plot_w)
            peak_y = top_m + plot_h - int((float(hist[peak_idx]) / max_val) * plot_h)
            draw.ellipse((peak_x - 4, peak_y - 4, peak_x + 4, peak_y + 4), fill=color, outline=(0, 0, 0))
            draw.line((peak_x, top_m, peak_x, peak_y), fill=color, width=1)

            label = f"{name}:{peak_idx}"
            text_x = peak_x - 16
            text_x = max(left_m, min(text_x, left_m + plot_w - 42))
            text_y = max(2, top_m - 28 + (idx * 10))
            draw.text((text_x, text_y), label, fill=color)

        draw.text((left_m, 2), "Histogram RGB + Peak", fill=(40, 40, 40))
        return canvas

    def save_to_supabase(self):
        if not self.current_stats:
            messagebox.showwarning("Peringatan", "Silakan capture dulu sebelum simpan.")
            return

        payload = {
            "nama_citra": self.current_stats["nama_citra"],
            "average": self.current_stats["average"],
            "std": self.current_stats["std"],
            "skewness": self.current_stats["skewness"],
            "kurtosis": self.current_stats["kurtosis"],
        }

        try:
            rows = self.supabase_request(
                method="POST",
                path=f"/rest/v1/{self.SUPABASE_TABLE}",
                payload=payload,
                prefer_return=True
            )
            if isinstance(rows, list) and rows:
                self.last_saved_id = rows[0].get("id")
                self.selected_db_id = self.last_saved_id
            self.refresh_db_table(select_id=self.last_saved_id)
            self.set_status("Data statistik berhasil disimpan ke Supabase.")
            messagebox.showinfo("Sukses", "Statistik citra berhasil disimpan ke Supabase.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal simpan ke Supabase:\n{e}")
            self.set_status(f"Gagal simpan ke Supabase: {e}")

    def export_to_excel(self):
        try:
            rows = self.supabase_request(
                method="GET",
                path=(
                    f"/rest/v1/{self.SUPABASE_TABLE}"
                    "?select=id,nama_citra,average,std,skewness,kurtosis,created_at"
                    "&order=created_at.desc"
                )
            )
        except Exception as e:
            messagebox.showerror("Error", f"Gagal mengambil data dari Supabase:\n{e}")
            return

        if not rows:
            messagebox.showinfo("Info", "Tidak ada data di database untuk diexport.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Simpan Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not save_path:
            return

        headers = ["id", "nama_citra", "average", "std", "skewness", "kurtosis", "created_at"]
        try:
            self.write_simple_xlsx(rows, headers, save_path, sheet_name="image_statistics")
            self.set_status(f"Export Excel berhasil: {save_path}")
            messagebox.showinfo("Sukses", f"Data berhasil diexport ke:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menulis file Excel:\n{e}")

    def write_simple_xlsx(self, rows, headers, output_path, sheet_name="Sheet1"):
        def cell_ref(col_idx, row_idx):
            return f"{self.xlsx_column_name(col_idx)}{row_idx}"

        xml_rows = []
        row_num = 1

        head_cells = []
        for col, header in enumerate(headers, start=1):
            ref = cell_ref(col, row_num)
            text = xml_escape(str(header))
            head_cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        xml_rows.append(f'<row r="{row_num}">{"".join(head_cells)}</row>')

        for row in rows:
            row_num += 1
            cells = []
            for col, key in enumerate(headers, start=1):
                ref = cell_ref(col, row_num)
                value = row.get(key)
                if value is None:
                    continue

                is_number = isinstance(value, (int, float, np.integer, np.floating))
                if is_number and np.isfinite(float(value)):
                    cells.append(f'<c r="{ref}"><v>{float(value)}</v></c>')
                else:
                    text = xml_escape(str(value))
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')

            xml_rows.append(f'<row r="{row_num}">{"".join(cells)}</row>')

        sheet_data = "".join(xml_rows)
        safe_sheet_name = xml_escape(sheet_name)

        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{safe_sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        )

        worksheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{sheet_data}</sheetData>'
            '</worksheet>'
        )

        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            '</styleSheet>'
        )

        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            '</Types>'
        )

        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            '</Relationships>'
        )

        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/>'
            '</Relationships>'
        )

        core_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:creator>Citra App</dc:creator>'
            '<cp:lastModifiedBy>Citra App</cp:lastModifiedBy>'
            '</cp:coreProperties>'
        )

        app_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>Python</Application>'
            '</Properties>'
        )

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
            zf.writestr("xl/styles.xml", styles_xml)
            zf.writestr("docProps/core.xml", core_xml)
            zf.writestr("docProps/app.xml", app_xml)

    def xlsx_column_name(self, index):
        name = ""
        while index > 0:
            index, rem = divmod(index - 1, 26)
            name = chr(65 + rem) + name
        return name

    def refresh_db_table(self, select_id=None):
        try:
            rows = self.supabase_request(
                method="GET",
                path=(
                    f"/rest/v1/{self.SUPABASE_TABLE}"
                    "?select=id,nama_citra,average,std,skewness,kurtosis,created_at"
                    "&order=created_at.desc"
                    "&limit=200"
                )
            )
            self.populate_db_table(rows, select_id=select_id)
            self.set_status(f"Tabel database dimuat: {len(rows or [])} data.")
        except Exception as e:
            self.set_status(f"Gagal memuat tabel database: {e}")

    def populate_db_table(self, rows, select_id=None):
        if not hasattr(self, "db_tree"):
            return

        def fmt_num(v):
            try:
                return f"{float(v):.6f}"
            except Exception:
                return "-"

        for item in self.db_tree.get_children():
            self.db_tree.delete(item)

        selected_item = None
        for row in rows or []:
            row_id = row.get("id")
            item = self.db_tree.insert(
                "", "end",
                values=(
                    row_id,
                    row.get("nama_citra", ""),
                    fmt_num(row.get("average")),
                    fmt_num(row.get("std")),
                    fmt_num(row.get("skewness")),
                    fmt_num(row.get("kurtosis")),
                    row.get("created_at", "")
                )
            )
            if select_id is not None and row_id == select_id:
                selected_item = item

        if selected_item is not None:
            self.db_tree.selection_set(selected_item)
            self.db_tree.focus(selected_item)
            self.db_tree.see(selected_item)

    def on_db_row_select(self, _event=None):
        if not hasattr(self, "db_tree"):
            return
        selected = self.db_tree.selection()
        if not selected:
            return
        values = self.db_tree.item(selected[0], "values")
        if not values:
            return
        try:
            self.selected_db_id = int(values[0])
            self.last_saved_id = self.selected_db_id
            self.set_status(f"Baris database dipilih: id={self.selected_db_id}")
        except Exception:
            self.selected_db_id = None

    def delete_data(self):
        if not self.current_stats and self.last_saved_id is None and self.selected_db_id is None:
            messagebox.showwarning("Peringatan", "Tidak ada data yang bisa dihapus.")
            return

        if not messagebox.askyesno("Konfirmasi", "Hapus data dari Supabase?"):
            return

        try:
            target_id = self.selected_db_id if self.selected_db_id is not None else self.last_saved_id
            if target_id is not None:
                filter_query = f"id=eq.{target_id}"
            else:
                name = self.current_stats.get("nama_citra", "") if self.current_stats else ""
                if not name:
                    messagebox.showwarning("Peringatan", "Nama citra kosong, tidak bisa hapus.")
                    return
                safe_name = urllib.parse.quote(name, safe="")
                filter_query = f"nama_citra=eq.{safe_name}"

            self.supabase_request(
                method="DELETE",
                path=f"/rest/v1/{self.SUPABASE_TABLE}?{filter_query}",
                prefer_return=True
            )

            self.last_saved_id = None
            self.selected_db_id = None
            self.refresh_db_table()
            self.clear_current_analysis()
            self.set_status("Data berhasil dihapus dari Supabase.")
            messagebox.showinfo("Sukses", "Data berhasil dihapus.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menghapus data:\n{e}")
            self.set_status(f"Gagal menghapus data: {e}")

    def print_histogram(self):
        if self.latest_histogram_image is None:
            messagebox.showwarning("Peringatan", "Histogram belum tersedia. Capture dulu.")
            return

        try:
            save_path = filedialog.asksaveasfilename(
                title="Simpan Histogram",
                defaultextension=".png",
                initialfile=f"histogram_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                filetypes=[
                    ("PNG Image", "*.png"),
                    ("JPEG Image", "*.jpg"),
                    ("Semua File", "*.*"),
                ]
            )
            if not save_path:
                return

            self.latest_histogram_image.save(save_path)
            self.set_status(f"Histogram disimpan ke: {save_path}")
            messagebox.showinfo("Sukses", f"Histogram berhasil disimpan:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan histogram:\n{e}")
            self.set_status(f"Gagal menyimpan histogram: {e}")

    def clear_current_analysis(self):
        self.captured_frame = None
        self.current_stats = None
        self.current_image_name = ""
        self.latest_histogram_image = None

        self.update_stat_labels()
        self.hist_label.configure(image="", text="Histogram akan tampil setelah capture")
        self.hist_label.image = None
        self.rgb_percent_info.config(text="Rasio warna RGB: R - | G - | B -")

        self.is_live = True
        if self.last_frame_bgr is not None:
            self.show_frame(self.last_frame_bgr)
        self.set_status("Data lokal dibersihkan. Live camera aktif kembali.")

    def supabase_request(self, method, path, payload=None, prefer_return=False):
        url = f"{self.SUPABASE_URL}{path}"
        headers = {
            "apikey": self.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {self.SUPABASE_ANON_KEY}",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if prefer_return:
            headers["Prefer"] = "return=representation"

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                if not raw.strip():
                    return []
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code}: {detail}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Koneksi gagal: {e}")

    def set_status(self, text):
        self.status_label.config(text=f"Status: {text}")

    def close(self):
        self.is_running = False
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None
        self.destroy()


