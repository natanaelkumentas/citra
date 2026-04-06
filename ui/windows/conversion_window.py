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
import urllib.parse
import zipfile
from xml.sax.saxutils import escape as xml_escape
from utils.image_utils import detect_image_type, format_file_size, estimate_image_bytes

from services import camera_service, conversion_service

class ConversionWindow(tk.Toplevel):
    """
    FINAL:
    - gray_to_biner  → LIVE GRAYSCALE
    - Info: Jenis, Ukuran, Type (REAL-TIME)
    - Tombol baru: Buka Drive Lokal, Invert, Resume Live
    - Tambahan: Analisis jumlah objek & jumlah orang setelah capture/convert
    """

    MODE_LABELS = {
        'rgb_to_gray':   ("RGB → Grayscale", "Ubah ke Grayscale"),
        'gray_to_biner': ("Grayscale → Biner (B/W)", "Ubah ke Biner")
    }

    def __init__(self, parent, drive_folder, conv_mode,
                 use_internal=False, camera_url=None):
        super().__init__(parent)

        self.drive_folder = drive_folder
        self.conv_mode = conv_mode
        self.use_internal = use_internal
        self.camera_url = camera_url or "http://172.29.241.86:8081/video"

        self.camera = None
        self.is_running = False

        # frames sebagai numpy arrays (OpenCV)
        self.gray_frame = None        # selalu menyimpan versi grayscale dari sumber
        self.converted_frame = None   # hasil konversi (grayscale atau binary)
        self.selected_source_bgr = None  # jika memilih file: simpan BGR asli
        self.inverted = False

        # hasil analisis
        self.objects_bboxes = []  # list of (x,y,w,h) untuk objek
        self.people_bboxes = []   # list of (x,y,w,h) untuk orang
        self.face_bboxes = []     # list of (x,y,w,h) untuk wajah (face detection)
        
        # face detector - safe load agar tidak spam error file cascade tidak ada
        self.face_cascade = self._load_cascade('haarcascade_frontalface_default.xml')
        self.face_alt_cascade = self._load_cascade('haarcascade_frontalface_alt2.xml')
        self.eye_cascade = self._load_cascade('haarcascade_eye.xml')
        self.nose_cascade = self._load_cascade('haarcascade_mcs_nose.xml')

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
            "accent_orange": "#F2994A",
            "accent_purple": "#9B59B6"
        }

        self.title(f"Konversi Citra — {self.MODE_LABELS[conv_mode][0]}")
        self.geometry("1150x700")
        self.configure(bg=self.colors["bg_root"])
        try:
            self.state("zoomed")
        except:
            pass

        self.setup_ui()
        self.start_camera()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ───────────────── UI ─────────────────
    def setup_ui(self):
        bg = self.colors["bg_root"]
        main_bg = self.colors["bg_main"]
        panel = self.colors["bg_panel"]
        inner = self.colors["bg_panel_inner"]
        fg = self.colors["fg_primary"]
        muted = self.colors["fg_muted"]

        main = tk.Frame(self, bg=bg)
        main.pack(expand=True, fill="both", padx=12, pady=12)
        main.grid_rowconfigure(2, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # ── Header ──
        header = tk.Frame(main, bg=bg)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(header, text=f"KONVERSI CITRA — {self.MODE_LABELS[self.conv_mode][0]}",
                 font=("Segoe UI", 16, "bold"), bg=bg, fg=fg).pack(pady=(0,5))

        # ── Main Area (Grid seragam) ──
        body = tk.Frame(main, bg=main_bg, height=520)
        body.grid(row=1, column=0, sticky="nsew", pady=8)
        body.grid_propagate(False)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1, uniform="panel") # Kiri
        body.grid_columnconfigure(1, weight=1, uniform="panel") # Kanan

        # KIRI: Live Camera
        left = tk.Frame(body, bg=panel, bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)

        tk.Label(left, text="KAMERA LIVE", font=("Segoe UI", 11, "bold"),
                 bg=panel, fg=self.colors["accent_blue"]).pack(pady=8)

        self.live_wrap = tk.Frame(left, bg=inner, bd=1, relief="solid")
        self.live_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.live_wrap.pack_propagate(False)

        self.live_label = tk.Label(self.live_wrap, bg=inner, text="Menghubungkan...", fg=muted, font=("Segoe UI", 10))
        self.live_label.pack(expand=True, fill="both")

        # KANAN: Capture & Info
        right = tk.Frame(body, bg=panel, bd=1, relief="solid")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_propagate(False)

        tk.Label(right, text="HASIL CAPTURE", font=("Segoe UI", 11, "bold"),
                 bg=panel, fg=self.colors["accent_orange"]).pack(pady=8)

        self.capture_wrap = tk.Frame(right, bg=inner, bd=1, relief="solid")
        self.capture_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.capture_wrap.pack_propagate(False)
        
        self.capture_label = tk.Label(self.capture_wrap, bg=inner, text="Belum ada capture", fg=muted, font=("Segoe UI", 10))
        self.capture_label.pack(expand=True, fill="both")

        # INFO BAR & SLIDERS
        info_area = tk.Frame(main, bg=bg)
        info_area.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        
        info = tk.Frame(info_area, bg=panel, bd=1, relief="solid")
        info.pack(fill="x", pady=(0, 8), ipady=4)

        # Labels info dalam grid horizontal
        info_grid = tk.Frame(info, bg=panel)
        info_grid.pack(fill="x", padx=10, pady=5)
        for i in range(6):
            info_grid.grid_columnconfigure(i, weight=1)

        self.lbl_jenis = tk.Label(info_grid, text="Jenis   : -", bg=panel, fg=fg, anchor="w", font=("Segoe UI", 9))
        self.lbl_ukuran = tk.Label(info_grid, text="Ukuran  : -", bg=panel, fg=fg, anchor="w", font=("Segoe UI", 9))
        self.lbl_type = tk.Label(info_grid, text="Type    : -", bg=panel, fg=fg, anchor="w", font=("Segoe UI", 9))
        self.lbl_objects = tk.Label(info_grid, text="Objek   : -", bg=panel, fg=fg, anchor="w", font=("Segoe UI", 9))
        self.lbl_people = tk.Label(info_grid, text="Wajah   : -", bg=panel, fg=fg, anchor="w", font=("Segoe UI", 9))
        self.lbl_status = tk.Label(info_grid, text="Status  : -", bg=panel, fg=self.colors["accent_green"], anchor="w", font=("Segoe UI", 9, "bold"))
        
        self.lbl_jenis.grid(row=0, column=0, sticky="ew")
        self.lbl_ukuran.grid(row=0, column=1, sticky="ew")
        self.lbl_type.grid(row=0, column=2, sticky="ew")
        self.lbl_objects.grid(row=0, column=3, sticky="ew")
        self.lbl_people.grid(row=0, column=4, sticky="ew")
        self.lbl_status.grid(row=0, column=5, sticky="ew")

        # slider biner
        if self.conv_mode == "gray_to_biner":
            self.threshold = tk.IntVar(value=127)
            self.slider = tk.Scale(
                info, from_=0, to=255, orient="horizontal",
                variable=self.threshold,
                command=self.on_threshold,
                bg=panel, fg=fg, troughcolor=inner, highlightthickness=0, label="Atur Nilai Threshold"
            )
            self.slider.pack(fill="x", pady=2, padx=10)

        # Kumpulan Tombol Nav/Action
        btn = tk.Frame(info_area, bg=bg)
        btn.pack(pady=4)

        tk.Button(btn, text="📸 Capture", command=self.capture, bg="#2980b9", fg="white", activebackground="#2471a3", activeforeground="white", font=("Segoe UI", 10, "bold"), width=12, cursor="hand2", relief="raised", bd=1).pack(side="left", padx=4)
        tk.Button(btn, text=f"🔄 {self.MODE_LABELS[self.conv_mode][1]}", command=self.convert, bg="#E67E22", fg="white", activebackground="#D35400", activeforeground="white", font=("Segoe UI", 10, "bold"), width=18, cursor="hand2", relief="raised", bd=1).pack(side="left", padx=4)
        tk.Button(btn, text="💾 Simpan", command=self.save, bg="#27AE60", fg="white", activebackground="#239B56", activeforeground="white", font=("Segoe UI", 10, "bold"), width=12, cursor="hand2", relief="raised", bd=1).pack(side="left", padx=4)
        tk.Button(btn, text="🗑️ Hapus", command=self.delete_capture, bg="#E74C3C", fg="white", activebackground="#C0392B", activeforeground="white", font=("Segoe UI", 10, "bold"), width=12, cursor="hand2", relief="raised", bd=1).pack(side="left", padx=4)

        extra = tk.Frame(info_area, bg=bg)
        extra.pack(pady=4)
        tk.Button(extra, text="📂 Buka Lokal", command=self.open_local_image, bg="#16A085", fg="white", font=("Segoe UI", 9, "bold"), width=14, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="🔁 Invert", command=self.invert_image, bg="#9B59B6", fg="white", font=("Segoe UI", 9, "bold"), width=12, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="▶ Resume Live", command=self.resume_live, bg="#95A5A6", fg="white", font=("Segoe UI", 9, "bold"), width=14, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="👤 Crop Orang", command=self.crop_person, bg="#D35400", fg="white", font=("Segoe UI", 9, "bold"), width=14, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="🎭 Hapus BG", command=self.remove_background, bg="#C0392B", fg="white", font=("Segoe UI", 9, "bold"), width=12, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="↔️ Geser Orang", command=self.move_person, bg="#8E44AD", fg="white", font=("Segoe UI", 9, "bold"), width=14, cursor="hand2", bd=1).pack(side="left", padx=4)
        tk.Button(extra, text="Tutup", command=self.close, bg=self.colors["bg_panel"], fg="white", font=("Segoe UI", 9, "bold"), width=10, cursor="hand2", bd=1).pack(side="left", padx=4)

    # ───────────────── CAMERA ─────────────────
    def start_camera(self):
        try:
            self.camera = camera_service.open_camera(self.use_internal, self.camera_url)
            self.is_running = True
            self.update_camera()
        except Exception as e:
            self.live_label.config(text=f"Gagal membuka kamera: {e}")

    def update_camera(self):
        if not self.is_running:
            return

        ret, frame = self.camera.read()
        if not ret:
            self.after(30, self.update_camera)
            return

        target_w = max(1, self.live_label.winfo_width())
        target_h = max(1, self.live_label.winfo_height())
        if target_w < 10 or target_h < 10:
            self.after(33, self.update_camera)
            return

        if self.conv_mode == "gray_to_biner":
            gray = frame if frame.ndim == 2 else conversion_service.rgb_to_gray(frame)
            rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
            rendered = self._resize_cover(rgb, target_w, target_h)
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rendered = self._resize_cover(rgb, target_w, target_h)

        img = Image.fromarray(rendered)
        photo = ImageTk.PhotoImage(img)
        self.live_label.configure(image=photo, text="")
        self.live_label.image = photo

        self.after(33, self.update_camera)

    # ───────────────── ACTIONS ─────────────────
    def capture(self):
        # capture current frame from camera or from selected file
        if self.selected_source_bgr is not None:
            bgr = self.selected_source_bgr.copy()
        else:
            if self.camera is None:
                return
            ret, frame = self.camera.read()
            if not ret:
                return
            bgr = frame

        # simpan juga warna asli agar people detector bisa jalan lebih baik
        try:
            if bgr.ndim == 2:
                bgr_color = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
            elif bgr.ndim == 3 and bgr.shape[2] == 4:
                bgr_color = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)
            else:
                bgr_color = bgr.copy()
            self.selected_source_bgr = bgr_color
        except Exception:
            self.selected_source_bgr = None

        # create grayscale untuk konversi nanti (tapi jangan tampilkan dulu)
        try:
            if bgr.ndim == 2:
                gray = bgr
            else:
                gray = conversion_service.rgb_to_gray(bgr)
            self.gray_frame = gray
        except Exception:
            self.gray_frame = None

        if self.selected_source_bgr is not None:
            if self.conv_mode == "gray_to_biner":
                self.show_image(self.gray_frame, gray=True)
                self.update_info(self.gray_frame, "Grayscale", "Captured")
            else:
                self.show_image(self.selected_source_bgr, gray=False)
                self.update_info(self.selected_source_bgr, "Color", "Captured")
        else:
            self.update_info(np.array([]), "-", "Captured")

        # Reset deteksi - tidak deteksi saat capture, hanya saat simpan
        self.objects_bboxes = []
        self.people_bboxes = []
        self.face_bboxes = []
        self.lbl_objects.config(text="Objek   : -")
        self.lbl_people.config(text="Wajah   : -")

    def convert(self):
        if self.gray_frame is None:
            return

        if self.conv_mode == "rgb_to_gray":
            # simply use gray_frame as converted
            self.converted_frame = self.gray_frame.copy()
            if self.inverted:
                self.converted_frame = cv2.bitwise_not(self.converted_frame)
            self.show_image(self.converted_frame, gray=True)
            self.update_info(self.converted_frame, "Grayscale", "Converted")
        else:
            # threshold to binary
            binary = conversion_service.gray_to_biner(self.gray_frame, self.threshold.get())
            if self.inverted:
                binary = cv2.bitwise_not(binary)
            self.converted_frame = binary
            self.show_image(self.converted_frame, gray=True)
            self.update_info(self.converted_frame, "Black & White", f"Threshold {self.threshold.get()}")

        # Tidak jalankan analisis saat convert - hanya saat simpan
        # self.analyze_and_display()  # Dihapus - analisis hanya saat simpan

    def on_threshold(self, v):
        if self.gray_frame is None:
            return
        binary = conversion_service.gray_to_biner(self.gray_frame, int(v))
        if self.inverted:
            binary = cv2.bitwise_not(binary)
        self.converted_frame = binary
        self.show_image(binary, gray=True)
        self.update_info(binary, "Black & White", f"Realtime {v}")
        # Tidak update analisis realtime - hanya saat simpan
        # self.analyze_and_display()  # Dihapus - analisis hanya saat simpan

    def save(self):
        if self.converted_frame is None:
            messagebox.showinfo("Info", "Belum ada hasil konversi untuk disimpan.")
            return
        
        # Tampilkan progress dialog
        progress_dialog = tk.Toplevel(self)
        progress_dialog.title("Menganalisis Gambar...")
        progress_dialog.geometry("400x150")
        progress_dialog.configure(bg="#2C3E50")
        progress_dialog.transient(self)
        progress_dialog.grab_set()
        
        tk.Label(progress_dialog, text="Sedang menganalisis gambar...",
                font=("Arial", 12, "bold"), bg="#2C3E50", fg="white").pack(pady=20)
        tk.Label(progress_dialog, text="Mendeteksi objek dan wajah...",
                font=("Arial", 10), bg="#2C3E50", fg="#BDC3C7").pack(pady=5)
        progress_dialog.update()
        
        try:
            # Lakukan analisis mendalam pada gambar yang akan disimpan
            # Gunakan source BGR untuk deteksi yang akurat
            source_for_analysis = None
            if self.selected_source_bgr is not None:
                source_for_analysis = self.selected_source_bgr.copy()
            elif self.converted_frame is not None:
                # Jika hanya ada converted (grayscale/biner), convert ke BGR untuk analisis
                if self.converted_frame.ndim == 2:
                    source_for_analysis = cv2.cvtColor(self.converted_frame, cv2.COLOR_GRAY2BGR)
                else:
                    source_for_analysis = self.converted_frame.copy()
            
            if source_for_analysis is not None:
                # Analisis mendalam: deteksi objek dan wajah
                # Bisa menggunakan BGR atau grayscale/biner
                self.perform_deep_analysis(source_for_analysis)
            
            # Juga coba deteksi langsung dari converted_frame jika grayscale/biner
            if self.converted_frame is not None and self.converted_frame.ndim == 2:
                # Deteksi wajah juga dari grayscale/biner langsung
                faces_from_gray = self.detect_faces(self.converted_frame)
                # Pakai fallback dari grayscale hanya jika dari source utama belum ada wajah
                if len(self.face_bboxes) == 0 and len(faces_from_gray) > 0:
                    self.face_bboxes = faces_from_gray
                    self.lbl_people.config(text=f"Wajah   : {len(self.face_bboxes)}")
            
            # Simpan gambar
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"konversi_{self.conv_mode}_{ts}.png"
            cv2.imwrite(os.path.join(self.drive_folder, name), self.converted_frame)
            
            # Update tampilan dengan hasil analisis
            self.update_display_with_analysis()
            
            self.lbl_status.config(text=f"Status  : Disimpan ({name})")
            
            messagebox.showinfo("Sukses", 
                f"Gambar berhasil disimpan!\n"
                f"Objek terdeteksi: {len(self.objects_bboxes)}\n"
                f"Wajah terdeteksi: {len(self.face_bboxes)}")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan atau menganalisis: {e}")
        finally:
            progress_dialog.destroy()
    
    def delete_capture(self):
        """Hapus capture dan reset semua frame"""
        self.gray_frame = None
        self.converted_frame = None
        self.selected_source_bgr = None
        self.inverted = False
        self.objects_bboxes = []
        self.people_bboxes = []
        self.face_bboxes = []
        
        # Reset tampilan
        self.capture_label.configure(image="", text="Belum ada capture", fg="#7F8C8D")
        self.capture_label.image = None
        self.lbl_jenis.config(text="Jenis   : -")
        self.lbl_ukuran.config(text="Ukuran  : -")
        self.lbl_type.config(text="Type    : -")
        self.lbl_status.config(text="Status  : Dihapus")
        self.lbl_objects.config(text="Objek   : -")
        self.lbl_people.config(text="Wajah   : -")
        
        messagebox.showinfo("Info", "Capture berhasil dihapus!")

    # ───────────────── tambahan: buka file lokal & invert ─────────────────
    def open_local_image(self):
        # buka file dialog dengan initialdir ke drive_folder
        try:
            initial = self.drive_folder if os.path.isdir(self.drive_folder) else os.getcwd()
            p = filedialog.askopenfilename(
                title="Pilih Gambar dari Drive Local",
                initialdir=initial,
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")]
            )
            if not p:
                return

            # matikan live camera
            self.stop_camera_for_file()

            # load dengan PIL lalu konversi ke BGR (OpenCV)
            pil = Image.open(p).convert("RGB")
            arr = np.array(pil)
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            self.selected_source_bgr = bgr

            # buat grayscale untuk operasi
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            self.gray_frame = gray
            self.converted_frame = None
            self.inverted = False

            # tampilkan gambar yang dipilih di panel LIVE (resized) - tampilkan RGB/warna
            self.show_live_from_bgr(bgr)

            # tampilkan preview RGB/warna di capture_label (bukan grayscale)
            self.show_image(bgr, gray=False)
            
            # update info berdasarkan file
            fsize = os.path.getsize(p)
            self.lbl_jenis.config(text=f"Jenis   : {detect_image_type(pil)}")
            self.lbl_ukuran.config(text=f"Ukuran  : {format_file_size(fsize)}")
            self.lbl_type.config(text=f"Type    : {self.gray_frame.dtype}")
            self.lbl_status.config(text=f"Status  : Loaded ({os.path.basename(p)})")

            # Reset deteksi - tidak deteksi saat buka file, hanya saat simpan
            self.objects_bboxes = []
            self.people_bboxes = []
            self.face_bboxes = []
            self.lbl_objects.config(text="Objek   : -")
            self.lbl_people.config(text="Wajah   : -")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka file: {e}")

    def stop_camera_for_file(self):
        self.is_running = False
        camera_service.release_camera(self.camera)
        self.camera = None

    def resume_live(self):
        if self.camera is not None and self.is_running:
            return
        self.selected_source_bgr = None
        self.gray_frame = None
        self.converted_frame = None
        self.inverted = False
        try:
            self.camera = camera_service.open_camera(self.use_internal, self.camera_url)
            self.is_running = True
            self.update_camera()
            self.lbl_status.config(text="Status  : Live resumed")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal resume live: {e}")

    def invert_image(self):
        # toggle inverted flag and apply on current visible data
        self.inverted = not self.inverted
        applied = False
        if self.converted_frame is not None:
            # invert converted
            inv = cv2.bitwise_not(self.converted_frame)
            self.converted_frame = inv
            self.show_image(self.converted_frame, gray=True)
            self.update_info(self.converted_frame, self.lbl_jenis.cget("text").split(":")[-1].strip(), "Inverted")
            applied = True
        elif self.gray_frame is not None:
            # invert gray_frame and show as converted (so user can save)
            inv = cv2.bitwise_not(self.gray_frame)
            self.converted_frame = inv
            self.show_image(self.converted_frame, gray=True)
            self.update_info(self.converted_frame, "Grayscale (Inverted)", "Inverted")
            applied = True

        if not applied:
            messagebox.showinfo("Info", "Tidak ada gambar untuk di-invert.")
        else:
            # update analisis jika ada gambar
            self.analyze_and_display()

    # ───────────────── HELPER ─────────────────
    def show_image(self, arr, gray=False, boxes=None, people_boxes=None, face_boxes=None):
        """
        Tampilkan arr di panel capture_label.
        Jika ada boxes/people_boxes/face_boxes, gambar bounding box di atas gambar.
        """
        try:
            if gray:
                vis = arr.copy()
                # convert to BGR for drawing boxes
                vis_bgr = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
            else:
                vis_bgr = arr.copy()
                if vis_bgr.shape[2] == 3:
                    pass
                else:
                    vis_bgr = cv2.cvtColor(vis_bgr, cv2.COLOR_BGRA2BGR)

            # gambar boxes objek (kuning)
            if boxes:
                for (x, y, w, h) in boxes:
                    cv2.rectangle(vis_bgr, (x, y), (x + w, y + h), (0, 215, 255), 2)  # kuning
                    cv2.putText(vis_bgr, "Objek", (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,215,255), 1)

            # gambar boxes people (hijau) - untuk HOG detector
            if people_boxes:
                for (x, y, w, h) in people_boxes:
                    cv2.rectangle(vis_bgr, (x, y), (x + w, y + h), (0, 200, 0), 2)  # hijau
                    cv2.putText(vis_bgr, "Orang", (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,200,0), 1)
            
            # gambar boxes wajah (biru) - untuk face detection
            if face_boxes:
                for (x, y, w, h) in face_boxes:
                    cv2.rectangle(vis_bgr, (x, y), (x + w, y + h), (255, 0, 0), 2)  # biru
                    cv2.putText(vis_bgr, "Wajah", (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1)

            target_w = max(1, self.capture_label.winfo_width())
            target_h = max(1, self.capture_label.winfo_height())
            if target_w < 10 or target_h < 10:
                pass
            
            vis_rgb = cv2.cvtColor(vis_bgr, cv2.COLOR_BGR2RGB)
            rendered = self._resize_cover(vis_rgb, target_w, target_h)

            img = Image.fromarray(rendered)
            photo = ImageTk.PhotoImage(img)
            self.capture_label.configure(image=photo, text="")
            self.capture_label.image = photo
        except Exception as e:
            # fallback
            try:
                target_w = max(1, self.capture_label.winfo_width())
                target_h = max(1, self.capture_label.winfo_height())
                
                if arr.ndim == 2:
                    bb = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
                else:
                    bb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
                
                rendered = self._resize_cover(bb, target_w, target_h)
                img = Image.fromarray(rendered)
                photo = ImageTk.PhotoImage(img)
                self.capture_label.configure(image=photo, text="")
                self.capture_label.image = photo
            except Exception:
                pass

    def show_live_from_bgr(self, bgr):
        # tampilkan gambar BGR pada live_label
        try:
            target_w = max(1, self.live_label.winfo_width())
            target_h = max(1, self.live_label.winfo_height())
            if target_w < 10 or target_h < 10:
                return
            
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            rendered = self._resize_cover(rgb, target_w, target_h)

            img = Image.fromarray(rendered)
            photo = ImageTk.PhotoImage(img)
            self.live_label.configure(image=photo, text="")
            self.live_label.image = photo
        except Exception as e:
            print("show_live_from_bgr error:", e)

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

    def update_info(self, arr, jenis, status):
        # arr adalah numpy array
        size_bytes = int(arr.size) if hasattr(arr, 'size') else 0
        size_kb = size_bytes / 1024 if size_bytes else 0.0

        self.lbl_jenis.config(text=f"Jenis   : {jenis}")
        self.lbl_ukuran.config(text=f"Ukuran  : {size_kb:.2f} KB")
        self.lbl_type.config(text=f"Type    : {arr.dtype if hasattr(arr, 'dtype') else '-'}")
        self.lbl_status.config(text=f"Status  : {status}")

    def close(self):
        self.is_running = False
        camera_service.release_camera(self.camera)
        self.camera = None
        self.destroy()

    def _load_cascade(self, filename):
        """Load cascade classifier dengan aman (skip jika file tidak tersedia)."""
        try:
            base = getattr(cv2.data, "haarcascades", "")
            if not base:
                return None
            path = os.path.join(base, filename)
            if not os.path.isfile(path):
                return None
            cascade = cv2.CascadeClassifier(path)
            if cascade is None or cascade.empty():
                return None
            return cascade
        except Exception:
            return None

    def _skin_mask(self, bgr):
        """Mask sederhana area kulit untuk membantu filter false positive objek tubuh."""
        try:
            ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
            mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=1)
            return mask
        except Exception:
            return np.zeros(bgr.shape[:2], dtype=np.uint8)

    def _face_overlap_ratio(self, box, faces):
        """Rasio overlap box kandidat terhadap wajah (maksimum dari semua wajah)."""
        if not faces:
            return 0.0
        x, y, w, h = box
        area_box = max(1, w * h)
        max_ratio = 0.0
        for fx, fy, fw, fh in faces:
            ix1 = max(x, fx)
            iy1 = max(y, fy)
            ix2 = min(x + w, fx + fw)
            iy2 = min(y + h, fy + fh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            ratio = inter / area_box
            if ratio > max_ratio:
                max_ratio = ratio
        return max_ratio

    def _build_human_mask(self, bgr, faces=None):
        """
        Bangun mask area manusia dari wajah + people detector.
        Mask ini dipakai untuk menekan deteksi objek palsu pada badan/rambut.
        """
        h, w = bgr.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        if faces is None:
            faces = self.detect_faces(bgr)

        # Wajah + torso dari wajah (expand moderat, jangan terlalu agresif)
        for (x, y, fw, fh) in faces:
            cx = x + fw // 2
            cy = y + fh // 2
            cv2.ellipse(
                mask,
                (cx, cy),
                (max(10, int(fw * 0.70)), max(10, int(fh * 0.85))),
                0, 0, 360, 255, -1
            )

            x1 = max(0, x - int(fw * 0.90))
            x2 = min(w, x + fw + int(fw * 0.90))
            y1 = max(0, y + int(fh * 0.35))
            y2 = min(h, y + int(fh * 3.00))
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

        # Tambahkan mask orang dari HOG (kalau ada)
        people = self.detect_people(bgr)
        for (px, py, pw, ph) in people:
            # Gunakan core-body saja (bukan full box) agar objek di tangan tidak ikut terhapus.
            cx = px + (pw // 2)
            core_w = max(20, int(pw * 0.55))
            x1 = max(0, cx - (core_w // 2))
            x2 = min(w, cx + (core_w // 2))
            y1 = max(0, py + int(ph * 0.10))
            y2 = min(h, py + int(ph * 0.92))
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

        if np.count_nonzero(mask) > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17))
            mask = cv2.dilate(mask, k, iterations=1)

        return mask, faces

    # ───────────────── ANALYSIS ─────────────────
    def perform_deep_analysis(self, img):
        """
        Lakukan analisis mendalam pada gambar (BGR, grayscale, atau biner):
        - Deteksi objek dengan akurasi tinggi
        - Deteksi wajah dengan akurasi tinggi (bisa dari BGR, grayscale, atau biner)
        - Simpan hasil ke self.objects_bboxes dan self.face_bboxes
        """
        # Reset
        self.objects_bboxes = []
        self.face_bboxes = []
        
        # Deteksi objek (menggunakan BGR untuk akurasi lebih baik)
        # Jika grayscale/biner, convert ke BGR dulu
        if img.ndim == 2:
            img_for_objects = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            img_for_objects = img.copy()
        self.objects_bboxes = self.detect_objects(img_for_objects)
        
        # Deteksi wajah - bisa langsung dari grayscale/biner atau BGR
        self.face_bboxes = self.detect_faces(img)
        
        # Update labels
        self.lbl_objects.config(text=f"Objek   : {len(self.objects_bboxes)}")
        self.lbl_people.config(text=f"Wajah   : {len(self.face_bboxes)}")
    
    def update_display_with_analysis(self):
        """
        Update tampilan dengan hasil analisis (bounding boxes).
        """
        # Tentukan gambar mana yang akan ditampilkan dengan boxes
        if self.converted_frame is not None:
            # Tampilkan converted dengan boxes
            self.show_image(self.converted_frame, gray=True, 
                          boxes=self.objects_bboxes, face_boxes=self.face_bboxes)
        elif self.selected_source_bgr is not None:
            # Tampilkan source BGR dengan boxes
            self.show_image(self.selected_source_bgr, gray=False,
                          boxes=self.objects_bboxes, face_boxes=self.face_bboxes)
        elif self.gray_frame is not None:
            # Tampilkan grayscale dengan boxes
            self.show_image(self.gray_frame, gray=True,
                          boxes=self.objects_bboxes, face_boxes=self.face_bboxes)
    
    def analyze_and_display(self):
        """
        Jalankan analisis objek & people pada data yang tersedia:
        - Utama: gunakan self.converted_frame (biner) untuk menghitung objek
        - Untuk people: gunakan self.selected_source_bgr bila ada; jika tidak ada,
          lakukan deteksi pada converted -> convert ke BGR & jalankan HOG (kurang akurat)
        - Deteksi wajah untuk fitur crop orang
        """
        # reset
        self.objects_bboxes = []
        self.people_bboxes = []
        self.face_bboxes = []

        # pilih source for object detection: jika ada converted_frame gunakan itu; else use gray_frame
        bin_img = None
        if self.converted_frame is not None:
            # jika converted_frame adalah grayscale (0/255), gunakan langsung
            if self.conv_mode == "gray_to_biner":
                bin_img = self.converted_frame.copy()
            else:
                # rgb_to_gray -> converted_frame is grayscale; threshold it to get bin
                _, bin_img = cv2.threshold(self.converted_frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        elif self.gray_frame is not None:
            _, bin_img = cv2.threshold(self.gray_frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # objek detection: utamakan source warna asli agar lebih presisi
        if self.selected_source_bgr is not None and self.selected_source_bgr.size != 0:
            self.objects_bboxes = self.detect_objects(self.selected_source_bgr)
        elif bin_img is not None and bin_img.size != 0:
            self.objects_bboxes = self.detect_objects(bin_img)

        # people detection via HOG on color image
        if self.selected_source_bgr is not None:
            self.people_bboxes = self.detect_people(self.selected_source_bgr)
            # Deteksi wajah juga
            self.face_bboxes = self.detect_faces(self.selected_source_bgr)
        else:
            # fallback: try detect on a BGR version of gray/converted
            if self.gray_frame is not None:
                try:
                    bgr_try = cv2.cvtColor(self.gray_frame, cv2.COLOR_GRAY2BGR)
                    self.people_bboxes = self.detect_people(bgr_try)
                    self.face_bboxes = self.detect_faces(bgr_try)
                except Exception:
                    self.people_bboxes = []
                    self.face_bboxes = []

        # update labels
        self.lbl_objects.config(text=f"Objek   : {len(self.objects_bboxes)}")
        self.lbl_people.config(text=f"Wajah   : {len(self.face_bboxes)}")

        # show preview with boxes: prefer to draw on converted_frame (if exists) else on gray_frame
        preview_arr = None
        if self.converted_frame is not None:
            preview_arr = self.converted_frame
            self.show_image(preview_arr, gray=True, boxes=self.objects_bboxes, 
                          people_boxes=self.people_bboxes, face_boxes=self.face_bboxes)
        elif self.gray_frame is not None:
            preview_arr = self.gray_frame
            self.show_image(preview_arr, gray=True, boxes=self.objects_bboxes, 
                          people_boxes=self.people_bboxes, face_boxes=self.face_bboxes)
        elif self.selected_source_bgr is not None:
            preview_bgr = self.selected_source_bgr.copy()
            self.show_image(preview_bgr, gray=False, boxes=self.objects_bboxes, 
                          people_boxes=self.people_bboxes, face_boxes=self.face_bboxes)

    def detect_objects(self, bgr_img):
        """
        Deteksi objek barang dengan fokus:
        - minim false positive pada wajah/badan
        - tetap mendeteksi objek yang dipegang tangan
        """
        try:
            if bgr_img is None or bgr_img.size == 0:
                return []

            # Normalisasi channel
            if bgr_img.ndim == 2:
                bgr = cv2.cvtColor(bgr_img, cv2.COLOR_GRAY2BGR)
            elif bgr_img.ndim == 3 and bgr_img.shape[2] == 4:
                bgr = cv2.cvtColor(bgr_img, cv2.COLOR_BGRA2BGR)
            else:
                bgr = bgr_img.copy()

            h, w = bgr.shape[:2]
            if h < 32 or w < 32:
                return []

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)

            # Multi-mask candidate extraction supaya objek kecil/dipegang tetap kebaca
            edges = cv2.Canny(blur, 40, 130)
            k3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, k3, iterations=2)
            edges = cv2.dilate(edges, k3, iterations=1)

            _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            otsu_inv = cv2.bitwise_not(otsu)
            adaptive = cv2.adaptiveThreshold(
                blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 5
            )

            masks = []
            for m in (edges, otsu, otsu_inv, adaptive):
                mm = cv2.morphologyEx(m, cv2.MORPH_OPEN, k3, iterations=1)
                mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, k5, iterations=2)
                masks.append(mm)

            human_mask, faces = self._build_human_mask(bgr)
            skin_mask = self._skin_mask(bgr)

            img_area = float(h * w)
            min_area = max(900, int(img_area * 0.0015))
            max_area = int(img_area * 0.42)
            candidates = []

            for mask in masks:
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in contours:
                    area = cv2.contourArea(c)
                    if area < min_area or area > max_area:
                        continue

                    x, y, bw, bh = cv2.boundingRect(c)
                    if bw < 20 or bh < 20:
                        continue

                    aspect_ratio = bw / float(max(1, bh))
                    if aspect_ratio < 0.20 or aspect_ratio > 4.8:
                        continue

                    rect_area = float(bw * bh)
                    if rect_area <= 0:
                        continue

                    extent = area / rect_area
                    if extent < 0.22:
                        continue

                    hull = cv2.convexHull(c)
                    hull_area = cv2.contourArea(hull)
                    solidity = area / float(max(1.0, hull_area))
                    if solidity < 0.18:
                        continue

                    # Box menempel tepi frame sering noise background.
                    if (x <= 2 or y <= 2 or (x + bw) >= (w - 2) or (y + bh) >= (h - 2)) and area < (img_area * 0.04):
                        continue

                    human_roi = human_mask[y:y + bh, x:x + bw]
                    human_ratio = float(np.count_nonzero(human_roi)) / rect_area if human_roi.size else 0.0

                    skin_roi = skin_mask[y:y + bh, x:x + bw]
                    skin_ratio = float(np.count_nonzero(skin_roi)) / rect_area if skin_roi.size else 0.0

                    face_overlap = self._face_overlap_ratio((x, y, bw, bh), faces)

                    # Reject komponen yang sangat mungkin bagian wajah/badan.
                    if human_ratio > 0.90:
                        continue
                    if human_ratio > 0.65 and skin_ratio > 0.12:
                        continue
                    if face_overlap > 0.18:
                        continue

                    edge_roi = edges[y:y + bh, x:x + bw]
                    edge_density = float(np.count_nonzero(edge_roi)) / rect_area if edge_roi.size else 0.0
                    if edge_density < 0.012 and extent < 0.35:
                        continue

                    # Score kandidat: lebih suka yang non-human, cukup padat, dan punya boundary.
                    score = (
                        (1.8 * (1.0 - min(1.0, human_ratio))) +
                        (0.9 * max(0.0, 0.35 - skin_ratio)) +
                        (0.8 * min(1.0, solidity)) +
                        (0.7 * min(1.0, extent)) +
                        (0.8 * min(1.0, edge_density * 8.0))
                    )
                    candidates.append((x, y, bw, bh, score))

            if not candidates:
                return []

            # NMS sederhana berbasis overlap ratio.
            candidates.sort(key=lambda t: t[4], reverse=True)
            selected = []
            for cand in candidates:
                box = cand[:4]
                keep = True
                for prev in selected:
                    if self.calculate_overlap(box, prev[:4]) > 0.55:
                        keep = False
                        break
                if keep:
                    selected.append(cand)
                if len(selected) >= 12:
                    break

            boxes = [tuple(int(v) for v in c[:4]) for c in selected]
            boxes = self.remove_overlapping_boxes(boxes, overlap_threshold=0.55)
            boxes.sort(key=lambda r: (r[1], r[0]))
            return boxes
        except Exception as e:
            print("detect_objects error:", e)
            return []
    
    def calculate_overlap(self, box1, box2):
        """Hitung overlap ratio antara dua bounding box."""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        overlap_area = x_overlap * y_overlap
        
        area1 = w1 * h1
        area2 = w2 * h2
        min_area = min(area1, area2)
        
        return overlap_area / min_area if min_area > 0 else 0
    
    def remove_overlapping_boxes(self, boxes, overlap_threshold=0.5):
        """
        Hapus bounding box yang overlap terlalu banyak.
        """
        if len(boxes) <= 1:
            return boxes
        
        filtered = []
        for i, (x1, y1, w1, h1) in enumerate(boxes):
            is_duplicate = False
            area1 = w1 * h1
            
            for j, (x2, y2, w2, h2) in enumerate(boxes):
                if i == j:
                    continue
                
                # Hitung overlap
                x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
                overlap_area = x_overlap * y_overlap
                
                # Jika overlap > threshold, pilih yang lebih besar
                if overlap_area > 0:
                    overlap_ratio = overlap_area / min(area1, w2 * h2)
                    if overlap_ratio > overlap_threshold:
                        area2 = w2 * h2
                        if area2 > area1:
                            is_duplicate = True
                            break
            
            if not is_duplicate:
                filtered.append((x1, y1, w1, h1))
        
        return filtered

    def detect_people(self, bgr):
        """
        Deteksi orang menggunakan HOGDescriptor default OpenCV.
        Kembalikan bounding boxes (x,y,w,h) pada ukuran asli bgr.
        """
        try:
            if bgr is None or bgr.size == 0:
                return []
            # resize untuk performa deteksi HOG
            h, w = bgr.shape[:2]
            max_w = 800
            scale = 1.0
            if w > max_w:
                scale = max_w / w
                small = cv2.resize(bgr, (int(w*scale), int(h*scale)))
            else:
                small = bgr.copy()

            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            rects, weights = hog.detectMultiScale(small, winStride=(8,8), padding=(8,8), scale=1.05)
            boxes = []
            for (x,y,ww,hh) in rects:
                # scale back to original size if resized
                if scale != 1.0:
                    sx = int(x / scale); sy = int(y / scale)
                    sww = int(ww / scale); shh = int(hh / scale)
                    boxes.append((sx, sy, sww, shh))
                else:
                    boxes.append((x,y,ww,hh))
            # optional: filter by weight if available (not returned together in older OpenCV)
            return boxes
        except Exception as e:
            print("detect_people error:", e)
            return []

    def detect_faces(self, img):
        """
        Deteksi wajah lebih robust (BGR/grayscale/biner):
        - multi-cascade + multi-preprocess
        - deduplicate overlap
        - validasi fitur mata/hidung bila tersedia
        Kembalikan bounding boxes (x,y,w,h) pada ukuran asli.
        """
        try:
            if img is None or img.size == 0:
                return []

            cascades = [c for c in (self.face_cascade, self.face_alt_cascade) if c is not None]
            if not cascades:
                return []

            # Normalisasi ke grayscale
            if img.ndim == 3:
                if img.shape[2] == 3:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                elif img.shape[2] == 4:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                else:
                    gray = img[:, :, 0]
            else:
                gray = img.copy()

            # Pastikan uint8
            if gray.dtype != np.uint8:
                gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

            h, w = gray.shape[:2]
            if h < 32 or w < 32:
                return []

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray)
            gray_eq = cv2.equalizeHist(gray)
            gray_blur = cv2.GaussianBlur(gray_clahe, (3, 3), 0)
            variants = [gray_clahe, gray_eq, gray_blur]

            # Multi-pass detect untuk memperbesar recall tanpa terlalu longgar.
            raw_faces = []
            param_sets = [
                (1.08, 6, (44, 44)),
                (1.12, 5, (36, 36)),
            ]
            for cascade in cascades:
                for var in variants:
                    for scale_factor, min_neighbors, min_size in param_sets:
                        faces = cascade.detectMultiScale(
                            var,
                            scaleFactor=scale_factor,
                            minNeighbors=min_neighbors,
                            minSize=min_size,
                            flags=cv2.CASCADE_SCALE_IMAGE
                        )
                        for (x, y, fw, fh) in faces:
                            raw_faces.append((int(x), int(y), int(fw), int(fh)))

            if not raw_faces:
                return []

            # Filter geometri wajah yang masuk akal.
            filtered = []
            for (x, y, fw, fh) in raw_faces:
                if fw <= 0 or fh <= 0:
                    continue
                aspect_ratio = fw / float(fh)
                if aspect_ratio < 0.55 or aspect_ratio > 1.6:
                    continue
                area_ratio = (fw * fh) / float(h * w)
                if area_ratio < 0.0025 or area_ratio > 0.50:
                    continue
                filtered.append((x, y, fw, fh))

            if not filtered:
                return []

            # Remove duplicates
            merged = []
            for box in sorted(filtered, key=lambda b: b[2] * b[3], reverse=True):
                duplicate = False
                for mbox in merged:
                    if self.calculate_overlap(box, mbox) > 0.60:
                        duplicate = True
                        break
                if not duplicate:
                    merged.append(box)

            # Validasi fitur wajah (mata/hidung) jika cascade tersedia.
            validated = []
            for (x, y, fw, fh) in merged:
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(w, x + fw)
                y2 = min(h, y + fh)
                if x2 <= x1 or y2 <= y1:
                    continue

                roi_gray = gray_clahe[y1:y2, x1:x2]
                if roi_gray.size == 0:
                    continue

                eye_hits = 0
                nose_hits = 0

                if self.eye_cascade is not None:
                    eyes = self.eye_cascade.detectMultiScale(
                        roi_gray,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(max(10, fw // 10), max(10, fh // 10))
                    )
                    for (_, ey, _, eh) in eyes:
                        # Mata seharusnya dominan di bagian atas wajah
                        if (ey + (eh * 0.5)) <= (fh * 0.72):
                            eye_hits += 1

                if self.nose_cascade is not None:
                    noses = self.nose_cascade.detectMultiScale(
                        roi_gray,
                        scaleFactor=1.1,
                        minNeighbors=3,
                        minSize=(max(10, fw // 12), max(10, fh // 12))
                    )
                    for (_, ny, _, nh) in noses:
                        center_y = ny + (nh * 0.5)
                        if (fh * 0.20) <= center_y <= (fh * 0.90):
                            nose_hits += 1

                # Score simple untuk menahan false positive.
                area_ratio = (fw * fh) / float(h * w)
                face_score = 0.8 + min(0.7, area_ratio * 6.0)
                if eye_hits >= 1:
                    face_score += 0.9
                if nose_hits >= 1:
                    face_score += 0.4

                if (self.eye_cascade is None and self.nose_cascade is None) or face_score >= 1.2:
                    validated.append((x1, y1, x2 - x1, y2 - y1))

            # Fallback: kalau validasi fitur terlalu ketat, pakai hasil merged.
            results = validated if validated else merged
            results = self.remove_overlapping_boxes(results, overlap_threshold=0.55)
            results.sort(key=lambda r: (r[1], r[0]))
            return results[:8]
        except Exception as e:
            print("detect_faces error:", e)
            return []

    def crop_person(self):
        """
        Hapus orang lain dari gambar, hanya pertahankan 1 orang.
        Orang lain dihapus (jadikan hitam), bukan di-inpaint.
        """
        # Gunakan source BGR untuk deteksi wajah
        source_img = None
        if self.selected_source_bgr is not None:
            source_img = self.selected_source_bgr.copy()
        elif self.converted_frame is not None:
            messagebox.showwarning("Warning", 
                "Untuk crop orang, perlu gambar warna asli.\n"
                "Silakan capture ulang atau buka file gambar warna.")
            return
        else:
            messagebox.showwarning("Warning", "Belum ada gambar untuk di-crop!")
            return

        # Progress dialog dengan analisis
        progress_dialog = tk.Toplevel(self)
        progress_dialog.title("Menganalisis & Crop Orang...")
        progress_dialog.geometry("450x180")
        progress_dialog.configure(bg="#2C3E50")
        progress_dialog.transient(self)
        progress_dialog.grab_set()
        
        status_label = tk.Label(progress_dialog, text="Memulai analisis...",
                font=("Arial", 11, "bold"), bg="#2C3E50", fg="white")
        status_label.pack(pady=15)
        
        detail_label = tk.Label(progress_dialog, text="",
                font=("Arial", 9), bg="#2C3E50", fg="#BDC3C7")
        detail_label.pack(pady=5)
        progress_dialog.update()

        try:
            # Analisis: Deteksi wajah
            status_label.config(text="Menganalisis gambar...")
            detail_label.config(text="Mendeteksi wajah...")
            progress_dialog.update()
            
            faces = self.detect_faces(source_img)
            
            if len(faces) == 0:
                progress_dialog.destroy()
                messagebox.showinfo("Info", "Tidak ada wajah terdeteksi dalam gambar.")
                return
            elif len(faces) == 1:
                # Hanya 1 wajah, langsung hapus background/orang lain
                selected_face = faces[0]
            else:
                # Lebih dari 1 wajah, buka dialog untuk memilih
                progress_dialog.destroy()
                selected_idx = self.choose_person_dialog(source_img, faces)
                if selected_idx is None:
                    return  # User cancel
                selected_face = faces[selected_idx]
                
                # Buka progress dialog lagi
                progress_dialog = tk.Toplevel(self)
                progress_dialog.title("Menganalisis & Crop Orang...")
                progress_dialog.geometry("450x180")
                progress_dialog.configure(bg="#2C3E50")
                progress_dialog.transient(self)
                progress_dialog.grab_set()
                
                status_label = tk.Label(progress_dialog, text="Memproses...",
                        font=("Arial", 11, "bold"), bg="#2C3E50", fg="white")
                status_label.pack(pady=15)
                
                detail_label = tk.Label(progress_dialog, text="Menghapus orang lain...",
                        font=("Arial", 9), bg="#2C3E50", fg="#BDC3C7")
                detail_label.pack(pady=5)
                progress_dialog.update()

            # Proses: Hapus orang lain
            status_label.config(text="Menghapus orang lain...")
            detail_label.config(text="Orang lain akan dihapus (hitam)...")
            progress_dialog.update()
            
            result_img = self.remove_other_people(source_img, [selected_face])

            # Update frame dengan hasil
            self.selected_source_bgr = result_img
            
            # Update grayscale dari hasil
            try:
                gray = cv2.cvtColor(result_img, cv2.COLOR_BGR2GRAY)
                self.gray_frame = gray
                self.converted_frame = None
            except Exception:
                pass

            # Tampilkan hasil
            self.show_live_from_bgr(result_img)
            if 'gray' in locals():
                self.show_image(gray, gray=True)
                self.update_info(gray, "Grayscale", "Crop selesai")
            else:
                self.show_image(result_img, gray=False)
                self.update_info(result_img, "Color", "Crop selesai")
            
            # Update info
            self.lbl_status.config(text=f"Status  : Crop selesai (1 orang dipertahankan, {len(faces)-1} orang dihapus)")
            
            messagebox.showinfo("Sukses", 
                f"Berhasil crop gambar!\n"
                f"1 orang dipertahankan dari {len(faces)} wajah terdeteksi.\n"
                f"Orang lain telah dihapus (hitam).")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal crop orang: {e}")
        finally:
            progress_dialog.destroy()

    def choose_person_dialog(self, img, faces):
        """
        Dialog untuk memilih orang yang ingin dipertahankan.
        Kembalikan index wajah yang dipilih, atau None jika cancel.
        """
        dialog = tk.Toplevel(self)
        dialog.title("Pilih Orang yang Ingin Dipertahankan")
        dialog.geometry("600x500")
        dialog.configure(bg="#2C3E50")
        dialog.transient(self)
        dialog.grab_set()

        selected_idx = [None]  # Use list to allow modification in nested function

        tk.Label(dialog, text=f"Terdeteksi {len(faces)} wajah. Pilih yang ingin dipertahankan:",
                font=("Arial", 12, "bold"), bg="#2C3E50", fg="white").pack(pady=10)

        # Buat preview dengan bounding box
        preview_img = img.copy()
        for i, (x, y, w, h) in enumerate(faces):
            color = (0, 255, 0) if i == 0 else (0, 0, 255)
            cv2.rectangle(preview_img, (x, y), (x + w, y + h), color, 3)
            cv2.putText(preview_img, f"Orang {i+1}", (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Resize untuk preview
        h, w = preview_img.shape[:2]
        ratio = min(500 / w, 350 / h)
        nw, nh = int(w * ratio), int(h * ratio)
        preview_resized = cv2.resize(preview_img, (nw, nh))
        preview_rgb = cv2.cvtColor(preview_resized, cv2.COLOR_BGR2RGB)
        preview_pil = Image.fromarray(preview_rgb)
        preview_photo = ImageTk.PhotoImage(preview_pil)

        preview_label = tk.Label(dialog, image=preview_photo, bg="#2C3E50")
        preview_label.image = preview_photo
        preview_label.pack(pady=10)

        tk.Label(dialog, text="Hijau = Orang 1, Merah = Orang lainnya",
                font=("Arial", 9, "italic"), bg="#2C3E50", fg="#BDC3C7").pack()

        # Radio buttons untuk memilih
        choice_frame = tk.Frame(dialog, bg="#2C3E50")
        choice_frame.pack(pady=10)
        
        choice_var = tk.IntVar(value=0)
        for i in range(len(faces)):
            rb = tk.Radiobutton(choice_frame, text=f"Orang {i+1}",
                               variable=choice_var, value=i,
                               bg="#2C3E50", fg="white", selectcolor="#34495E",
                               font=("Arial", 11))
            rb.pack(anchor='w', padx=20, pady=5)

        # Buttons
        btn_frame = tk.Frame(dialog, bg="#2C3E50")
        btn_frame.pack(pady=15)

        def on_ok():
            selected_idx[0] = choice_var.get()
            dialog.destroy()

        def on_cancel():
            selected_idx[0] = None
            dialog.destroy()

        tk.Button(btn_frame, text="OK", command=on_ok,
                 bg="#27AE60", fg="white", width=12).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=on_cancel,
                 bg="#E74C3C", fg="white", width=12).pack(side="left", padx=10)

        dialog.wait_window()
        return selected_idx[0]

    def remove_other_people(self, img, keep_faces):
        """
        Hapus orang lain dengan Instance Segmentation yang akurat.
        Menggunakan GrabCut untuk setiap instance orang secara terpisah.
        
        Args:
            img: gambar BGR
            keep_faces: list of (x,y,w,h) - wajah yang ingin dipertahankan
        
        Returns:
            gambar hasil dengan hanya orang yang dipilih, orang lain jadi hitam
        """
        try:
            result = img.copy()
            h, w = img.shape[:2]
            
            # Deteksi semua wajah untuk instance segmentation
            all_faces = self.detect_faces(img)
            
            # Buat mask untuk orang yang dipertahankan menggunakan instance segmentation
            keep_mask = np.zeros((h, w), dtype=np.uint8)
            
            # Untuk setiap wajah yang dipertahankan, lakukan instance segmentation
            for keep_face in keep_faces:
                x, y, fw, fh = keep_face
                
                # Expand area untuk instance segmentation
                expand_y_down = int(fh * 3.5)
                expand_y_up = int(fh * 0.4)
                expand_x = int(fw * 0.7)
                
                x1 = max(0, x - expand_x)
                y1 = max(0, y - expand_y_up)
                x2 = min(w, x + fw + expand_x)
                y2 = min(h, y + fh + expand_y_down)
                
                # Instance segmentation dengan GrabCut untuk orang ini
                roi = img[y1:y2, x1:x2].copy()
                if roi.size == 0:
                    continue
                
                roi_h, roi_w = roi.shape[:2]
                roi_mask = np.zeros((roi_h, roi_w), np.uint8)
                
                # Set area wajah sebagai foreground
                face_x_in_roi = x - x1
                face_y_in_roi = y - y1
                face_x2 = min(roi_w, face_x_in_roi + fw)
                face_y2 = min(roi_h, face_y_in_roi + fh)
                
                roi_mask[max(0, face_y_in_roi):face_y2, max(0, face_x_in_roi):face_x2] = cv2.GC_FGD
                roi_mask[roi_mask == 0] = cv2.GC_BGD
                
                # GrabCut untuk instance segmentation
                bgd_model = np.zeros((1, 65), np.float64)
                fgd_model = np.zeros((1, 65), np.float64)
                cv2.grabCut(roi, roi_mask, None, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)
                
                # Buat mask final untuk ROI ini
                roi_mask_final = np.where((roi_mask == 2) | (roi_mask == 0), 0, 1).astype('uint8')
                
                # Refine dengan morphological operations
                kernel = np.ones((3, 3), np.uint8)
                roi_mask_final = cv2.morphologyEx(roi_mask_final, cv2.MORPH_CLOSE, kernel, iterations=2)
                
                # Update keep_mask dengan hasil instance segmentation
                keep_mask[y1:y2, x1:x2] = np.maximum(keep_mask[y1:y2, x1:x2], roi_mask_final)
            
            # Hapus area yang tidak dipertahankan (jadikan hitam)
            if result.ndim == 3:
                result[keep_mask == 0] = [0, 0, 0]
            else:
                result[keep_mask == 0] = 0
            
            return result
            
        except Exception as e:
            print(f"remove_other_people error: {e}")
            return img

    def move_person(self):
        """
        Geser orang kedua secara otomatis (pixel manipulation).
        Orang pertama tetap di tempat, hanya orang kedua yang digeser.
        """
        # Gunakan source BGR
        source_img = None
        if self.selected_source_bgr is not None:
            source_img = self.selected_source_bgr.copy()
        elif self.converted_frame is not None:
            messagebox.showwarning("Warning", 
                "Untuk geser orang, perlu gambar warna asli.\n"
                "Silakan capture ulang atau buka file gambar warna.")
            return
        else:
            messagebox.showwarning("Warning", "Belum ada gambar untuk digeser!")
            return

        # Progress dialog dengan analisis
        progress_dialog = tk.Toplevel(self)
        progress_dialog.title("Menganalisis & Geser Orang...")
        progress_dialog.geometry("450x180")
        progress_dialog.configure(bg="#2C3E50")
        progress_dialog.transient(self)
        progress_dialog.grab_set()
        
        status_label = tk.Label(progress_dialog, text="Memulai analisis...",
                font=("Arial", 11, "bold"), bg="#2C3E50", fg="white")
        status_label.pack(pady=15)
        
        detail_label = tk.Label(progress_dialog, text="",
                font=("Arial", 9), bg="#2C3E50", fg="#BDC3C7")
        detail_label.pack(pady=5)
        progress_dialog.update()

        try:
            # Analisis: Deteksi wajah
            status_label.config(text="Menganalisis gambar...")
            detail_label.config(text="Mendeteksi wajah...")
            progress_dialog.update()
            
            faces = self.detect_faces(source_img)
            
            if len(faces) < 2:
                progress_dialog.destroy()
                messagebox.showinfo("Info", 
                    f"Terdeteksi {len(faces)} wajah.\n"
                    f"Minimal perlu 2 wajah untuk fitur geser orang.")
                return
            
            # Pilih orang pertama (tetap di tempat) dan orang kedua (yang digeser)
            # Default: orang pertama = wajah paling kiri, orang kedua = wajah lainnya
            faces_sorted = sorted(faces, key=lambda f: f[0])  # Sort berdasarkan x (kiri ke kanan)
            keep_face = faces_sorted[0]  # Orang pertama (paling kiri)
            move_face = faces_sorted[1]  # Orang kedua
            
            if len(faces) > 2:
                # Jika lebih dari 2, tanya user mana yang digeser
                progress_dialog.destroy()
                move_idx = self.choose_person_to_move_dialog(source_img, faces, keep_face)
                if move_idx is None:
                    return
                keep_face = faces[move_idx]
                # Pilih orang lain sebagai yang digeser
                other_faces = [f for i, f in enumerate(faces) if i != move_idx]
                move_face = other_faces[0] if other_faces else None
                
                if move_face is None:
                    return
                
                # Buka progress dialog lagi
                progress_dialog = tk.Toplevel(self)
                progress_dialog.title("Menganalisis & Geser Orang...")
                progress_dialog.geometry("450x180")
                progress_dialog.configure(bg="#2C3E50")
                progress_dialog.transient(self)
                progress_dialog.grab_set()
                
                status_label = tk.Label(progress_dialog, text="Memproses...",
                        font=("Arial", 11, "bold"), bg="#2C3E50", fg="white")
                status_label.pack(pady=15)
                
                detail_label = tk.Label(progress_dialog, text="",
                        font=("Arial", 9), bg="#2C3E50", fg="#BDC3C7")
                detail_label.pack(pady=5)
                progress_dialog.update()

            # Proses: Geser orang kedua
            status_label.config(text="Menggeser orang kedua...")
            detail_label.config(text="Memproses perpindahan pixel...")
            progress_dialog.update()
            
            result_img = self.move_person_pixels(source_img, keep_face, move_face)

            # Update frame dengan hasil
            self.selected_source_bgr = result_img
            
            # Update grayscale dari hasil
            try:
                gray = cv2.cvtColor(result_img, cv2.COLOR_BGR2GRAY)
                self.gray_frame = gray
                self.converted_frame = None
            except Exception:
                pass

            # Tampilkan hasil
            self.show_live_from_bgr(result_img)
            if 'gray' in locals():
                self.show_image(gray, gray=True)
            else:
                self.show_image(result_img, gray=False)
            
            # Update info
            self.lbl_status.config(text="Status  : Orang kedua telah digeser")
            
            messagebox.showinfo("Sukses", 
                f"Berhasil geser orang!\n"
                f"Orang pertama tetap di tempat.\n"
                f"Orang kedua telah digeser secara otomatis.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal geser orang: {e}")
        finally:
            try:
                if 'progress_dialog' in locals() and progress_dialog.winfo_exists():
                    progress_dialog.destroy()
            except Exception:
                pass

    def choose_person_to_move_dialog(self, img, faces, keep_face):
        """
        Dialog untuk memilih orang yang tetap di tempat (yang lain akan digeser).
        """
        dialog = tk.Toplevel(self)
        dialog.title("Pilih Orang yang Tetap di Tempat")
        dialog.geometry("600x500")
        dialog.configure(bg="#2C3E50")
        dialog.transient(self)
        dialog.grab_set()

        selected_idx = [None]

        tk.Label(dialog, text=f"Terdeteksi {len(faces)} wajah. Pilih yang tetap di tempat:",
                font=("Arial", 12, "bold"), bg="#2C3E50", fg="white").pack(pady=10)

        # Buat preview dengan bounding box
        preview_img = img.copy()
        for i, (x, y, w, h) in enumerate(faces):
            color = (0, 255, 0) if (x, y, w, h) == keep_face else (0, 0, 255)
            cv2.rectangle(preview_img, (x, y), (x + w, y + h), color, 3)
            cv2.putText(preview_img, f"Orang {i+1}", (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Resize untuk preview
        h, w = preview_img.shape[:2]
        ratio = min(500 / w, 350 / h)
        nw, nh = int(w * ratio), int(h * ratio)
        preview_resized = cv2.resize(preview_img, (nw, nh))
        preview_rgb = cv2.cvtColor(preview_resized, cv2.COLOR_BGR2RGB)
        preview_pil = Image.fromarray(preview_rgb)
        preview_photo = ImageTk.PhotoImage(preview_pil)

        preview_label = tk.Label(dialog, image=preview_photo, bg="#2C3E50")
        preview_label.image = preview_photo
        preview_label.pack(pady=10)

        tk.Label(dialog, text="Hijau = Tetap di tempat, Merah = Akan digeser",
                font=("Arial", 9, "italic"), bg="#2C3E50", fg="#BDC3C7").pack()

        # Radio buttons
        choice_frame = tk.Frame(dialog, bg="#2C3E50")
        choice_frame.pack(pady=10)
        
        choice_var = tk.IntVar(value=0)
        for i, (x, y, w, h) in enumerate(faces):
            is_keep = ((x, y, w, h) == keep_face)
            rb = tk.Radiobutton(choice_frame, text=f"Orang {i+1} {'(Default)' if is_keep else ''}",
                               variable=choice_var, value=i,
                               bg="#2C3E50", fg="white", selectcolor="#34495E",
                               font=("Arial", 11))
            rb.pack(anchor='w', padx=20, pady=5)

        # Buttons
        btn_frame = tk.Frame(dialog, bg="#2C3E50")
        btn_frame.pack(pady=15)

        def on_ok():
            selected_idx[0] = choice_var.get()
            dialog.destroy()

        def on_cancel():
            selected_idx[0] = None
            dialog.destroy()

        tk.Button(btn_frame, text="OK", command=on_ok,
                 bg="#27AE60", fg="white", width=12).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=on_cancel,
                 bg="#E74C3C", fg="white", width=12).pack(side="left", padx=10)

        dialog.wait_window()
        return selected_idx[0]

    def move_person_pixels(self, img, keep_face, move_face):
        """
        Geser 1 orang dengan translasi pixel pada frame (bukan crop kotak PNG).
        Alur:
        1) Segmentasi orang dari face seed
        2) Inpaint background di posisi lama
        3) Translasi layer orang ke posisi baru
        4) Feather blend ke frame hasil
        """
        try:
            h, w = img.shape[:2]
            xk, yk, wk, hk = [int(v) for v in keep_face]
            xm, ym, wm, hm = [int(v) for v in move_face]

            # 1) Segmentasi orang yang akan digeser (seed dari wajah)
            person_mask = np.zeros((h, w), dtype=np.uint8)
            expand_x = int(wm * 1.1)
            expand_up = int(hm * 0.45)
            expand_down = int(hm * 4.2)

            x1 = max(0, xm - expand_x)
            y1 = max(0, ym - expand_up)
            x2 = min(w, xm + wm + expand_x)
            y2 = min(h, ym + hm + expand_down)

            roi = img[y1:y2, x1:x2]
            if roi.size == 0:
                return img

            rh, rw = roi.shape[:2]
            gc_mask = np.full((rh, rw), cv2.GC_BGD, dtype=np.uint8)

            fx1 = max(0, xm - x1)
            fy1 = max(0, ym - y1)
            fx2 = min(rw, fx1 + wm)
            fy2 = min(rh, fy1 + hm)

            # Wajah = sure foreground
            gc_mask[fy1:fy2, fx1:fx2] = cv2.GC_FGD

            # Torso sekitar wajah = probable foreground
            tx1 = max(0, fx1 - int(wm * 0.75))
            tx2 = min(rw, fx2 + int(wm * 0.75))
            ty1 = max(0, fy1 + int(hm * 0.20))
            ty2 = min(rh, fy2 + int(hm * 3.00))
            gc_mask[ty1:ty2, tx1:tx2] = np.maximum(gc_mask[ty1:ty2, tx1:tx2], cv2.GC_PR_FGD)

            # Tepi ROI paksa background
            margin = 8
            gc_mask[:margin, :] = cv2.GC_BGD
            gc_mask[-margin:, :] = cv2.GC_BGD
            gc_mask[:, :margin] = cv2.GC_BGD
            gc_mask[:, -margin:] = cv2.GC_BGD

            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            cv2.grabCut(roi, gc_mask, None, bgd_model, fgd_model, 4, cv2.GC_INIT_WITH_MASK)
            cv2.grabCut(roi, gc_mask, None, bgd_model, fgd_model, 2, cv2.GC_EVAL)

            roi_mask = np.where(
                (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0
            ).astype(np.uint8)

            # Ambil komponen terhubung yang menyentuh area wajah
            nlab, labels, stats, _ = cv2.connectedComponentsWithStats(roi_mask, connectivity=8)
            if nlab > 1:
                cx = min(rw - 1, max(0, fx1 + (wm // 2)))
                cy = min(rh - 1, max(0, fy1 + (hm // 2)))
                face_label = labels[cy, cx]
                if face_label > 0:
                    roi_mask = np.where(labels == face_label, 255, 0).astype(np.uint8)
                else:
                    # fallback ke komponen terbesar jika titik wajah tidak kena
                    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
                    roi_mask = np.where(labels == largest_label, 255, 0).astype(np.uint8)

            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, k, iterations=2)
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, k, iterations=1)

            person_mask[y1:y2, x1:x2] = roi_mask

            # Fallback jika mask terlalu kecil: pakai body region berbasis wajah
            if np.count_nonzero(person_mask) < max(800, int(h * w * 0.004)):
                person_mask[:] = 0
                bx1 = max(0, xm - int(wm * 0.9))
                bx2 = min(w, xm + wm + int(wm * 0.9))
                by1 = max(0, ym - int(hm * 0.2))
                by2 = min(h, ym + int(hm * 3.4))
                cv2.rectangle(person_mask, (bx1, by1), (bx2, by2), 255, -1)
                person_mask = cv2.GaussianBlur(person_mask, (7, 7), 0)
                _, person_mask = cv2.threshold(person_mask, 20, 255, cv2.THRESH_BINARY)

            ys, xs = np.where(person_mask > 0)
            if xs.size == 0 or ys.size == 0:
                return img

            pbx1, pbx2 = int(xs.min()), int(xs.max())
            pby1, pby2 = int(ys.min()), int(ys.max())
            pbw = max(1, pbx2 - pbx1 + 1)
            pbh = max(1, pby2 - pby1 + 1)

            # 2) Hitung shift arah horizontal (translasi frame)
            keep_cx = xk + (wk // 2)
            move_cx = xm + (wm // 2)
            direction = -1 if move_cx > keep_cx else 1  # menjauh dari orang yang diam

            desired = int(w * 0.28) * direction
            min_shift = -pbx1
            max_shift = (w - 1) - pbx2
            shift_x = int(np.clip(desired, min_shift, max_shift))

            min_needed = max(28, int(w * 0.04))
            if abs(shift_x) < min_needed:
                alt = int(np.clip(-desired, min_shift, max_shift))
                if abs(alt) > abs(shift_x):
                    shift_x = alt

            if shift_x == 0:
                return img

            # Hindari terlalu overlap dengan orang yang diam.
            keep_box = (
                max(0, xk - int(wk * 1.0)),
                max(0, yk - int(hk * 0.4)),
                min(w - 1, xk + wk + int(wk * 1.0)) - max(0, xk - int(wk * 1.0)),
                min(h - 1, yk + int(hk * 3.0)) - max(0, yk - int(hk * 0.4))
            )
            moved_box = (pbx1 + shift_x, pby1, pbw, pbh)
            if self.calculate_overlap(moved_box, keep_box) > 0.30:
                alt = int(np.clip(-desired, min_shift, max_shift))
                alt_box = (pbx1 + alt, pby1, pbw, pbh)
                if self.calculate_overlap(alt_box, keep_box) < self.calculate_overlap(moved_box, keep_box):
                    shift_x = alt

            # 3) Hapus orang dari posisi awal dengan inpaint (isi background, bukan hitam)
            remove_mask = person_mask.copy()
            kd = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            remove_mask = cv2.dilate(remove_mask, kd, iterations=1)
            background = cv2.inpaint(img, remove_mask, 6, cv2.INPAINT_TELEA)

            # 4) Translasi layer orang + mask
            M = np.float32([[1, 0, float(shift_x)], [0, 1, 0.0]])
            moved_pixels = cv2.warpAffine(
                img, M, (w, h), flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)
            )
            moved_mask = cv2.warpAffine(
                person_mask, M, (w, h), flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT, borderValue=0
            )

            moved_mask = cv2.morphologyEx(moved_mask, cv2.MORPH_CLOSE, k, iterations=1)
            soft_mask = cv2.GaussianBlur(moved_mask, (0, 0), sigmaX=1.8, sigmaY=1.8)
            alpha = (soft_mask.astype(np.float32) / 255.0)[..., np.newaxis]

            result = (
                (background.astype(np.float32) * (1.0 - alpha)) +
                (moved_pixels.astype(np.float32) * alpha)
            ).astype(np.uint8)

            return result
            
        except Exception as e:
            print(f"move_person_pixels error: {e}")
            return img

    def human_semantic_segmentation(self, img, faces):
        """
        Smart Human Semantic Segmentation dengan Analisis Presisi.
        SAFE approach: Detect wajah dulu, expand daerah tubuh AMAN, hapus background yg JELAS.
        """
        h, w = img.shape[:2]
        
        # Convert color space
        if img.ndim == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            bgr = img.copy()
        else:
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            gray = img.copy()
        
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # ======================================================================
        # STEP 1: Face-Based Initial Seeding (SAFE AREA)
        # ======================================================================
        for (x, y, fw, fh) in faces:
            # Face region - pasti foreground
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w, x + fw)
            y2 = min(h, y + fh)
            mask[y1:y2, x1:x2] = cv2.GC_FGD  # Pasti foreground
            
            # Expand ke area tubuh dengan AMAN
            # Ke atas: rambut (expand 1.5x)
            # Ke bawah: bahu, tubuh (expand 6x)
            # Ke samping: lengan (expand 1.5x)
            expand_x = int(fw * 1.2)
            expand_y_up = int(fh * 1.5)
            expand_y_down = int(fh * 5.5)  # Agak kurang dari sebelumnya
            
            x1_exp = max(0, x - expand_x)
            y1_exp = max(0, y - expand_y_up)
            x2_exp = min(w, x + fw + expand_x)
            y2_exp = min(h, y + fh + expand_y_down)
            
            # Set expanded area sebagai PROBABLE foreground (bukan pasti)
            roi = mask[y1_exp:y2_exp, x1_exp:x2_exp]
            roi[roi == 0] = cv2.GC_PR_FGD
        
        # Set semua background awal
        mask[mask == 0] = cv2.GC_BGD
        
        # Set edges sebagai background pasti (margin lebih kecil)
        margin = 20
        mask[:margin, :] = cv2.GC_BGD
        mask[-margin:, :] = cv2.GC_BGD
        mask[:, :margin] = cv2.GC_BGD
        mask[:, -margin:] = cv2.GC_BGD
        
        # ======================================================================
        # STEP 2: Skin Detection untuk STRENGTHEN foreground
        # ======================================================================
        # Deteksi kulit dengan range yang PRESISI (tidak terlalu luas)
        l_channel = lab[:, :, 0].astype(np.float32)
        a_channel = lab[:, :, 1].astype(np.float32)
        b_channel = lab[:, :, 2].astype(np.float32)
        
        skin_mask = ((l_channel > 50) & (l_channel < 220) &
                     (a_channel > 12) & (a_channel < 45) &
                     (b_channel > 5) & (b_channel < 40)).astype(np.uint8)
        
        # Jika ada skin, strengthen foreground likelihood
        mask[skin_mask > 0] = np.maximum(mask[skin_mask > 0], cv2.GC_PR_FGD)
        
        # ======================================================================
        # STEP 3: Dark Hair/Clothing Detection (tapi HANYA di area probable foreground)
        # ======================================================================
        # Dark areas: gray < 130 (not too aggressive)
        dark_mask = (gray < 130).astype(np.uint8)
        
        # Hanya apply dark mask di area probable atau dekat dengan foreground
        for y in range(h):
            for x in range(w):
                if dark_mask[y, x] > 0 and mask[y, x] == cv2.GC_BGD:
                    # Check if close to any probable/foreground
                    nearby_fg = np.any(mask[max(0,y-30):min(h,y+30), max(0,x-30):min(w,x+30)] >= cv2.GC_PR_FGD)
                    if nearby_fg:
                        mask[y, x] = cv2.GC_PR_FGD
        
        # ======================================================================
        # STEP 4: GrabCut untuk refinement
        # ======================================================================
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        # Multi-pass GrabCut dengan iterasi moderate
        mask_copy = mask.copy()
        cv2.grabCut(bgr, mask_copy, None, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)
        cv2.grabCut(bgr, mask_copy, None, bgd_model, fgd_model, 5, cv2.GC_EVAL)
        
        # Convert GrabCut hasil ke binary
        mask_binary = np.where((mask_copy == cv2.GC_FGD) | (mask_copy == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        
        # ======================================================================
        # STEP 5: Morphological Cleanup (tapi GENTLE, bukan aggressive)
        # ======================================================================
        kernel_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        kernel_m = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_l = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        
        # Close kecil untuk connect area
        mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel_m, iterations=1)
        
        # Open kecil untuk hapus noise
        mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_OPEN, kernel_s, iterations=1)
        
        # ======================================================================
        # STEP 6: Largest Connected Component (pastikan hanya 1 manusia)
        # ======================================================================
        num_labels, labels_im, stats, centroids = cv2.connectedComponentsWithStats(mask_binary, connectivity=8)
        
        if num_labels > 1:
            # Find largest component (exclude background label 0)
            largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            mask_final = (labels_im == largest_label).astype(np.uint8) * 255
        else:
            mask_final = mask_binary.copy()
        
        # ======================================================================
        # STEP 7: Contour refinement (smooth tapi aman)
        # ======================================================================
        contours, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            largest_cnt = max(contours, key=cv2.contourArea)
            
            # Smooth kontour dengan epsilon moderate (tidak terlalu halus)
            epsilon = 0.001 * cv2.arcLength(largest_cnt, True)
            approx = cv2.approxPolyDP(largest_cnt, epsilon, True)
            
            # Create mask dari kontour
            mask_final = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask_final, [approx], 255)
            
            # Add kontour lain yg dekat (bagian terpisah dari tubuh)
            for cnt in contours:
                if cv2.contourArea(cnt) > (h * w) * 0.008:  # Minimal 0.8% area
                    x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
                    center_x = x_c + w_c // 2
                    center_y = y_c + h_c // 2
                    
                    # Check distance to largest contour
                    dist = cv2.pointPolygonTest(largest_cnt, (center_x, center_y), True)
                    if -70 < dist < 0 or dist > 0:  # Dalam area atau touching
                        cv2.fillPoly(mask_final, [cnt], 255)
        
        return mask_final.astype(np.uint8)
    
    def portrait_image_matting(self, img, mask):
        """
        Simple Portrait Image Matting - Just ensure binary mask is clean
        """
        h, w = mask.shape[:2]
        
        # Just return mask as-is, or do minimal cleanup
        # Binary threshold to ensure clean mask
        mask_binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]
        
        # Minimal morphology untuk clean edges
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        return mask_binary.astype(np.uint8)
    
    def advanced_segmentation(self, img, faces):
        """
        Human Semantic Segmentation + Portrait Image Matting untuk hasil yang sangat akurat.
        """
        # Step 1: Human Semantic Segmentation
        mask = self.human_semantic_segmentation(img, faces)
        
        # Step 2: Portrait Image Matting untuk refine edges
        mask_final = self.portrait_image_matting(img, mask)
        
        return mask_final

    def remove_background(self):
        """
        Hapus background dengan presisi tinggi menggunakan rembg (deep learning human matting).
        Hasil PNG transparan (alpha channel), dan jika input grayscale hasil tetap grayscale.
        """
        # Pilih sumber gambar: hasil capture (warna) atau file yang dipilih
        source_img = None
        is_gray_input = False
        if self.selected_source_bgr is not None:
            source_img = self.selected_source_bgr.copy()
            if len(source_img.shape) == 2 or (len(source_img.shape) == 3 and source_img.shape[2] == 1):
                is_gray_input = True
        elif self.gray_frame is not None:
            source_img = self.gray_frame.copy()
            is_gray_input = True
        else:
            self.lbl_status.config(text="Status  : Tidak ada gambar untuk dihapus background-nya!")
            messagebox.showerror("Error", "Tidak ada gambar untuk dihapus background-nya!")
            return

        try:
            # Konversi ke PIL Image (rembg butuh RGB/grayscale)
            if is_gray_input:
                if len(source_img.shape) == 2:
                    pil_img = Image.fromarray(source_img, mode="L")
                else:
                    pil_img = Image.fromarray(source_img[:, :, 0], mode="L")
            else:
                pil_img = Image.fromarray(cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB))
            # Hapus background dengan rembg
            result = remove(pil_img)
            result_arr = np.array(result)
            # Jika hasil RGBA (ada alpha), tampilkan preview transparan
            if result_arr.ndim == 3 and result_arr.shape[2] == 4:
                # Simpan PNG transparan
                self.converted_frame = result_arr
                self.show_image(result_arr)
                self.update_info(result_arr, "Color (No BG, PNG)", "Background dihapus transparan (rembg)")
                self.lbl_status.config(text="Status  : Background dihapus transparan (rembg)")
                messagebox.showinfo("Sukses", "Background berhasil dihapus dengan transparansi (PNG)!")
            elif is_gray_input:
                # Jika input grayscale, hasil tetap grayscale (background = 0)
                if result_arr.ndim == 3 and result_arr.shape[2] == 3:
                    # rembg kadang output 3 channel, ambil channel pertama
                    result_arr = result_arr[:, :, 0]
                self.converted_frame = result_arr
                self.show_image(result_arr, gray=True)
                self.update_info(result_arr, "Grayscale (No BG)", "Background dihapus (rembg, grayscale)")
                self.lbl_status.config(text="Status  : Background dihapus (rembg, grayscale)")
                messagebox.showinfo("Sukses", "Background berhasil dihapus (grayscale)!")
            else:
                # Fallback: tampilkan hasil RGB biasa
                self.converted_frame = result_arr
                self.show_image(result_arr)
                self.update_info(result_arr, "Color (No BG)", "Background dihapus dengan rembg (presisi tinggi)")
                self.lbl_status.config(text="Status  : Background dihapus dengan presisi tinggi (rembg)")
                messagebox.showinfo("Sukses", "Background berhasil dihapus dengan presisi tinggi!")
        except Exception as e:
            self.lbl_status.config(text=f"Status  : Gagal hapus background: {e}")
            messagebox.showerror("Error", f"Gagal hapus background: {e}")




