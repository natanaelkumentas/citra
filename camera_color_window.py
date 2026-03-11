import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import cv2
import os
from datetime import datetime
import numpy as np
import json


class CameraColorWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.camera = None
        self.is_running = False
        self.captured_frame = None
        self.is_frozen = False  # flag untuk freeze capture

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

        self.title("Window Kamera Warna - Deteksi Warna")
        self.geometry("1200x700")
        self.configure(bg=self.colors["bg_root"])
        try:
            self.state("zoomed")
        except:
            pass

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
        root = tk.Frame(self, bg=self.colors["bg_root"])
        root.pack(fill="both", expand=True, padx=12, pady=12)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)

        # ── Header ──
        header = tk.Frame(root, bg=self.colors["bg_root"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tk.Label(header, text="KAMERA WARNA – DETEKSI WARNA REAL-TIME", font=("Segoe UI", 16, "bold"),
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

        # ── Main Area (Horizontal Middle) ──
        main = tk.Frame(root, bg=self.colors["bg_main"])
        main.grid(row=1, column=0, sticky="nsew")
        main.grid_rowconfigure(0, weight=1) # main_middle takes most space
        main.grid_rowconfigure(1, weight=0) # info_log_label
        main.grid_rowconfigure(2, weight=0) # button_row
        main.grid_columnconfigure(0, weight=1)

        main_middle = tk.Frame(main, bg=self.colors["bg_main"])
        main_middle.grid(row=0, column=0, sticky="nsew", pady=(8, 4))
        main_middle.grid_rowconfigure(0, weight=1)
        main_middle.grid_columnconfigure(0, weight=3) # Camera wider
        main_middle.grid_columnconfigure(1, weight=2) # Color Detect Panel

        # ── LEFT: Kamera Live ──
        left_panel = tk.Frame(main_middle, bg=self.colors["bg_panel"], bd=1, relief="solid")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        self.camera_header_label = tk.Label(left_panel, text="KAMERA LIVE (DETEKSI WARNA)",
                                            font=("Segoe UI", 11, "bold"),
                                            bg=self.colors["bg_panel_inner"], fg=self.colors["accent_blue"],
                                            pady=8)
        self.camera_header_label.grid(row=0, column=0, sticky="ew")

        self.live_label = tk.Label(left_panel, bg="#000000", text="Memuat kamera...", fg="white")
        self.live_label.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.live_label.bind("<Configure>", self._on_resize)
        
        # Draw a little help text at the bottom of left panel
        tk.Label(left_panel, text="ROI (Region of Interest) ditandai dengan kotak merah di tengah",
                 font=("Segoe UI", 8, "italic"), bg=self.colors["bg_panel"], fg=self.colors["fg_muted"]).grid(row=2, column=0, pady=4)

        # ── RIGHT: Deteksi Warna ──
        right_panel = tk.Frame(main_middle, bg=self.colors["bg_panel"], bd=1, relief="solid")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        tk.Label(right_panel, text="DETEKSI WARNA", font=("Segoe UI", 11, "bold"),
                 bg=self.colors["bg_panel_inner"], fg=self.colors["fg_primary"],
                 pady=8).grid(row=0, column=0, sticky="ew")

        self.color_panel_container = tk.Frame(right_panel, bg=self.colors["bg_panel"])
        self.color_panel_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.color_panel_container.grid_columnconfigure(0, weight=1)

        # Info Log
        self.info_log_label = tk.Label(main, text="", font=("Segoe UI", 10, "bold"),
                                       bg=self.colors["bg_main"], fg=self.colors["accent_green"])
        self.info_log_label.grid(row=1, column=0, sticky="ew", pady=2)

        # ── Bottom Action Buttons ──
        button_row = tk.Frame(main, bg=self.colors["bg_main"])
        button_row.grid(row=2, column=0, sticky="ew", pady=(4, 8))
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
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=2, padx=5, sticky="ew", ipady=6)

        tk.Button(button_row, text="Tutup Halaman", command=self.close,
                  font=("Segoe UI", 11, "bold"), bg=self.colors["bg_panel"], fg="white", activebackground="#26517F", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2").grid(row=0, column=3, padx=(5, 0), sticky="ew", ipady=6)

        # Fill color panels
        for cn, ci in self.color_ranges.items():
            self.create_color_panel(self.color_panel_container, cn, ci['rgb'])

    def create_color_panel(self, parent, color_name, rgb_color):
        """Create a clean, evenly-spaced color detection row"""
        panel_frame = tk.Frame(parent, bg=self.colors["bg_panel_inner"], relief="flat", bd=0)
        panel_frame.pack(pady=1, fill="x", ipady=3)

        # Inner row with padding
        inner = tk.Frame(panel_frame, bg=self.colors["bg_panel_inner"])
        inner.pack(fill="x", padx=10)

        name_label = tk.Label(inner, text=color_name,
                              font=("Segoe UI", 10, "bold"), bg=self.colors["bg_panel_inner"],
                              fg=self.colors["fg_primary"], anchor="w")
        name_label.pack(side="left", pady=1)

        color_canvas = tk.Canvas(inner, width=50, height=18,
                                 bg=self.colors["bg_panel_inner"], highlightthickness=0)
        color_canvas.pack(side="right", pady=1)
        rect = color_canvas.create_rectangle(1, 1, 49, 17, fill=self.colors["bg_panel_inner"],
                                             outline="#4A6A8A", width=1)
        self.color_panels[color_name] = {
            'canvas': color_canvas, 'rect': rect,
            'rgb': rgb_color, 'name_label': name_label
        }

    # ── kamera ──
    def start_camera(self):
        try:
            self.show_log("🔄 Menghubungkan ke Kamera...", "#3498DB")
            self.camera = cv2.VideoCapture(0 if self.use_internal else self.camera_url)
            if self.use_internal and not self.camera.isOpened():
                self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            
            if not self.use_internal:
                try:
                    target = self.camera_url
                    if hasattr(target, 'isdigit') and target.isdigit():
                        target = int(target)
                        self.camera.release()
                        self.camera = cv2.VideoCapture(target)
                except: pass

            try:
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except: pass

            if not self.camera.isOpened():
                raise Exception("Tidak dapat terhubung ke Kamera")
            self.is_running = True
            self.show_log("✅ Terhubung ke Kamera!", "#2ECC71")
            # Ensure window is ready before starting loop
            self.update_idletasks()
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
        Kalau is_frozen=True, tampilkan captured_frame (freeze), jangan update.
        """
        if not self.is_running or self.camera is None:
            return

        # Jika frozen (sudah capture), tampilkan gambar diam
        if self.is_frozen and self.captured_frame is not None:
            self.after(100, self.update_camera)  # tetap loop tapi tidak update display
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

                # gambar ROI pada display_frame
                h, w = display_frame.shape[:2]
                roi_size = 100
                cx, cy = w // 2, h // 2
                rx1, ry1 = cx - roi_size // 2, cy - roi_size // 2
                rx2, ry2 = cx + roi_size // 2, cy + roi_size // 2
                disp_with_rect = display_frame.copy()
                cv2.rectangle(disp_with_rect, (rx1, ry1), (rx2, ry2), (0, 0, 255), 3)

                # ROI untuk deteksi
                roi = display_frame[ry1:ry2, rx1:rx2]
                detected = self.detect_color_in_roi(roi)
                self.update_color_panels(detected)

                # resize untuk tampilan
                target_w = max(1, self.live_label.winfo_width())
                target_h = max(1, self.live_label.winfo_height())
                if target_w < 10 or target_h < 10:
                    self.after(33, self.update_camera)
                    return

                rgb = cv2.cvtColor(disp_with_rect, cv2.COLOR_BGR2RGB)
                rendered = self._resize_cover(rgb, target_w, target_h)

                photo = ImageTk.PhotoImage(Image.fromarray(rendered))
                self.live_label.configure(image=photo, text="")
                self.live_label.image = photo
            self.after(33, self.update_camera)
        except Exception as e:
            print(f"Error updating camera: {e}")
            self.is_running = False

    def detect_color_in_roi(self, roi):
        if roi.size == 0:
            return None
        try:
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        except Exception:
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
            
            # hitung persentase warna
            count = cv2.countNonZero(mask)
            total = max(1, roi.shape[0] * roi.shape[1])
            pct = (count / total) * 100
            color_pct[cn] = pct
        return color_pct

    def update_color_panels(self, detected_colors):
        if not detected_colors:
            return
        for cn, pct in detected_colors.items():
            if cn in self.color_panels:
                panel = self.color_panels[cn]
                # Jika terdeteksi signifikan (> 5%) munculkan warna aslinya
                if pct > 5.0:
                    r, g, b = panel['rgb']
                    hex_color = '#{:02x}{:02x}{:02x}'.format(r, g, b)
                    panel['name_label'].configure(fg=self.colors["accent_green"])
                    panel['canvas'].itemconfig(panel['rect'], fill=hex_color, outline="white", width=2)
                else:
                    hex_color = self.colors["bg_panel_inner"]
                    panel['name_label'].configure(fg=self.colors["fg_primary"])
                    panel['canvas'].itemconfig(panel['rect'], fill=hex_color, outline="#4A6A8A", width=1)

    def capture_image(self):
        """Capture: freeze frame dan tampilkan gambar diam"""
        if self.camera is None or not self.camera.isOpened():
            self.show_log("⚠️ Kamera tidak aktif!", "#E67E22")
            return
        try:
            ret, frame = self.camera.read()
            if ret:
                # normalisasi ke BGR
                if frame.ndim == 2:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                elif frame.ndim == 3 and frame.shape[2] == 4:
                    bgr_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                else:
                    bgr_frame = frame.copy()

                self.captured_frame = bgr_frame
                self.is_frozen = True

                # Tampilkan gambar frozen di live_label
                self._display_frozen_frame()

                # Update header status
                self.camera_header_label.configure(text="📷 CAPTURED (Diam)", fg="#F39C12")

                self.show_log("✅ Gambar di-capture! Kamera ter-freeze. Klik Hapus untuk kembali ke live.", "#2ECC71")
            else:
                self.show_log("❌ Gagal mengambil gambar", "#E74C3C")
        except Exception as e:
            self.show_log(f"❌ Error: {e}", "#E74C3C")

    def _display_frozen_frame(self):
        """Tampilkan captured frame di live_label (frozen/diam)"""
        if self.captured_frame is None:
            return
        frame = self.captured_frame.copy()
        h, w = frame.shape[:2]
        roi_size = 100
        cx, cy = w // 2, h // 2
        rx1, ry1 = cx - roi_size // 2, cy - roi_size // 2
        rx2, ry2 = cx + roi_size // 2, cy + roi_size // 2
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 0, 255), 3)

        # Tambah overlay text "CAPTURED"
        cv2.putText(frame, "CAPTURED", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        target_w = max(1, self.live_label.winfo_width())
        target_h = max(1, self.live_label.winfo_height())
        if target_w < 10 or target_h < 10:
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rendered = self._resize_contain(rgb, target_w, target_h)
        photo = ImageTk.PhotoImage(Image.fromarray(rendered))
        self.live_label.configure(image=photo, text="")
        self.live_label.image = photo





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
        """Hapus capture dan kembali ke live camera"""
        if self.captured_frame is None and not self.is_frozen:
            self.show_log("ℹ️ Tidak ada capture untuk dihapus", "#3498DB")
            return
        self.captured_frame = None
        self.is_frozen = False

        # Reset header
        self.camera_header_label.configure(text="KAMERA LIVE (DETEKSI WARNA)", fg=self.colors["accent_blue"])

        self.show_log("✅ Capture dihapus! Kembali ke live camera.", "#2ECC71")

    def show_log(self, message, color="#2ECC71"):
        self.info_log_label.configure(text=message, fg=color)
        self.after(5000, lambda: self.info_log_label.configure(text=""))

    def reconnect_camera(self):
        self.is_running = False
        self.is_frozen = False
        self.captured_frame = None
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
        self.camera_header_label.configure(text="KAMERA LIVE (DETEKSI WARNA)", fg=self.colors["accent_blue"])
        self.after(500, self.start_camera)

    def close(self):
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
        self.destroy()

    def _on_resize(self, event):
        """Placeholder for resize event"""
        pass

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

if __name__ == "__main__":
    import tkinter as tk
    root = tk.Tk()
    app = CameraColorWindow(root, "./")
    root.mainloop()
