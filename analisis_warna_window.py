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
        
        # Upper Area: Left (Camera) and Right (Stats/Hist)
        upper_area = tk.Frame(main_vbox, bg=self.colors["bg_root"])
        upper_area.pack(fill="both", expand=True)
        
        # Left Panel: Live View
        left_panel = tk.Frame(upper_area, bg=self.colors["bg_surface"], bd=1, relief="solid")
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        header_l = tk.Frame(left_panel, bg=self.colors["bg_surface"])
        header_l.pack(fill="x", pady=10)
        tk.Label(header_l, text="LIVE CAMERA CAPTURE", font=("Arial", 14, "bold"),
                 bg=self.colors["bg_surface"], fg=self.colors["accent"]).pack()
        
        # Video Wrapper (Fixed size to prevent growing madness)
        self.video_wrap = tk.Frame(left_panel, bg="#000000")
        self.video_wrap.pack(fill="both", expand=True, padx=10, pady=5)
        self.video_wrap.pack_propagate(False)
        
        self.video_label = tk.Label(self.video_wrap, bg="#000000")
        self.video_label.pack(fill="both", expand=True)
        
        # ROI Size Control
        ctrl_frame = tk.Frame(left_panel, bg=self.colors["bg_surface"])
        ctrl_frame.pack(fill="x", padx=10, pady=10)
        tk.Label(ctrl_frame, text="Ukuran ROI:", bg=self.colors["bg_surface"], fg=self.colors["fg_primary"]).pack(side="left", padx=5)
        self.roi_slider = tk.Scale(ctrl_frame, from_=50, to=400, orient="horizontal", 
                                   variable=self.roi_size, bg=self.colors["bg_surface"], 
                                   fg=self.colors["fg_primary"], highlightthickness=0,
                                   troughcolor=self.colors["bg_input"], activebackground=self.colors["accent"])
        self.roi_slider.pack(side="left", fill="x", expand=True, padx=5)

        # Right Panel: Analysis & Stats
        right_panel = tk.Frame(upper_area, bg=self.colors["bg_surface"], width=480, bd=1, relief="solid")
        right_panel.pack(side="right", fill="both", padx=(10, 0))
        right_panel.pack_propagate(False)

        # Stats Area (Top of Right Panel)
        stats_frame = tk.Frame(right_panel, bg=self.colors["bg_surface"], padx=15, pady=10)
        stats_frame.pack(fill="x")
        
        self.lbl_mean = tk.Label(stats_frame, text="Mean RGB: ( -, -, - )", font=("Consolas", 11, "bold"), 
                                 bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_mean.pack(fill="x", pady=2)
        
        self.lbl_unique = tk.Label(stats_frame, text="Jumlah Warna Unik: -", font=("Consolas", 11), 
                                   bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_unique.pack(fill="x", pady=2)
        
        self.lbl_dominant = tk.Label(stats_frame, text="Warna Dominan: ( -, -, - )", font=("Consolas", 11), 
                                     bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], anchor="w")
        self.lbl_dominant.pack(fill="x", pady=2)
        
        # Description/Log View
        self.txt_desc = tk.Text(stats_frame, height=4, font=("Consolas", 9), bg=self.colors["bg_input"], 
                                fg=self.colors["fg_muted"], bd=0, padx=5, pady=5)
        self.txt_desc.pack(fill="x", pady=5)
        self.txt_desc.insert("1.0", "Detail analisis akan muncul di sini...")
        self.txt_desc.configure(state="disabled")

        # Dominant Color Preview Box
        self.dom_color_box = tk.Canvas(stats_frame, width=60, height=60, bg=self.colors["bg_input"], 
                                       highlightthickness=1, highlightbackground=self.colors["fg_muted"])
        self.dom_color_box.pack(pady=5)

        # Histogram Area (Middle of Right Panel)
        hist_frame = tk.LabelFrame(right_panel, text=" Histogram RGB (ROI) ", font=("Arial", 11, "bold"),
                                   bg=self.colors["bg_surface"], fg=self.colors["fg_primary"], padx=10, pady=5)
        hist_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.hist_canvas = tk.Canvas(hist_frame, bg="#FFFFFF", highlightthickness=0)
        self.hist_canvas.pack(fill="both", expand=True)

        # Histogram Toggle Buttons
        toggle_frame = tk.Frame(hist_frame, bg=self.colors["bg_surface"])
        toggle_frame.pack(fill="x", pady=(5, 0))
        
        tk.Checkbutton(toggle_frame, text="Red", variable=self.show_r, 
                       bg=self.colors["bg_surface"], fg="#E74C3C", selectcolor=self.colors["bg_input"],
                       activebackground=self.colors["bg_surface"], activeforeground="#E74C3C",
                       font=("Arial", 9, "bold")).pack(side="left", expand=True)
        tk.Checkbutton(toggle_frame, text="Green", variable=self.show_g, 
                       bg=self.colors["bg_surface"], fg="#27AE60", selectcolor=self.colors["bg_input"],
                       activebackground=self.colors["bg_surface"], activeforeground="#27AE60",
                       font=("Arial", 9, "bold")).pack(side="left", expand=True)
        tk.Checkbutton(toggle_frame, text="Blue", variable=self.show_b, 
                       bg=self.colors["bg_surface"], fg="#4FA3FF", selectcolor=self.colors["bg_input"],
                       activebackground=self.colors["bg_surface"], activeforeground="#4FA3FF",
                       font=("Arial", 9, "bold")).pack(side="left", expand=True)

        # Action Buttons (Bottom of Right Panel)
        btn_frame = tk.Frame(right_panel, bg=self.colors["bg_surface"])
        btn_frame.pack(fill="x", padx=15, pady=15)
        
        self.btn_capture = tk.Button(btn_frame, text="📸 Capture / Live", command=self.toggle_live,
                                     bg=self.colors["bg_button"], fg="white", font=("Arial", 10, "bold"), height=2)
        self.btn_capture.pack(fill="x", pady=2)
        
        self.btn_open_file = tk.Button(btn_frame, text="📂 Buka Gambar Lokal", command=self.open_local_file,
                                       bg="#16A085", fg="white", font=("Arial", 10, "bold"), height=2)
        self.btn_open_file.pack(fill="x", pady=2)
        
        db_exp_frame = tk.Frame(btn_frame, bg=self.colors["bg_surface"])
        db_exp_frame.pack(fill="x", pady=2)
        
        tk.Button(db_exp_frame, text="💾 Simpan ke Database", command=self.save_to_database,
                  bg=self.colors["accent"], fg="white", font=("Arial", 9, "bold"), height=2).pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        tk.Button(db_exp_frame, text="📤 Export ke Excel", command=self.export_to_excel,
                  bg=self.colors["green"], fg="white", font=("Arial", 9, "bold"), height=2).pack(side="left", fill="x", expand=True, padx=(2, 0))
        
        tk.Button(btn_frame, text="❌ Tutup Halaman", command=self.close,
                  bg=self.colors["red"], fg="white", font=("Arial", 10, "bold"), height=2).pack(fill="x", pady=2)

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
        rendered = resize_cover_rgb(rgb, target_w, target_h)
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
        if w < 10: return
        self.hist_canvas.delete("all")
        
        # opencv bgr -> indices are 0:B, 1:G, 2:R
        # colors for drawing (matching line_colors)
        line_colors = ['#4FA3FF', '#27AE60', '#E74C3C'] # Blue, Green, Red
        show_flags = [self.show_b.get(), self.show_g.get(), self.show_r.get()]
        
        for i in range(3):
            if not show_flags[i]:
                continue
                
            hist = cv2.calcHist([roi], [i], None, [256], [0, 256])
            cv2.normalize(hist, hist, 0, h - 10, cv2.NORM_MINMAX)
            points = []
            for x, y in enumerate(hist):
                px = (x / 255.0) * (w - 10) + 5
                py = h - 5 - y[0]
                points.append((px, py))
            for j in range(len(points) - 1):
                self.hist_canvas.create_line(points[j][0], points[j][1], points[j+1][0], points[j+1][1], 
                                             fill=line_colors[i], width=2)

    def export_to_excel(self):
        if not self.last_stats: return
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", 
                                                filetypes=[("Excel files", "*.xlsx")],
                                                initialfile=f"Warna_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if not filepath: return
        try:
            df = pd.DataFrame([{
                "Waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Mean_R": self.last_stats["Mean_R"], "Mean_G": self.last_stats["Mean_G"], "Mean_B": self.last_stats["Mean_B"],
                "Unique_Colors": self.last_stats["Unique_Colors"],
                "Dom_R": self.last_stats["Dominant_R"], "Dom_G": self.last_stats["Dominant_G"], "Dom_B": self.last_stats["Dominant_B"]
            }])
            df.to_excel(filepath, index=False)
            messagebox.showinfo("Sukses", f"Export berhasil ke {filepath}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def close(self):
        self.is_running = False
        if self.camera: self.camera.release()
        self.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AnalisisWarnaWindow(root, "hasil", use_internal=True)
    root.mainloop()
