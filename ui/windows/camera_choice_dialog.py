# ui/windows/camera_choice_dialog.py — Dialog pemilihan sumber kamera
# Update import path dari flat ke struktur baru.
# Isi class tidak berubah sama sekali.

import tkinter as tk
from tkinter import ttk


class CameraChoiceDialog(tk.Toplevel):
    def __init__(self, parent, mode='save', callback=None):
        super().__init__(parent)
        self.callback = callback
        self.mode = mode

        # ── Theme colors ──
        self.colors = {
            "bg_root":          "#0B1D36",
            "bg_panel":         "#112A46",
            "bg_input":         "#0F2A48",
            "fg_primary":       "#EAF2FF",
            "fg_muted":         "#B8CBE2",
            "accent_blue":      "#2D9CDB",
            "accent_green":     "#27AE60",
            "btn_cancel":       "#4A5568",
            "btn_cancel_hover": "#5A6578",
            "border":           "#1E3A5F",
        }

        self.title("Pilih Kamera")
        self.geometry("520x280")
        self.configure(bg=self.colors["bg_root"])
        self.resizable(False, False)

        self.selection = tk.StringVar(value='internal')
        self.ip_url    = tk.StringVar(value="http://172.29.241.86:8081/video")

        # ── Main container ──
        main = tk.Frame(self, bg=self.colors["bg_root"])
        main.pack(fill="both", expand=True, padx=20, pady=15)

        # ── Header ──
        header = tk.Frame(main, bg=self.colors["bg_root"])
        header.pack(fill="x", pady=(0, 12))

        tk.Label(header, text="📷", font=("Segoe UI", 20),
                 bg=self.colors["bg_root"], fg=self.colors["fg_primary"]).pack(side="left", padx=(0, 10))

        header_text = tk.Frame(header, bg=self.colors["bg_root"])
        header_text.pack(side="left")
        tk.Label(header_text, text="Pilih Sumber Kamera",
                 font=("Segoe UI", 14, "bold"),
                 bg=self.colors["bg_root"], fg=self.colors["fg_primary"]).pack(anchor="w")
        tk.Label(header_text, text="Pilih kamera internal atau external untuk memulai",
                 font=("Segoe UI", 9),
                 bg=self.colors["bg_root"], fg=self.colors["fg_muted"]).pack(anchor="w")

        # ── Divider ──
        tk.Frame(main, bg=self.colors["border"], height=1).pack(fill="x", pady=(0, 12))

        # ── Radio buttons panel ──
        radio_panel = tk.Frame(main, bg=self.colors["bg_panel"], bd=1, relief="solid",
                               highlightbackground=self.colors["border"], highlightthickness=1)
        radio_panel.pack(fill="x", pady=(0, 10))

        # Internal camera option
        internal_row = tk.Frame(radio_panel, bg=self.colors["bg_panel"])
        internal_row.pack(fill="x", padx=15, pady=(10, 3))
        self.rb_internal = tk.Radiobutton(
            internal_row, text="💻  Kamera Internal (Laptop)",
            variable=self.selection, value='internal',
            bg=self.colors["bg_panel"], fg=self.colors["fg_primary"],
            selectcolor=self.colors["bg_input"],
            activebackground=self.colors["bg_panel"],
            activeforeground=self.colors["fg_primary"],
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        )
        self.rb_internal.pack(anchor="w")

        # External camera option
        external_row = tk.Frame(radio_panel, bg=self.colors["bg_panel"])
        external_row.pack(fill="x", padx=15, pady=(3, 5))
        self.rb_external = tk.Radiobutton(
            external_row, text="📱  Kamera External (HP – IP Camera)",
            variable=self.selection, value='external',
            bg=self.colors["bg_panel"], fg=self.colors["fg_primary"],
            selectcolor=self.colors["bg_input"],
            activebackground=self.colors["bg_panel"],
            activeforeground=self.colors["fg_primary"],
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        )
        self.rb_external.pack(anchor="w")

        # ── IP Camera URL input ──
        url_row = tk.Frame(radio_panel, bg=self.colors["bg_panel"])
        url_row.pack(fill="x", padx=15, pady=(2, 12))
        tk.Label(url_row, text="IP Camera URL:",
                 font=("Segoe UI", 9, "bold"),
                 bg=self.colors["bg_panel"], fg=self.colors["fg_muted"]).pack(side="left", padx=(22, 8))
        self.url_entry = tk.Entry(
            url_row, textvariable=self.ip_url, width=35,
            font=("Segoe UI", 10),
            bg=self.colors["bg_input"], fg=self.colors["fg_primary"],
            insertbackground="white", bd=1, relief="solid",
            highlightcolor=self.colors["accent_blue"], highlightthickness=1,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # ── Radio change handler ──
        def on_radio_change(*_):
            if self.selection.get() == 'internal':
                self.url_entry.configure(state='disabled', bg="#1A2F4A")
            else:
                self.url_entry.configure(state='normal', bg=self.colors["bg_input"])
        self.selection.trace_add('write', on_radio_change)
        on_radio_change()

        # ── Buttons ──
        btn_frame = tk.Frame(main, bg=self.colors["bg_root"])
        btn_frame.pack(fill="x", pady=(5, 0))

        tk.Button(btn_frame, text="Cancel", width=14, command=self.destroy,
                  font=("Segoe UI", 10, "bold"),
                  bg=self.colors["btn_cancel"], fg=self.colors["fg_primary"],
                  activebackground=self.colors["btn_cancel_hover"],
                  activeforeground="white", bd=1, relief="raised", cursor="hand2",
                  ).pack(side="right", padx=(8, 0))

        tk.Button(btn_frame, text="✅ Open", width=14, command=self.on_open,
                  font=("Segoe UI", 10, "bold"),
                  bg=self.colors["accent_blue"], fg="white",
                  activebackground="#2488C2", activeforeground="white",
                  bd=1, relief="raised", cursor="hand2",
                  ).pack(side="right")

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
