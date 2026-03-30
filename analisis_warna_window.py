import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os
from datetime import datetime
import pandas as pd
import json
import urllib.request
import urllib.parse
import urllib.error
from ui_theme import apply_mixed_theme, PREVIEW_PROFILES, resize_cover_rgb

class AnalisisWarnaWindow(tk.Toplevel):
    SUPABASE_URL = "https://lvvaydjnadyywvdbiueu.supabase.co"
    SUPABASE_ANON_KEY = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx2dmF5ZGpuYWR5eXd2ZGJpdWV1Iiwicm9sZSI6"
        "ImFub24iLCJpYXQiOjE3NzA3MDQ0ODIsImV4cCI6MjA4NjI4MDQ4Mn0."
        "PjWS-pF5M0nW5WzcI77Ux26OI-_nVt_mRxkFrtgZc68"
    )
    SUPABASE_TABLE = "analisis_gambar" # Sesuai dengan tabel_analisis_gambar.md

    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.camera = None
        self.is_running = False
        self.is_live = True
        self.is_file_mode = False
        self.current_frame = None
        self.captured_frame = None
        self.file_frame = None
        self.last_stats = None
        
        self.use_internal = use_internal
        self.camera_url = camera_url
        
        # ROI Settings
        self.roi_size = tk.IntVar(value=100)
        
        # Histogram Filters
        self.show_r = tk.BooleanVar(value=True)
        self.show_g = tk.BooleanVar(value=True)
        self.show_b = tk.BooleanVar(value=True)
        
        # Theme colors (Dark Blue)
        self.colors = {
            "bg_root": "#06162B",
            "bg_surface": "#0B1F38",
            "bg_panel": "#102847",
            "bg_input": "#0D223C",
            "bg_button": "#1F4E7A",
            "fg_primary": "#EAF2FF",
            "fg_muted": "#C4D4E8",
            "accent": "#4FA3FF",
            "red": "#E74C3C",
            "green": "#27AE60",
            "yellow": "#F1C40F"
        }

        self.title("Aplikasi Statistik Warna Kamera - Dashboard")
        self.geometry("1400x900")
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
        # Main layout: Top (Working Area) and Bottom (History Table)
        main_vbox = tk.Frame(self, bg=self.colors["bg_root"])
        main_vbox.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Upper Area: Horizontal Split
        upper_area = tk.Frame(main_vbox, bg=self.colors["bg_root"])
        upper_area.pack(fill="both", expand=True)
        upper_area.grid_columnconfigure(0, weight=3) # Camera large
        upper_area.grid_columnconfigure(1, weight=2) # Stats & Hist
        upper_area.grid_rowconfigure(0, weight=1)

        # Left Panel: Camera view
        left_panel = tk.Frame(upper_area, bg=self.colors["bg_surface"], bd=1, relief="solid")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        header_l = tk.Frame(left_panel, bg=self.colors["bg_surface"])
        header_l.pack(fill="x", pady=10)
        tk.Label(header_l, text="LIVE CAMERA CAPTURE", font=("Arial", 14, "bold"),
                 bg=self.colors["bg_surface"], fg=self.colors["accent"]).pack()

        # Video Wrapper
        self.video_wrap = tk.Frame(left_panel, bg="#000000")
        self.video_wrap.pack(fill="both", expand=True, padx=10, pady=5)
        self.video_wrap.pack_propagate(False)

        self.video_label = tk.Label(self.video_wrap, bg="#000000")
        self.video_label.pack(fill="both", expand=True)

        # ROI Slider at bottom of camera panel
        ctrl_frame = tk.Frame(left_panel, bg=self.colors["bg_surface"])
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(ctrl_frame, text="Ukuran ROI:", bg=self.colors["bg_surface"], fg=self.colors["fg_primary"]).pack(side="left", padx=5)
        self.roi_slider = tk.Scale(ctrl_frame, from_=50, to=400, orient="horizontal", 
                                   variable=self.roi_size, bg=self.colors["bg_surface"], 
                                   fg=self.colors["fg_primary"], highlightthickness=0,
                                   troughcolor=self.colors["bg_input"], activebackground=self.colors["accent"])
        self.roi_slider.pack(side="left", fill="x", expand=True, padx=5)

        # Right Panel: Stats & Histogram
        right_panel = tk.Frame(upper_area, bg=self.colors["bg_surface"], bd=1, relief="solid")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_rowconfigure(1, weight=1) # Histogram expands
        right_panel.grid_columnconfigure(0, weight=1)

        # Stats Area (Top of Right Panel)
        stats_frame = tk.Frame(right_panel, bg=self.colors["bg_surface"], padx=15, pady=10)
        stats_frame.grid(row=0, column=0, sticky="ew")
        
        self.lbl_mean = tk.Label(stats_frame, text="Mean RGB: ( -, -, - )", font=("Consolas", 10, "bold"), 
                                 bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_mean.pack(fill="x", pady=1)
        
        self.lbl_unique = tk.Label(stats_frame, text="Jumlah Warna Unik: -", font=("Consolas", 10), 
                                   bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_unique.pack(fill="x", pady=1)
        
        self.lbl_dominant = tk.Label(stats_frame, text="Warna Dominan: ( -, -, - )", font=("Consolas", 10), 
                                     bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_dominant.pack(fill="x", pady=1)
        
        # Description/Log View
        self.txt_desc = tk.Text(stats_frame, height=3, font=("Consolas", 8), bg=self.colors["bg_input"], 
                                fg=self.colors["fg_muted"], bd=0, padx=5, pady=4)
        self.txt_desc.pack(fill="x", pady=5)
        self.txt_desc.insert("1.0", "Detail analisis akan muncul di sini...")
        self.txt_desc.configure(state="disabled")

        # Dominant Color Preview Box
        self.dom_color_box = tk.Canvas(stats_frame, width=30, height=30, bg=self.colors["bg_input"], 
                                       highlightthickness=1, highlightbackground=self.colors["fg_muted"])
        self.dom_color_box.pack(pady=3)

        # Histogram Area (Middle of Right Panel)
        hist_frame = tk.LabelFrame(right_panel, text=" Histogram RGB (ROI) ", font=("Arial", 11, "bold"),
                                   bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], padx=10, pady=5)
        hist_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        
        self.hist_canvas = tk.Canvas(hist_frame, bg="#FFFFFF", highlightthickness=0)
        self.hist_canvas.pack(fill="both", expand=True)

        # Toggle frame inside hist frame
        toggle_frame = tk.Frame(hist_frame, bg=self.colors["bg_surface"])
        toggle_frame.pack(fill="x", pady=(5, 0))
        
        for c_text, c_var, c_color in [("Red", self.show_r, "#E74C3C"), ("Green", self.show_g, "#27AE60"), ("Blue", self.show_b, "#4FA3FF")]:
            tk.Checkbutton(toggle_frame, text=c_text, variable=c_var, 
                           bg=self.colors["bg_surface"], fg=c_color, selectcolor=self.colors["bg_input"],
                           activebackground=self.colors["bg_surface"], activeforeground=c_color,
                           font=("Arial", 9, "bold")).pack(side="left", expand=True)

        # ── Global Bottom Button Row ──
        btn_row = tk.Frame(main_vbox, bg=self.colors["bg_root"])
        btn_row.pack(fill="x", pady=(10, 0))
        
        self.btn_capture = tk.Button(btn_row, text="📸 Capture / Live", command=self.toggle_live,
                                     bg=self.colors["bg_button"], fg="white", font=("Arial", 10, "bold"), height=2)
        self.btn_capture.pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_open_file = tk.Button(btn_row, text="📂 Buka Gambar", command=self.open_local_file,
                                       bg="#16A085", fg="white", font=("Arial", 10, "bold"), height=2)
        self.btn_open_file.pack(side="left", fill="x", expand=True, padx=2)
        
        tk.Button(btn_row, text="💾 Simpan DB", command=self.save_to_database,
                  bg=self.colors["accent"], fg="white", font=("Arial", 10, "bold"), height=2).pack(side="left", fill="x", expand=True, padx=2)
        
        tk.Button(btn_row, text="📤 Export Excel", command=self.export_to_excel,
                  bg=self.colors["green"], fg="white", font=("Arial", 10, "bold"), height=2).pack(side="left", fill="x", expand=True, padx=2)
        
        tk.Button(btn_row, text="❌ Tutup", command=self.close,
                  bg=self.colors["red"], fg="white", font=("Arial", 10, "bold"), height=2).pack(side="left", fill="x", expand=True, padx=2)

        # History Table Area (Bottom)
        hist_table_frame = tk.LabelFrame(main_vbox, text=" Riwayat Analisis Warna (Database Supabase) ", 
                                         font=("Arial", 11, "bold"), bg=self.colors["bg_surface"], 
                                         fg=self.colors["fg_primary"], padx=10, pady=10)
        hist_table_frame.pack(fill="x", pady=(10, 0))
        
        columns = ("id", "created_at", "mean_rgb", "unique_colors", "dominant_rgb")
        self.tree = ttk.Treeview(hist_table_frame, columns=columns, show="headings", height=5)
        self.tree.heading("id", text="ID")
        self.tree.heading("created_at", text="Waktu")
        self.tree.heading("mean_rgb", text="Mean RGB")
        self.tree.heading("unique_colors", text="Warna Unik")
        self.tree.heading("dominant_rgb", text="Warna Dominan")
        
        self.tree.column("id", width=50, anchor="center")
        self.tree.column("created_at", width=150, anchor="center")
        self.tree.column("mean_rgb", width=150, anchor="center")
        self.tree.column("unique_colors", width=100, anchor="center")
        self.tree.column("dominant_rgb", width=150, anchor="center")
        
        self.tree.pack(side="left", fill="x", expand=True)
        
        sb = ttk.Scrollbar(hist_table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        apply_mixed_theme(self)

    # ── Database Helpers ──
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
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                if not raw.strip():
                    return []
                return json.loads(raw)
        except Exception as e:
            raise RuntimeError(f"Database error: {e}")

    def refresh_db_table(self):
        try:
            # Query columns sesuai dengan tabel analisis_gambar
            rows = self.supabase_request("GET", f"/rest/v1/{self.SUPABASE_TABLE}?select=*&order=created_at.desc&limit=50")
            for item in self.tree.get_children():
                self.tree.delete(item)
            for r in rows:
                mean_rgb = f"({r['mean_r']}, {r['mean_g']}, {r['mean_b']})"
                dom_rgb = f"({r['dominan_r']}, {r['dominan_g']}, {r['dominan_b']})"
                # Format timestamp created_at
                ts = r.get("created_at", "").replace("T", " ").split(".")[0]
                self.tree.insert("", "end", values=(r["id"], ts, mean_rgb, r["jumlah_warna_unik"], dom_rgb))
        except Exception as e:
            print(f"Error refresh table: {e}")

    def save_to_database(self):
        if not self.last_stats:
            messagebox.showwarning("Peringatan", "Belum ada data untuk disimpan.")
            return
        
        try:
            # Map data sesuai dengan tabel_analisis_gambar.md
            payload = {
                "mean_r": float(self.last_stats["Mean_R"]),
                "mean_g": float(self.last_stats["Mean_G"]),
                "mean_b": float(self.last_stats["Mean_B"]),
                "jumlah_warna_unik": int(self.last_stats["Unique_Colors"]),
                "dominan_r": int(self.last_stats["Dominant_R"]),
                "dominan_g": int(self.last_stats["Dominant_G"]),
                "dominan_b": int(self.last_stats["Dominant_B"])
                # created_at diisi default now() oleh database
            }
            self.supabase_request("POST", f"/rest/v1/{self.SUPABASE_TABLE}", payload)
            self.refresh_db_table()
            messagebox.showinfo("Sukses", "Data berhasil disimpan ke database Supabase!")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal simpan ke database: {e}\n\nPastikan tabel '{self.SUPABASE_TABLE}' sudah dibuat di Supabase sesuai schema.")

    # ── Camera & Analysis ──
    def start_camera(self):
        try:
            source = 0 if self.use_internal else self.camera_url
            self.camera = cv2.VideoCapture(source)
            if not self.camera.isOpened():
                raise Exception("Kamera tidak terbuka")
            self.is_running = True
            self.update_loop()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka kamera: {e}")
            self.close()

    def toggle_live(self):
        self.is_live = not self.is_live
        self.is_file_mode = False # Clear file mode if toggling live
        if self.is_live:
            self.btn_capture.configure(bg=self.colors["bg_button"], text="📸 Capture Image")
        else:
            self.btn_capture.configure(bg=self.colors["yellow"], text="▶ Resume Live")
            self.captured_frame = self.current_frame.copy() if self.current_frame is not None else None

    def open_local_file(self):
        initial = self.drive_folder if os.path.isdir(self.drive_folder) else os.getcwd()
        path = filedialog.askopenfilename(
            initialdir=initial,
            title="Pilih Gambar",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")]
        )
        if path:
            try:
                # Load with PIL for better compatibility then convert to OpenCV BGR
                img_pil = Image.open(path).convert("RGB")
                img_np = np.array(img_pil)
                self.file_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                self.is_live = False
                self.is_file_mode = True
                self.btn_capture.configure(bg=self.colors["yellow"], text="▶ Resume Live")
                # Trigger analysis once
                self.process_and_display(self.file_frame)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka file: {e}")

    def update_loop(self):
        if not self.is_running:
            return
        
        frame_to_process = None
        if self.is_live:
            ret, frame = self.camera.read()
            if ret:
                self.current_frame = frame
                frame_to_process = frame
        elif self.is_file_mode:
            frame_to_process = self.file_frame
        else:
            frame_to_process = self.captured_frame
            
        if frame_to_process is not None:
            self.process_and_display(frame_to_process)
            
        self.after(30, self.update_loop)

    def process_and_display(self, frame):
        if frame is None: return
        disp_frame = frame.copy()
        h, w = disp_frame.shape[:2]
        
        roi_sz = self.roi_size.get()
        cx, cy = w // 2, h // 2
        x1, y1 = max(0, cx - roi_sz // 2), max(0, cy - roi_sz // 2)
        x2, y2 = min(w, cx + roi_sz // 2), min(h, cy + roi_sz // 2)
        
        cv2.rectangle(disp_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        roi = frame[y1:y2, x1:x2]
        if roi.size > 0:
            self.analyze_roi(roi)
        
        target_w = self.video_wrap.winfo_width()
        target_h = self.video_wrap.winfo_height()
        if target_w < 50: target_w, target_h = 760, 428 # Default size from profile
        
        rgb = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
        rendered = self._resize_cover(rgb, target_w, target_h)
        img = Image.fromarray(rendered)
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

    def analyze_roi(self, roi):
        mean_bgr = cv2.mean(roi)[:3]
        mean_rgb = (round(mean_bgr[2], 2), round(mean_bgr[1], 2), round(mean_bgr[0], 2))
        self.lbl_mean.configure(text=f"Mean RGB: {mean_rgb}")
        
        pixels = roi.reshape(-1, 3)
        unique_colors_cnt = len(np.unique(pixels, axis=0))
        self.lbl_unique.configure(text=f"Jumlah Warna Unik: {unique_colors_cnt}")
        
        # Dominant
        quantized = (pixels // 16) * 16
        from collections import Counter
        pixel_strings = [f"{p[0]}-{p[1]}-{p[2]}" for p in quantized]
        counts = Counter(pixel_strings)
        dom_str = counts.most_common(1)[0][0]
        db, dg, dr = [int(v) for v in dom_str.split('-')]
        dom_rgb = (dr, dg, db)
        self.lbl_dominant.configure(text=f"Warna Dominan: {dom_rgb}")
        
        hx = '#{:02x}{:02x}{:02x}'.format(*dom_rgb)
        self.dom_color_box.configure(bg=hx)
        
        self.last_stats = {
            "Mean_R": mean_rgb[0], "Mean_G": mean_rgb[1], "Mean_B": mean_rgb[2],
            "Unique_Colors": unique_colors_cnt,
            "Dominant_R": dom_rgb[0], "Dominant_G": dom_rgb[1], "Dominant_B": dom_rgb[2]
        }
        
        # Update Description
        desc = (f"STATISTIK ROI ({roi.shape[1]}x{roi.shape[0]} px):\n"
                f"- Rerata Intensitas: R={mean_rgb[0]}, G={mean_rgb[1]}, B={mean_rgb[2]}\n"
                f"- Variasi Warna: Terdeteksi {unique_colors_cnt} kombinasi warna unik.\n"
                f"- Dominansi: Warna hex {hx} paling sering muncul di area pusat.")
        self.txt_desc.configure(state="normal")
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", desc)
        self.txt_desc.configure(state="disabled")
        
        self.draw_histogram(roi)

    def draw_histogram(self, roi):
        self.hist_canvas.update_idletasks()
        w = self.hist_canvas.winfo_width()
        h = self.hist_canvas.winfo_height()
        if w < 10 or h < 10: return
        self.hist_canvas.delete("all")

        # Layout margins for axes
        left_m = 48
        right_m = 10
        top_m = 28
        bottom_m = 28
        plot_w = w - left_m - right_m
        plot_h = h - top_m - bottom_m

        # Background
        self.hist_canvas.create_rectangle(left_m, top_m, w - right_m, h - bottom_m,
                                          fill="#1a2a40", outline="#3a5a80", width=1)

        # Channel info: (cv index, color hex, name)
        channels_info = [
            (0, '#4FA3FF', 'Blue'),
            (1, '#27AE60', 'Green'),
            (2, '#E74C3C', 'Red'),
        ]
        show_flags = [self.show_b.get(), self.show_g.get(), self.show_r.get()]

        # Compute raw histograms for peak detection
        raw_hists = []
        for ch_i, color, name in channels_info:
            hist = cv2.calcHist([roi], [ch_i], None, [256], [0, 256]).flatten()
            raw_hists.append((hist, color, name))

        # Find global max for consistent Y scaling
        active_hists = [h for i, (h, c, n) in enumerate(raw_hists) if show_flags[i]]
        if not active_hists:
            return
        global_max = max(float(np.max(h)) for h in active_hists)
        if global_max <= 0:
            global_max = 1.0

        # ── Gridlines & Y-axis labels ──
        y_ticks = 4
        for ti in range(y_ticks + 1):
            frac = ti / y_ticks
            gy = top_m + plot_h - int(frac * plot_h)
            val = int(frac * global_max)
            # Dashed gridline
            if 0 < ti < y_ticks:
                for gx in range(left_m, w - right_m, 6):
                    self.hist_canvas.create_line(gx, gy, min(gx + 3, w - right_m), gy,
                                                 fill="#304060", width=1)
            # Tick + label
            self.hist_canvas.create_line(left_m - 4, gy, left_m, gy, fill="#8aabcc", width=1)
            label = f"{val // 1000}k" if val >= 1000 else str(val)
            self.hist_canvas.create_text(left_m - 6, gy, text=label,
                                         anchor="e", fill="#8aabcc", font=("Consolas", 8))

        # ── X-axis labels ──
        x_ticks = [0, 64, 128, 192, 255]
        for xv in x_ticks:
            px = left_m + int(xv / 255.0 * plot_w)
            self.hist_canvas.create_line(px, h - bottom_m, px, h - bottom_m + 4, fill="#8aabcc", width=1)
            self.hist_canvas.create_text(px, h - bottom_m + 12, text=str(xv),
                                         anchor="center", fill="#8aabcc", font=("Consolas", 8))
            # Dashed vertical gridline
            if 0 < xv < 255:
                for gy in range(top_m, h - bottom_m, 6):
                    self.hist_canvas.create_line(px, gy, px, min(gy + 3, h - bottom_m),
                                                 fill="#304060", width=1)

        # ── Draw histogram lines + peak markers ──
        peak_label_y = top_m - 10
        for idx, (hist_data, color, name) in enumerate(raw_hists):
            if not show_flags[idx]:
                continue

            # Draw line
            points = []
            for x in range(256):
                px = left_m + int(x / 255.0 * plot_w)
                py = top_m + plot_h - int((hist_data[x] / global_max) * plot_h)
                py = max(top_m, min(top_m + plot_h, py))
                points.append((px, py))
            for j in range(len(points) - 1):
                self.hist_canvas.create_line(
                    points[j][0], points[j][1],
                    points[j + 1][0], points[j + 1][1],
                    fill=color, width=2
                )

            # Peak dot marker on the chart line
            peak_idx = int(np.argmax(hist_data))
            peak_val = int(hist_data[peak_idx])
            peak_px = left_m + int(peak_idx / 255.0 * plot_w)
            peak_py = top_m + plot_h - int((hist_data[peak_idx] / global_max) * plot_h)
            peak_py = max(top_m, min(top_m + plot_h, peak_py))

            # Filled circle at peak point
            # Filled circle at peak point
            self.hist_canvas.create_oval(peak_px - 4, peak_py - 4, peak_px + 4, peak_py + 4,
                                          fill=color, outline="white", width=1)

            # Value label with slight vertical offset based on channel to avoid overlap
            label_x = peak_px + 7
            label_y = peak_py - 5
            
            # Offset labels based on name to help prevent overlap
            if name == "Red": label_y -= 10
            if name == "Blue": label_y += 10
            
            # Keep label within bounds
            if label_x + 30 > w - right_m:
                label_x = peak_px - 35
            if label_y < top_m + 8:
                label_y = peak_py + 12
            if label_y > h - bottom_m - 8:
                label_y = peak_py - 12
                
            self.hist_canvas.create_text(label_x, label_y, text=f"{name[0]}:{peak_idx}",
                                         anchor="w", fill=color, font=("Consolas", 9, "bold"))


    def export_to_excel(self):
        if not self.last_stats: return
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                                filetypes=[("Excel files", "*.xlsx")],
                                                initialfile=f"Warna_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if not filepath: return
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Analisis Warna"
            # Header
            headers = ["Waktu", "Mean_R", "Mean_G", "Mean_B", "Unique_Colors", "Dom_R", "Dom_G", "Dom_B"]
            ws.append(headers)
            # Data row
            ws.append([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.last_stats["Mean_R"],
                self.last_stats["Mean_G"],
                self.last_stats["Mean_B"],
                self.last_stats["Unique_Colors"],
                self.last_stats["Dominant_R"],
                self.last_stats["Dominant_G"],
                self.last_stats["Dominant_B"],
            ])
            wb.save(filepath)
            messagebox.showinfo("Sukses", f"Export berhasil ke {filepath}")
        except ImportError:
            messagebox.showerror("Error", "Module 'openpyxl' tidak ditemukan.\nJalankan: pip install openpyxl")
        except Exception as e:
            messagebox.showerror("Error", str(e))

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

    def close(self):
        self.is_running = False
        if self.camera: self.camera.release()
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AnalisisWarnaWindow(root, "hasil", use_internal=True)
    root.mainloop()
