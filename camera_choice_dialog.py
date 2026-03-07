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

class CameraChoiceDialog(tk.Toplevel):
    def __init__(self, parent, mode='save', callback=None):
        super().__init__(parent)
        self.callback = callback
        self.mode = mode
        self.title("Pilih Kamera")
        self.geometry("480x180")
        self.configure(bg="#F4F6F7")
        self.resizable(False, False)

        self.selection = tk.StringVar(value='internal')
        self.ip_url = tk.StringVar(value="http://172.29.241.86:8081/video")

        tk.Label(self, text="Pilih sumber kamera:",
                 font=("Arial", 12, "bold"), bg="#F4F6F7").pack(pady=(10, 5))

        rb_frame = tk.Frame(self, bg="#F4F6F7")
        rb_frame.pack(pady=5)
        tk.Radiobutton(rb_frame, text="Kamera Internal (Laptop)",
                       variable=self.selection, value='internal',
                       bg="#F4F6F7").pack(anchor='w', padx=10)
        tk.Radiobutton(rb_frame, text="Kamera External (HP – IP Camera)",
                       variable=self.selection, value='external',
                       bg="#F4F6F7").pack(anchor='w', padx=10)

        url_frame = tk.Frame(self, bg="#F4F6F7")
        url_frame.pack(pady=8, fill='x', padx=10)
        tk.Label(url_frame, text="IP Camera URL:", bg="#F4F6F7").pack(side='left')
        self.url_entry = tk.Entry(url_frame, textvariable=self.ip_url, width=40)
        self.url_entry.pack(side='left', padx=5)

        def on_radio_change(*_):
            self.url_entry.configure(
                state='disabled' if self.selection.get() == 'internal' else 'normal'
            )
        self.selection.trace_add('write', on_radio_change)
        on_radio_change()

        btn_frame = tk.Frame(self, bg="#F4F6F7")
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Open", width=12, command=self.on_open).pack(side='left', padx=8)
        tk.Button(btn_frame, text="Cancel", width=12, command=self.destroy).pack(side='left', padx=8)

        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def on_open(self):
        use_internal = (self.selection.get() == 'internal')
        url = None if use_internal else self.ip_url.get().strip()
        if self.callback:
            try:
                self.callback(use_internal, url)
            except Exception as e:
                print(f"Callback error: {e}")
        self.destroy()



