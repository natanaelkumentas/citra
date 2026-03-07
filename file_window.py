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

        self.title("Window Buka File")
        self.geometry("1000x700")
        self.configure(bg="#ECF0F1")

        self.setup_ui()
        self.load_images()
        self.protocol("WM_DELETE_WINDOW", self.close)

    # ── UI ──
    def setup_ui(self):
        main_frame = tk.Frame(self, bg="#ECF0F1")
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        tk.Label(
            main_frame,
            text=f"FILE TERSIMPAN ({os.path.basename(self.drive_folder)})",
            font=("Arial", 16, "bold"), bg="#ECF0F1", fg="#2C3E50"
        ).pack(pady=(0, 6))

        container = tk.Frame(main_frame, bg="#ECF0F1")
        container.pack(fill='both', expand=True)

        # ── panel kiri ──
        left_panel = tk.Frame(container, width=260, bg="#ECF0F1")
        left_panel.pack(side='left', fill='y', padx=(0, 8), pady=4)

        tk.Label(left_panel, text="Pilih Foto:", bg="#ECF0F1", anchor='w').pack(fill='x')

        self.listbox = tk.Listbox(left_panel, width=38, height=30)
        self.listbox.pack(side='left', fill='y', pady=6)
        self.listbox.bind('<<ListboxSelect>>', self.on_listbox_select)

        sb = tk.Scrollbar(left_panel, orient='vertical', command=self.listbox.yview)
        sb.pack(side='left', fill='y')
        self.listbox.config(yscrollcommand=sb.set)

        btn_frame_top = tk.Frame(left_panel, bg="#ECF0F1")
        btn_frame_top.pack(fill='x', pady=(4, 8))
        tk.Button(btn_frame_top, text="🔄 Refresh",
                  command=self.load_images, width=10,
                  bg="#3498DB", fg="white").pack(side='left', padx=4)
        tk.Button(btn_frame_top, text="📂 Buka Drive Lokal",
                  command=self.open_local_drive, width=14,
                  bg="#16A085", fg="white").pack(side='left', padx=4)

        # ── panel kanan ──
        right_panel = tk.Frame(container, bg="white", relief="solid", bd=1)
        right_panel.pack(side='right', fill='both', expand=True)

        self.image_frame = tk.Frame(right_panel, bg="white")
        self.image_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.image_label = tk.Label(self.image_frame, bg="white", text="Tidak ada gambar")
        self.image_label.pack(expand=True)

        # ── info bawah ──
        info_box = tk.Frame(self, bg="#ECF0F1", relief='sunken', bd=1)
        info_box.pack(fill='x', padx=10, pady=(6, 4))
        tk.Label(info_box, text="Deskripsi Gambar:",
                 font=("Arial", 10, "bold"), bg="#ECF0F1").pack(anchor='w')
        self.info_label = tk.Label(info_box, text="Informasi: -",
                                   font=("Arial", 10), bg="#ECF0F1",
                                   justify='left', anchor='w')
        self.info_label.pack(fill='x')

        # ── navigasi ──
        nav_frame = tk.Frame(self, bg="#ECF0F1")
        nav_frame.pack(fill='x', padx=10, pady=(4, 8))
        tk.Button(nav_frame, text="◀ Previous",
                  command=self.prev_image, width=12,
                  bg="#95A5A6", fg="white").pack(side='left')
        self.counter_label = tk.Label(nav_frame, text="0 / 0", bg="#ECF0F1")
        self.counter_label.pack(side='left', padx=8)
        tk.Button(nav_frame, text="Next ▶",
                  command=self.next_image, width=12,
                  bg="#95A5A6", fg="white").pack(side='left')

    # ── load & tampil ──
    def load_images(self):
        self.image_files = []
        self.current_image_index = 0
        self.listbox.delete(0, tk.END)

        if os.path.exists(self.drive_folder):
            for f in os.listdir(self.drive_folder):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    self.image_files.append(os.path.join(self.drive_folder, f))
            self.image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        for p in self.image_files:
            self.listbox.insert(tk.END, os.path.basename(p))

        if self.image_files:
            self.show_image()
        else:
            self.show_no_image()

    def show_image(self):
        if not self.image_files:
            self.show_no_image()
            return

        image_path = self.image_files[self.current_image_index]
        try:
            pil_image = Image.open(image_path).convert('RGB')
            ow, oh = pil_image.size

            ratio = min(700 / ow, 500 / oh, 1.0)
            pil_resized = pil_image.resize((int(ow * ratio), int(oh * ratio)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(pil_resized)

            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo

            jenis = detect_image_type(pil_image)
            fname = os.path.basename(image_path)
            info = (
                f"Nama File : {fname}\n"
                f"Resolusi  : {ow} x {oh} px\n"
                f"Ukuran    : {format_file_size(os.path.getsize(image_path))}\n"
                f"Tipe      : {os.path.splitext(fname)[1].lstrip('.')}\n"
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
            font=("Arial", 12), fg="#7F8C8D"
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

    def open_local_drive(self):
        try:
            if not os.path.exists(self.drive_folder):
                os.makedirs(self.drive_folder)
            if os.name == 'nt':
                os.startfile(self.drive_folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.drive_folder])
            else:
                subprocess.Popen(['xdg-open', self.drive_folder])
        except Exception as e:
            print(f"Gagal membuka folder lokal: {e}")

    def close(self):
        self.destroy()


