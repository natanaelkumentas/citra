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
from utils_image import detect_image_type, format_file_size

class FileWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, gdrive_link):
        super().__init__(parent)
        self.drive_folder = drive_folder
        self.gdrive_link = gdrive_link
        self.current_image_index = 0
        self.image_files = []

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
            "accent_teal": "#16A085"
        }

        self.title("Window Buka File - Riwayat Citra")
        self.geometry("1400x850")
        self.configure(bg=self.colors["bg_root"])
        try:
            self.state("zoomed")
        except:
            pass

        self.setup_ui()
        self.load_images()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ── UI ──
    def setup_ui(self):
        root_container = tk.Frame(self, bg=self.colors["bg_root"])
        root_container.pack(fill="both", expand=True, padx=15, pady=15)

        # ── Title ──
        tk.Label(
            root_container, text="RIWAYAT CITRA TERSIMPAN (Drive Local)",
            font=("Segoe UI", 18, "bold"), bg=self.colors["bg_root"], fg=self.colors["fg_primary"]
        ).pack(pady=(0, 12))

        # ── Main Content Grid ──
        main_grid = tk.Frame(root_container, bg=self.colors["bg_root"])
        main_grid.pack(fill="both", expand=True)
        main_grid.grid_columnconfigure(0, weight=1, minsize=400) # Left Panel lega
        main_grid.grid_columnconfigure(1, weight=2)              # Preview Area dikurangi weight-nya agar tidak terlalu lebar
        main_grid.grid_rowconfigure(0, weight=1)

        # ── Panel Kiri: List & Control ──
        left_panel = tk.LabelFrame(
            main_grid, text="Daftar File", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["accent_blue"], relief="solid", bd=1
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Tools Top
        tool_frame = tk.Frame(left_panel, bg=self.colors["bg_main"])
        tool_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(tool_frame, text="🔄 Refresh", command=self.load_images,
                  font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="white",
                  bd=0, cursor="hand2", width=10).pack(side="left", padx=2)
        
        tk.Button(tool_frame, text="📂 Buka Folder", command=self.open_local_drive,
                  font=("Segoe UI", 9, "bold"), bg=self.colors["accent_teal"], fg="white",
                  bd=0, cursor="hand2", width=12).pack(side="left", padx=2)

        # Listbox with dark theme
        list_container = tk.Frame(left_panel, bg=self.colors["bg_panel_inner"])
        list_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.listbox = tk.Listbox(
            list_container, font=("Segoe UI", 10), bg=self.colors["bg_panel_inner"], 
            fg=self.colors["fg_primary"], selectbackground=self.colors["accent_blue"],
            selectforeground="white", bd=0, highlightthickness=0, activestyle="none"
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        sb = ttk.Scrollbar(list_container, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        # ── Panel Kanan: Preview & Info ──
        right_panel = tk.Frame(main_grid, bg=self.colors["bg_root"])
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=3) # Preview
        right_panel.grid_rowconfigure(1, weight=1) # Info
        right_panel.grid_columnconfigure(0, weight=1) # Biar box-nya melebar penuh ke kanan

        # Preview Area - Flexible but constrained visually
        preview_box = tk.LabelFrame(
            right_panel, text="Pratinjau Citra", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["accent_blue"], relief="solid", bd=1,
            height=720 
        )
        preview_box.grid(row=0, column=0, sticky="nsew", pady=(0, 5)) 
        preview_box.grid_propagate(False)

        self.image_frame = tk.Frame(preview_box, bg=self.colors["bg_panel_inner"])
        self.image_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.image_frame.pack_propagate(False)

        self.image_label = tk.Label(self.image_frame, bg=self.colors["bg_panel_inner"], text="Memuat Gambar...", fg=self.colors["fg_muted"])
        self.image_label.pack(expand=True, fill="both")

        # Info Box (Statistik)
        info_box = tk.LabelFrame(
            right_panel, text="Informasi Berkas", font=("Segoe UI", 11, "bold"),
            bg=self.colors["bg_main"], fg=self.colors["fg_primary"], relief="solid", bd=1
        )
        info_box.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        
        self.info_label = tk.Label(
            info_box, text="Informasi: -", font=("Segoe UI", 10), 
            bg=self.colors["bg_main"], fg=self.colors["fg_muted"],
            justify="left", anchor="nw", padx=15, pady=10
        )
        self.info_label.pack(fill="both", expand=True)

        # ── Navigasi & Action ──
        bottom_bar = tk.Frame(root_container, bg=self.colors["bg_root"])
        bottom_bar.pack(fill="x", pady=(15, 0))

        # Nav Buttons
        nav_wrap = tk.Frame(bottom_bar, bg=self.colors["bg_root"])
        nav_wrap.pack(side="left")

        tk.Button(nav_wrap, text="◀ SEBELUMNYA", command=self.prev_image,
                  font=("Segoe UI", 9, "bold"), bg=self.colors["bg_panel"], fg="white",
                  width=15, bd=1, relief="flat", cursor="hand2").pack(side="left", padx=2)
        
        self.counter_label = tk.Label(nav_wrap, text="0 / 0", font=("Segoe UI", 10, "bold"), 
                                      bg=self.colors["bg_root"], fg=self.colors["accent_blue"], width=10)
        self.counter_label.pack(side="left", padx=10)

        tk.Button(nav_wrap, text="SELANJUTNYA ▶", command=self.next_image,
                  font=("Segoe UI", 9, "bold"), bg=self.colors["bg_panel"], fg="white",
                  width=15, bd=1, relief="flat", cursor="hand2").pack(side="left", padx=2)

        # Close Button
        tk.Button(bottom_bar, text="❌ TUTUP JENDELA", command=self.close,
                  font=("Segoe UI", 9, "bold"), bg=self.colors["accent_red"], fg="white",
                  width=18, bd=1, relief="raised", cursor="hand2").pack(side="right")

    # ── load & tampil ──
    def load_images(self):
        self.image_files = []
        self.current_image_index = 0
        self.listbox.delete(0, tk.END)

        if os.path.exists(self.drive_folder):
            current_files = []
            for f in os.listdir(self.drive_folder):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    current_files.append(os.path.join(self.drive_folder, f))
            
            # Sort after fetching all files
            current_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            self.image_files = current_files

        for p in self.image_files:
            self.listbox.insert(tk.END, os.path.basename(p))

        # Ensure counter and UI update correctly even if empty
        self.counter_label.configure(
            text=f"{len(self.image_files) if self.image_files else 0} berkas"
        )

        if self.image_files:
            self.current_image_index = 0
            self.show_image()
        else:
            self.show_no_image()

    def show_image(self):
        if not self.image_files:
            self.show_no_image()
            return

        if self.current_image_index >= len(self.image_files):
            self.current_image_index = 0
            
        image_path = self.image_files[self.current_image_index]
        try:
            pil_image = Image.open(image_path).convert('RGB')
            
            # Use improved resizing for interactive feel
            self.image_frame.update_idletasks()
            # Gunakan resolusi target yang ideal untuk 4:3 atau 16:9 tanpa maksa melebar
            tw = self.image_frame.winfo_width()
            th = self.image_frame.winfo_height()
            
            if tw < 100 or th < 100: # Failsafe if not rendered yet
                tw, th = 960, 720

            cv_img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            rendered_cv = self._resize_fit(cv_img, tw, th) # Pakai FIT agar foto terlihat FULL
            rendered_rgb = cv2.cvtColor(rendered_cv, cv2.COLOR_BGR2RGB)
            
            photo = ImageTk.PhotoImage(Image.fromarray(rendered_rgb))

            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo

            jenis = detect_image_type(pil_image)
            fname = os.path.basename(image_path)
            info = (
                f"Nama File : {fname}\n"
                f"Resolusi  : {pil_image.size[0]} x {pil_image.size[1]} px  |  "
                f"Ukuran    : {format_file_size(os.path.getsize(image_path))}  |  "
                f"Tipe      : {os.path.splitext(fname)[1].lstrip('.').upper()}  |  "
                f"Jenis     : {jenis}"
            )
            self.info_label.configure(text=info)
            self.counter_label.configure(
                text=f"{self.current_image_index + 1} / {len(self.image_files)}"
            )
            try:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(self.current_image_index)
                self.listbox.see(self.current_image_index)
            except Exception:
                pass
        except Exception as e:
            print(f"Error membuka gambar: {e}")
            self.show_no_image()

    def show_no_image(self):
        self.image_label.configure(
            image="", text="Tidak ada gambar tersimpan\n\nGunakan Window Kamera untuk mengambil foto",
            font=("Segoe UI", 12), bg=self.colors["bg_panel_inner"], fg=self.colors["fg_muted"]
        )
        self.image_label.image = None
        self.info_label.configure(text="Informasi: -")
        self.counter_label.configure(text="0 / 0")

    def prev_image(self):
        if not self.image_files:
            return
        self.current_image_index = (self.current_image_index - 1) % len(self.image_files)
        self.show_image()

    def next_image(self):
        if not self.image_files:
            return
        self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
        self.show_image()

    def on_listbox_select(self, evt):
        if not self.image_files:
            return
        sel = evt.widget.curselection()
        if not sel:
            return
        self.current_image_index = int(sel[0])
        self.show_image()

    def _resize_fit(self, cv_image, target_w, target_h):
        """Resizing dengan metode FIT agar seluruh gambar terlihat (dengan filler)"""
        src_h, src_w = cv_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return cv_image

        ratio = min(target_w / float(src_w), target_h / float(src_h))
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        
        interp = cv2.INTER_CUBIC if ratio > 1.0 else cv2.INTER_AREA
        resized = cv2.resize(cv_image, (new_w, new_h), interpolation=interp)

        # Buat canvas kosong dengan warna background panel
        # Konversi hex ke BGR
        bg_hex = self.colors["bg_panel_inner"].lstrip('#')
        bg_bgr = tuple(int(bg_hex[i:i+2], 16) for i in (4, 2, 0)) # RGB -> BGR
        
        canvas = np.full((target_h, target_w, 3), bg_bgr, dtype=np.uint8)

        # Tempel gambar di tengah canvas
        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized

        return canvas

    def _resize_cover(self, cv_image, target_w, target_h):
        """Metode COVER: Gambar mengisi penuh area (crop jika perlu)"""
        src_h, src_w = cv_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return cv_image

        ratio = max(target_w / float(src_w), target_h / float(src_h))
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        
        interp = cv2.INTER_CUBIC if ratio > 1.0 else cv2.INTER_AREA
        resized = cv2.resize(cv_image, (new_w, new_h), interpolation=interp)

        x0 = (new_w - target_w) // 2
        y0 = (new_h - target_h) // 2
        x1 = x0 + target_w
        y1 = y0 + target_h

        return resized[y0:y1, x0:x1]

    def open_local_drive(self):
        """Membuka folder penyimpanan di File Explorer"""
        try:
            folder = os.path.abspath(self.drive_folder)
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            if sys.platform == 'win32':
                os.startfile(folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder])
            else:
                subprocess.Popen(['xdg-open', folder])
        except Exception as e:
            print(f"Gagal membuka folder lokal: {e}")
            messagebox.showerror("Error", f"Tidak bisa membuka folder: {e}")

    def close(self):
        self.destroy()


