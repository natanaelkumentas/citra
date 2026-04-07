import json
import os
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox
from core.config import SUPABASE_TABLE_ANALISIS
from services import camera_service, supabase_service, hull_service, image_service


class ConversiHullWindow(tk.Toplevel):
    def __init__(self, parent, drive_folder, use_internal=False, camera_url=None):
        super().__init__(parent)
        self.drive_folder = drive_folder
        os.makedirs(self.drive_folder, exist_ok=True)

        self.use_internal = use_internal
        self.camera_url = camera_url or "http://172.29.241.86:8081/video"

        self.camera = None
        self.is_camera_running = False
        self.last_live_frame = None

        self.source_image = None
        self.result_image = None
        self.current_source_name = "-"
        self.current_metrics = None
        self.current_metrics = None

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
        }
        self.padding = {"outer": 12, "gap": 8, "row": 6}

        self.title("Dashboard Conversi hull")
        self.geometry("1320x760")
        self.configure(bg=self.colors["bg_root"])
        self.minsize(1180, 700)

        self.metric_labels = {}
        self.status_var = tk.StringVar(value="Status: Siap. Pilih Open Drive_Local atau Kamera.")

        self._build_ui()
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
        left_menu = tk.Frame(parent, bg=self.colors["bg_sidebar"], width=190, relief="solid", bd=1)
        left_menu.grid(row=0, column=0, sticky="nsw", padx=(0, self.padding["gap"]))
        left_menu.grid_propagate(False)

        tk.Label(
            left_menu,
            text="CONVERSI HULL",
            bg=self.colors["bg_sidebar"],
            fg=self.colors["fg_primary"],
            font=("Segoe UI", 13, "bold"),
        ).pack(fill="x", padx=12, pady=(14, 10))

        buttons = [
            ("Open Drive_Local", self.open_drive_local),
            ("Halaman Hasil", self.open_result_page),
            ("Kamera", self.handle_camera_button),
        ]

        for text, cmd in buttons:
            tk.Button(
                left_menu,
                text=text,
                command=cmd,
                font=("Segoe UI", 10, "bold"),
                bg=self.colors["bg_sidebar_btn"],
                fg=self.colors["fg_primary"],
                activebackground="#26517F",
                activeforeground=self.colors["fg_primary"],
                width=18,
                relief="raised",
                bd=1,
                cursor="hand2",
            ).pack(fill="x", padx=12, pady=5, ipady=3)

        tk.Label(
            left_menu,
            text=(
                "Kamera:\n"
                "- Klik sekali: mulai live\n"
                "- Klik lagi: capture + deteksi"
            ),
            bg=self.colors["bg_sidebar"],
            fg=self.colors["fg_muted"],
            justify="left",
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=12, pady=(14, 8))

    def _build_main_area(self, parent):
        main = tk.Frame(parent, bg=self.colors["bg_main"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=0)
        main.grid_rowconfigure(1, weight=0)
        main.grid_rowconfigure(2, weight=0)
        main.grid_columnconfigure(0, weight=1)

        preview_wrap = tk.Frame(main, bg=self.colors["bg_main"], height=500)
        preview_wrap.grid(row=0, column=0, sticky="ew", pady=(self.padding["gap"], self.padding["gap"]))
        preview_wrap.grid_propagate(False)
        preview_wrap.grid_rowconfigure(0, weight=1)
        preview_wrap.grid_columnconfigure(0, weight=5, uniform="panel")
        preview_wrap.grid_columnconfigure(1, weight=5, uniform="panel")
        preview_wrap.grid_columnconfigure(2, weight=3, uniform="panel")

        self.original_label = self._make_panel(preview_wrap, 0, "Citra Asal", "Belum ada citra")
        self.result_label = self._make_panel(preview_wrap, 1, "Hasil Convex Hull", "Belum ada hasil")

        desc_box = tk.LabelFrame(
            preview_wrap,
            text="Deskripsi Objek",
            bg=self.colors["bg_desc"],
            fg=self.colors["fg_primary"],
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief="solid",
        )
        desc_box.grid(
            row=0,
            column=2,
            sticky="nsew",
            padx=(self.padding["gap"], 0),
            pady=(self.padding["gap"], 0),
        )
        desc_box.grid_columnconfigure(0, weight=1)

        rows = [
            ("deskripsi", "Deskripsi"),
            ("pixel_objek", "Piksel Objek"),
            ("luas", "Luas"),
            ("panjang", "Panjang"),
            ("lebar", "Lebar"),
            ("perimeter", "Perimeter"),
            ("dispersi", "Dispersi"),
            ("kebulatan", "Kebulatan"),
            ("kerampingan", "Kerampingan"),
        ]
        for key, label_text in rows:
            row = tk.Frame(desc_box, bg=self.colors["bg_desc"])
            row.pack(fill="x", padx=10, pady=4)
            tk.Label(
                row,
                text=f"{label_text:<12}",
                bg=self.colors["bg_desc"],
                fg=self.colors["fg_primary"],
                width=12,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
            ).pack(side="left")
            value = tk.Label(
                row,
                text="-",
                bg=self.colors["bg_desc"],
                fg=self.colors["fg_muted"],
                anchor="w",
                justify="left",
                font=("Segoe UI", 10),
            )
            value.pack(side="left", fill="x", expand=True)
            self.metric_labels[key] = value

        action_row = tk.Frame(main, bg=self.colors["bg_main"])
        action_row.grid(row=1, column=0, sticky="ew", pady=(self.padding["row"], self.padding["row"]))
        for i in range(3):
            action_row.grid_columnconfigure(i, weight=1)

        tk.Button(
            action_row,
            text="Tutup Aplikasi",
            command=self.close,
            bg="#E74C3C",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            activebackground="#C0392B",
            activeforeground="white",
        ).grid(row=0, column=0, padx=(0, 5), sticky="ew", ipady=4)

        tk.Button(
            action_row,
            text="Export ke Excel",
            command=self.export_to_excel,
            bg="#8E44AD",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            activebackground="#7D3C98",
            activeforeground="white",
        ).grid(row=0, column=1, padx=5, sticky="ew", ipady=4)

        tk.Button(
            action_row,
            text="Simpan ke Database",
            command=self.save_to_database,
            bg="#27AE60",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="raised",
            bd=1,
            activebackground="#239B56",
            activeforeground="white",
        ).grid(row=0, column=2, padx=(5, 0), sticky="ew", ipady=4)

        tk.Label(
            main,
            textvariable=self.status_var,
            bg=self.colors["bg_main"],
            fg=self.colors["fg_muted"],
            anchor="w",
            font=("Segoe UI", 10, "italic"),
        ).grid(row=2, column=0, sticky="ew", pady=(2, 0))

        self.original_label.bind("<Configure>", lambda _e: self._refresh_image_panels())
        self.result_label.bind("<Configure>", lambda _e: self._refresh_image_panels())

    def _make_panel(self, parent, col, title, empty_text):
        panel = tk.LabelFrame(
            parent,
            text=title,
            bg=self.colors["bg_panel"],
            fg=self.colors["fg_primary"],
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief="solid",
        )
        panel.grid(
            row=0,
            column=col,
            sticky="nsew",
            padx=(0 if col == 0 else self.padding["gap"], 0),
            pady=(self.padding["gap"], 0),
        )
        panel.grid_propagate(False)

        label = tk.Label(
            panel,
            text=empty_text,
            bg=self.colors["bg_panel_inner"],
            fg=self.colors["fg_primary"],
            anchor="center",
            font=("Segoe UI", 10),
        )
        label.pack(fill="both", expand=True)
        return label

    def set_status(self, text):
        self.status_var.set(f"Status: {text}")

    def open_drive_local(self):
        file_path = filedialog.askopenfilename(
            title="Pilih gambar dari Drive_Local",
            initialdir=self.drive_folder,
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"),
                ("All Files", "*.*"),
            ],
        )
        if not file_path:
            return

        bgr = image_service.imread_unicode(file_path)
        if bgr is None:
            messagebox.showerror("Error", "Gagal membaca file gambar.")
            return

        self._stop_camera()
        self.source_image = bgr
        self.current_source_name = os.path.basename(file_path)
        self._show_bgr_on_label(self.original_label, self.source_image, empty_text="Belum ada citra")
        self.run_convex_hull_detection()
        self.set_status(f"Gambar dibuka: {self.current_source_name}")

    def open_result_page(self):
        if self.is_camera_running and self.last_live_frame is not None:
            self.source_image = self.last_live_frame.copy()
            self.current_source_name = f"capture_hull_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            self._stop_camera()
            self._show_bgr_on_label(self.original_label, self.source_image, empty_text="Belum ada citra")

        if self.source_image is None:
            messagebox.showwarning("Info", "Belum ada citra untuk dianalisis.")
            return

        self.run_convex_hull_detection()
        self.set_status("Halaman hasil diperbarui.")

    def handle_camera_button(self):
        if not self.is_camera_running:
            self.start_camera()
            return
        self._capture_from_camera()

    def start_camera(self):
        try:
            self.camera = camera_service.open_camera(self.use_internal, self.camera_url)
        except Exception as e:
            messagebox.showerror("Error", f"Kamera tidak dapat dibuka: {e}")
            self.camera = None
            return

        self.is_camera_running = True
        self.set_status("Kamera aktif. Klik tombol Kamera lagi untuk capture dan deteksi.")
        self._camera_loop()

    def _camera_loop(self):
        if not self.is_camera_running or self.camera is None:
            return

        ret, frame = self.camera.read()
        if ret and frame is not None:
            self.last_live_frame = frame.copy()
            self._show_bgr_on_label(self.original_label, frame, empty_text="Menunggu kamera...")

        self.after(30, self._camera_loop)

    def _capture_from_camera(self):
        if self.last_live_frame is None:
            messagebox.showwarning("Info", "Belum ada frame kamera.")
            return

        self.source_image = self.last_live_frame.copy()
        self.current_source_name = f"capture_hull_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

        try:
            self.current_source_name = image_service.save_capture(self.drive_folder, self.source_image, prefix="capture_hull")
        except Exception:
            pass

        self._stop_camera()
        self._show_bgr_on_label(self.original_label, self.source_image, empty_text="Belum ada citra")
        self.run_convex_hull_detection()
        self.set_status("Capture kamera berhasil dan convex hull sudah dianalisis.")

    def run_convex_hull_detection(self):
        if self.source_image is None:
            return

        result, metrics = hull_service.compute_convex_hull(self.source_image)
        self.result_image = result
        self.current_metrics = metrics

        self._show_bgr_on_label(self.result_label, self.result_image, empty_text="Belum ada hasil")
        self._update_metric_panel(metrics)

    def _update_metric_panel(self, metrics):
        if not metrics:
            for lbl in self.metric_labels.values():
                lbl.configure(text="-")
            return

        self.metric_labels["deskripsi"].configure(text=metrics.get("deskripsi", "-"))
        self.metric_labels["pixel_objek"].configure(text=str(int(metrics.get("pixel_objek", 0))))
        self.metric_labels["luas"].configure(text=self._format_float(metrics.get("luas", 0.0), 1))
        self.metric_labels["panjang"].configure(text=self._format_float(metrics.get("panjang", 0.0), 0))
        self.metric_labels["lebar"].configure(text=self._format_float(metrics.get("lebar", 0.0), 0))
        self.metric_labels["perimeter"].configure(text=self._format_float(metrics.get("perimeter", 0.0), 6))
        self.metric_labels["dispersi"].configure(text=self._format_float(metrics.get("dispersi", 0.0), 6))
        self.metric_labels["kebulatan"].configure(text=self._format_float(metrics.get("kebulatan", 0.0), 12))
        self.metric_labels["kerampingan"].configure(text=self._format_float(metrics.get("kerampingan", 0.0), 12))

    def _format_float(self, value, decimals):
        try:
            if decimals == 0:
                return str(int(round(float(value))))
            return f"{float(value):.{decimals}f}"
        except Exception:
            return "-"

    def _refresh_image_panels(self):
        if self.source_image is not None and not self.is_camera_running:
            self._show_bgr_on_label(self.original_label, self.source_image, empty_text="Belum ada citra")
        if self.result_image is not None:
            self._show_bgr_on_label(self.result_label, self.result_image, empty_text="Belum ada hasil")

    def _show_bgr_on_label(self, label_widget, bgr_image, empty_text="Belum ada gambar"):
        if bgr_image is None:
            label_widget.configure(image="", text=empty_text)
            label_widget.image = None
            return

        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        target_w = max(320, int(label_widget.winfo_width()))
        target_h = max(220, int(label_widget.winfo_height()))
        resized = self._resize_cover(rgb, target_w, target_h)

        photo = ImageTk.PhotoImage(Image.fromarray(resized))
        label_widget.configure(image=photo, text="")
        label_widget.image = photo

    def _resize_cover(self, rgb_image, target_w, target_h):
        src_h, src_w = rgb_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return rgb_image

        # Cover fill: isi penuh panel tanpa black bar, dengan crop kecil di tepi.
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

    def export_to_excel(self):
        if not self.current_metrics:
            messagebox.showwarning("Info", "Belum ada data analisis untuk diexport.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Simpan Excel",
            initialdir=self.drive_folder,
            initialfile=f"conversi_hull_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not save_path:
            return

        row = {
            "tanggal_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sumber_citra": self.current_source_name,
            "pixel_objek": int(self.current_metrics.get("pixel_objek", 0)),
            "luas": float(self.current_metrics.get("luas", 0.0)),
            "panjang": float(self.current_metrics.get("panjang", 0.0)),
            "lebar": float(self.current_metrics.get("lebar", 0.0)),
            "perimeter": float(self.current_metrics.get("perimeter", 0.0)),
            "dispersi": float(self.current_metrics.get("dispersi", 0.0)),
            "kebulatan": float(self.current_metrics.get("kebulatan", 0.0)),
            "kerampingan": float(self.current_metrics.get("kerampingan", 0.0)),
            "deskripsi": self.current_metrics.get("deskripsi", ""),
        }
        headers = [
            "tanggal_analisis",
            "sumber_citra",
            "pixel_objek",
            "luas",
            "panjang",
            "lebar",
            "perimeter",
            "dispersi",
            "kebulatan",
            "kerampingan",
            "deskripsi",
        ]

        try:
            self.write_simple_xlsx([row], headers, save_path, sheet_name="conversi_hull")
            self.set_status(f"Export Excel berhasil: {os.path.basename(save_path)}")
            messagebox.showinfo("Sukses", f"Data berhasil diexport ke:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menulis Excel:\n{e}")

    def save_to_database(self):
        """Simpan metrik convex hull ke Supabase via supabase_service."""
        if not self.current_metrics:
            messagebox.showwarning("Info", "Belum ada data analisis untuk disimpan.")
            return

        payload = {
            "jumlah_objek":  int(self.current_metrics.get("objek_terdeteksi", 0)),
            "piksel_objek":  int(self.current_metrics.get("pixel_objek", 0)),
            "luas":          float(self.current_metrics.get("luas", 0.0)),
            "panjang":       float(self.current_metrics.get("panjang", 0.0)),
            "lebar":         float(self.current_metrics.get("lebar", 0.0)),
            "perimeter":     float(self.current_metrics.get("perimeter", 0.0)),
            "dispersi":      float(self.current_metrics.get("dispersi", 0.0)),
            "kebulatan":     float(self.current_metrics.get("kebulatan", 0.0)),
            "kerampingan":   float(self.current_metrics.get("kerampingan", 0.0)),
        }

        try:
            supabase_service.insert_record("analisis_objek", payload, prefer_return=False)
            self.set_status("Data berhasil disimpan ke database Supabase.")
            messagebox.showinfo("Sukses", "Data berhasil disimpan ke database Supabase!")
        except Exception as e:
            self.set_status("Gagal menyimpan ke database Supabase.")
            messagebox.showerror("Error", f"Gagal simpan ke Supabase:\n{e}")
            self._save_to_local()

    def _save_to_local(self):
        data = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sumber_citra": self.current_source_name,
            "metrics": self.current_metrics,
        }
        pending_path = os.path.join(self.drive_folder, "conversi_hull_pending_db.jsonl")
        try:
            with open(pending_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            self.set_status("Data disimpan ke antrian lokal sebagai fallback.")
            messagebox.showinfo(
                "Info",
                (
                    "Data disimpan sementara ke file lokal karena gagal ke Supabase.\n\n"
                    f"File: {pending_path}"
                ),
            )
        except Exception as e:
            messagebox.showerror("Error", f"Gagal simpan antrian database lokal:\n{e}")

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
                if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(float(value)):
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
            "</workbook>"
        )
        worksheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{sheet_data}</sheetData>"
            "</worksheet>"
        )
        styles_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
            '<borders count="1"><border/></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
            "</styleSheet>"
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
            "</Types>"
        )
        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
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
            "</Relationships>"
        )

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            zf.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
            zf.writestr("xl/styles.xml", styles_xml)

    def xlsx_column_name(self, index):
        name = ""
        while index > 0:
            index, rem = divmod(index - 1, 26)
            name = chr(65 + rem) + name
        return name

    def _stop_camera(self):
        self.is_camera_running = False
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None

    def close(self):
        self._stop_camera()
        self.destroy()
