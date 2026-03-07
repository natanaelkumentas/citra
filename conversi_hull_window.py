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
try:
    from rembg import remove as rembg_remove
except Exception:
    rembg_remove = None


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
        self.rembg_enabled = rembg_remove is not None

        self.face_cascade = self._load_cascade("haarcascade_frontalface_default.xml")
        self.face_alt_cascade = self._load_cascade("haarcascade_frontalface_alt2.xml")

        self.title("Dashboard Conversi hull")
        self.geometry("1380x820")
        self.configure(bg="#ECF0F1")

        self.metric_labels = {}
        self.status_var = tk.StringVar(value="Status: Siap. Pilih Open Drive_Local atau Kamera.")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        root = tk.Frame(self, bg="#ECF0F1")
        root.pack(fill="both", expand=True, padx=10, pady=10)
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        self._build_left_menu(root)
        self._build_main_area(root)

    def _build_left_menu(self, parent):
        left_menu = tk.Frame(parent, bg="#1F2D3D", width=200, relief="solid", bd=2)
        left_menu.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        left_menu.grid_propagate(False)

        tk.Label(
            left_menu,
            text="CONVERSI HULL",
            bg="#1F2D3D",
            fg="white",
            font=("Arial", 12, "bold"),
        ).pack(fill="x", padx=8, pady=(12, 8))

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
                font=("Arial", 10, "bold"),
                bg="#ECF0F1",
                fg="#111111",
                width=18,
                relief="raised",
                bd=2,
                cursor="hand2",
            ).pack(fill="x", padx=12, pady=6)

        tk.Label(
            left_menu,
            text=(
                "Kamera:\n"
                "- Klik sekali: mulai live\n"
                "- Klik lagi: capture + deteksi"
            ),
            bg="#1F2D3D",
            fg="#D5DBDB",
            justify="left",
            anchor="w",
            font=("Arial", 9),
        ).pack(fill="x", padx=12, pady=(14, 8))

    def _build_main_area(self, parent):
        main = tk.Frame(parent, bg="#ECF0F1")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=4, uniform="panel")
        main.grid_columnconfigure(1, weight=4, uniform="panel")
        main.grid_columnconfigure(2, weight=3, uniform="panel")

        self.original_label = self._make_panel(main, 0, "Citra Asal", "Belum ada citra")
        self.result_label = self._make_panel(main, 1, "Hasil Convex Hull", "Belum ada hasil")

        desc_box = tk.LabelFrame(
            main,
            text="Deskripsi Objek",
            bg="#D0D3D4",
            fg="#111111",
            font=("Arial", 11, "bold"),
            bd=2,
            relief="solid",
        )
        desc_box.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        desc_box.grid_columnconfigure(0, weight=1)

        rows = [
            ("deskripsi", "Deskripsi"),
            ("luas", "Luas"),
            ("panjang", "Panjang"),
            ("lebar", "Lebar"),
            ("perimeter", "Perimeter"),
            ("dispersi", "Dispersi"),
            ("kebulatan", "Kebulatan"),
            ("kerampingan", "Kerampingan"),
        ]
        for key, label_text in rows:
            row = tk.Frame(desc_box, bg="#D0D3D4")
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(
                row,
                text=f"{label_text:<12}",
                bg="#D0D3D4",
                fg="#111111",
                width=12,
                anchor="w",
                font=("Arial", 10, "bold"),
            ).pack(side="left")
            value = tk.Label(
                row,
                text="-",
                bg="#D0D3D4",
                fg="#111111",
                anchor="w",
                justify="left",
                font=("Arial", 10),
            )
            value.pack(side="left", fill="x", expand=True)
            self.metric_labels[key] = value

        action_row = tk.Frame(main, bg="#ECF0F1")
        action_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        for i in range(3):
            action_row.grid_columnconfigure(i, weight=1)

        tk.Button(
            action_row,
            text="Tutup Aplikasi",
            command=self.close,
            bg="#E74C3C",
            fg="white",
            font=("Arial", 10, "bold"),
            relief="raised",
            bd=2,
        ).grid(row=0, column=0, padx=4, sticky="ew")

        tk.Button(
            action_row,
            text="Export ke Excel",
            command=self.export_to_excel,
            bg="#8E44AD",
            fg="white",
            font=("Arial", 10, "bold"),
            relief="raised",
            bd=2,
        ).grid(row=0, column=1, padx=4, sticky="ew")

        tk.Button(
            action_row,
            text="Simpan ke Database",
            command=self.save_to_database,
            bg="#27AE60",
            fg="white",
            font=("Arial", 10, "bold"),
            relief="raised",
            bd=2,
        ).grid(row=0, column=2, padx=4, sticky="ew")

        tk.Label(
            main,
            textvariable=self.status_var,
            bg="#ECF0F1",
            fg="#2C3E50",
            anchor="w",
            font=("Arial", 10, "italic"),
        ).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        self.original_label.bind("<Configure>", lambda _e: self._refresh_image_panels())
        self.result_label.bind("<Configure>", lambda _e: self._refresh_image_panels())

    def _make_panel(self, parent, col, title, empty_text):
        panel = tk.LabelFrame(
            parent,
            text=title,
            bg="#D0D3D4",
            fg="#111111",
            font=("Arial", 11, "bold"),
            bd=2,
            relief="solid",
        )
        panel.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
        panel.grid_propagate(False)

        label = tk.Label(
            panel,
            text=empty_text,
            bg="black",
            fg="white",
            anchor="center",
            font=("Arial", 10),
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

        bgr = self._imread_unicode(file_path)
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
        source = 0 if self.use_internal else self.camera_url
        self.camera = cv2.VideoCapture(source)

        if (not self.use_internal) and isinstance(self.camera_url, str) and self.camera_url.isdigit():
            self.camera.release()
            self.camera = cv2.VideoCapture(int(self.camera_url))

        if self.camera is None or not self.camera.isOpened():
            messagebox.showerror("Error", "Kamera tidak dapat dibuka.")
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
            save_path = os.path.join(self.drive_folder, self.current_source_name)
            cv2.imwrite(save_path, self.source_image)
        except Exception:
            pass

        self._stop_camera()
        self._show_bgr_on_label(self.original_label, self.source_image, empty_text="Belum ada citra")
        self.run_convex_hull_detection()
        self.set_status("Capture kamera berhasil dan convex hull sudah dianalisis.")

    def run_convex_hull_detection(self):
        if self.source_image is None:
            return

        result, metrics = self._analyze_convex_hull(self.source_image)
        self.result_image = result
        self.current_metrics = metrics

        self._show_bgr_on_label(self.result_label, self.result_image, empty_text="Belum ada hasil")
        self._update_metric_panel(metrics)

    def _load_cascade(self, filename):
        try:
            path = os.path.join(cv2.data.haarcascades, filename)
            if os.path.exists(path):
                return cv2.CascadeClassifier(path)
        except Exception:
            pass
        return None

    def _normalize_bgr(self, image):
        if image is None or image.size == 0:
            return None
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.ndim == 3 and image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image.copy()

    def _crop_active_region(self, bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        active = cv2.inRange(gray, 12, 255)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        active = cv2.morphologyEx(active, cv2.MORPH_CLOSE, kernel, iterations=2)
        points = cv2.findNonZero(active)
        if points is None:
            return bgr, 0, 0

        x, y, w, h = cv2.boundingRect(points)
        area_ratio = (w * h) / float(max(1, bgr.shape[0] * bgr.shape[1]))
        if area_ratio < 0.20:
            return bgr, 0, 0

        return bgr[y:y + h, x:x + w].copy(), x, y

    def _detect_faces(self, gray):
        faces_all = []
        for cascade in (self.face_cascade, self.face_alt_cascade):
            if cascade is None:
                continue
            try:
                faces = cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.08,
                    minNeighbors=5,
                    minSize=(60, 60),
                )
                for f in faces:
                    faces_all.append(tuple(int(v) for v in f))
            except Exception:
                continue

        if not faces_all:
            return []

        dedup = []
        for f in faces_all:
            keep = True
            for prev in dedup:
                if self._box_iou(f, prev) > 0.35:
                    keep = False
                    break
            if keep:
                dedup.append(f)
        return dedup

    def _build_person_mask(self, bgr):
        h, w = bgr.shape[:2]
        person_mask = np.zeros((h, w), dtype=np.uint8)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        faces = self._detect_faces(gray)

        for x, y, fw, fh in faces:
            ex = max(0, int(x - 0.35 * fw))
            ey = max(0, int(y - 0.25 * fh))
            ex2 = min(w, int(x + 1.35 * fw))
            ey2 = min(h, int(y + 2.35 * fh))
            cv2.rectangle(person_mask, (ex, ey), (ex2, ey2), 255, -1)

        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        skin_ycrcb = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        skin_hsv = cv2.inRange(hsv, (0, 20, 20), (30, 255, 255))
        skin = cv2.bitwise_and(skin_ycrcb, skin_hsv)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, kernel, iterations=1)
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, kernel, iterations=2)

        if faces:
            skin = cv2.dilate(skin, kernel, iterations=2)
            person_mask = cv2.bitwise_or(person_mask, skin)

        person_mask = cv2.dilate(person_mask, kernel, iterations=2)
        return person_mask, faces

    def _extract_rembg_mask(self, bgr):
        if not self.rembg_enabled or rembg_remove is None:
            return None
        try:
            ok, encoded = cv2.imencode(".png", bgr)
            if not ok:
                return None

            mask_raw = rembg_remove(encoded.tobytes(), only_mask=True)
            if isinstance(mask_raw, bytes):
                arr = np.frombuffer(mask_raw, dtype=np.uint8)
                mask = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
            else:
                mask = np.array(mask_raw)

            if mask is None or mask.size == 0:
                return None
            if mask.ndim == 3 and mask.shape[2] == 4:
                mask = mask[:, :, 3]
            elif mask.ndim == 3:
                mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

            if mask.shape[:2] != bgr.shape[:2]:
                mask = cv2.resize(mask, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

            _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            return mask
        except Exception:
            # Disable repeated failed calls to keep UI responsive.
            self.rembg_enabled = False
            return None

    def _build_candidate_masks(self, bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        masks = []

        rembg_mask = self._extract_rembg_mask(bgr)
        if rembg_mask is not None:
            fg_ratio = float(np.count_nonzero(rembg_mask)) / float(rembg_mask.size)
            if 0.005 <= fg_ratio <= 0.95:
                masks.append(("rembg", rembg_mask))

        _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        masks.append(("otsu", otsu))
        masks.append(("otsu_inv", cv2.bitwise_not(otsu)))

        adaptive = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 5
        )
        masks.append(("adaptive", adaptive))

        edges = cv2.Canny(blur, 35, 135)
        edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, edge_kernel, iterations=1)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, edge_kernel, iterations=2)
        masks.append(("edges", edges))

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        _, sat_otsu = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        masks.append(("saturation", sat_otsu))

        return masks

    def _analyze_convex_hull(self, bgr):
        image_bgr = self._normalize_bgr(bgr)
        if image_bgr is None:
            return bgr, None

        work_bgr, off_x, off_y = self._crop_active_region(image_bgr)
        person_mask, faces = self._build_person_mask(work_bgr)
        candidates = self._detect_candidate_contours(work_bgr, person_mask, faces)
        selected = self._nms_candidates(candidates, iou_threshold=0.45, max_keep=5)

        if not selected:
            empty_result = image_bgr.copy()
            cv2.putText(
                empty_result,
                "Objek presisi tidak terdeteksi",
                (20, 36),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
            return empty_result, {
                "deskripsi": "Objek presisi tidak terdeteksi",
                "luas": 0.0,
                "panjang": 0.0,
                "lebar": 0.0,
                "perimeter": 0.0,
                "dispersi": 0.0,
                "kebulatan": 0.0,
                "kerampingan": 0.0,
                "objek_terdeteksi": 0,
            }

        best = selected[0]
        primary_hull = best["hull"]
        area = float(cv2.contourArea(primary_hull))
        perimeter = float(cv2.arcLength(primary_hull, True))
        x, y, w, h = best["bbox"]
        panjang = float(max(w, h))
        lebar = float(min(w, h))
        dispersi = float((perimeter * perimeter) / area) if area > 0 else 0.0
        kebulatan = float((4.0 * np.pi * area) / (perimeter * perimeter)) if perimeter > 0 else 0.0
        kerampingan = float(panjang / lebar) if lebar > 0 else 0.0

        result = image_bgr.copy()
        offset = np.array([[[off_x, off_y]]], dtype=np.int32)
        for idx, cand in enumerate(selected):
            hull_global = (cand["hull"] + offset).astype(np.int32)
            color = (60, 220, 70) if idx == 0 else (20, 170, 220)
            thickness = 3 if idx == 0 else 2
            cv2.drawContours(result, [hull_global], -1, color, thickness)

        gx, gy = x + off_x, y + off_y
        cv2.rectangle(result, (gx, gy), (gx + w, gy + h), (40, 40, 240), 2)
        cv2.putText(
            result,
            f"Objek: {len(selected)}",
            (max(12, gx), max(24, gy - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        metrics = {
            "deskripsi": f"Objek presisi: {len(selected)} (metrik objek utama)",
            "luas": area,
            "panjang": panjang,
            "lebar": lebar,
            "perimeter": perimeter,
            "dispersi": dispersi,
            "kebulatan": kebulatan,
            "kerampingan": kerampingan,
            "objek_terdeteksi": len(selected),
        }
        return result, metrics

    def _detect_candidate_contours(self, bgr, person_mask, faces):
        h, w = bgr.shape[:2]
        img_area = float(h * w)
        min_area = max(1300.0, img_area * 0.0028)
        max_area = img_area * 0.72

        masks = self._build_candidate_masks(bgr)
        candidates = []
        for source, mask in masks:
            candidates.extend(
                self._extract_valid_contours(
                    mask=mask,
                    min_area=min_area,
                    max_area=max_area,
                    width=w,
                    height=h,
                    person_mask=person_mask,
                    faces=faces,
                    source_name=source,
                )
            )
        return candidates

    def _extract_valid_contours(
        self,
        mask,
        min_area,
        max_area,
        width,
        height,
        person_mask,
        faces,
        source_name,
    ):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = []
        margin = 2

        for c in contours:
            area = float(cv2.contourArea(c))
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(c)
            if w < 18 or h < 18:
                continue

            rect_area = float(w * h)
            if rect_area <= 0:
                continue

            aspect = w / float(max(1, h))
            if aspect < 0.18 or aspect > 5.5:
                continue

            hull = cv2.convexHull(c)
            hull_area = float(cv2.contourArea(hull))
            if hull_area <= 1.0:
                continue
            solidity = area / hull_area
            if solidity < 0.18:
                continue

            extent = area / rect_area
            if extent < 0.18:
                continue

            touches_edge = x <= margin or y <= margin or (x + w) >= (width - margin) or (y + h) >= (height - margin)
            if touches_edge and area < (0.08 * width * height):
                continue

            roi_person = person_mask[y:y + h, x:x + w]
            person_ratio = float(np.count_nonzero(roi_person)) / rect_area if roi_person.size else 0.0
            face_ratio = self._face_overlap_ratio((x, y, w, h), faces)
            if person_ratio > 0.48:
                continue
            if face_ratio > 0.10:
                continue

            score = (
                (2.2 * (1.0 - min(1.0, person_ratio))) +
                (1.0 * min(1.0, solidity)) +
                (0.8 * min(1.0, extent)) +
                (0.9 * min(1.0, area / (0.12 * width * height))) +
                (0.4 if source_name == "rembg" else 0.0)
            )

            valid.append(
                {
                    "contour": c,
                    "hull": hull,
                    "bbox": (x, y, w, h),
                    "score": score,
                    "source": source_name,
                    "area": area,
                }
            )

        return valid

    def _face_overlap_ratio(self, box, faces):
        if not faces:
            return 0.0
        x, y, w, h = box
        box_area = float(max(1, w * h))
        best = 0.0
        for fx, fy, fw, fh in faces:
            x1 = max(x, fx)
            y1 = max(y, fy)
            x2 = min(x + w, fx + fw)
            y2 = min(y + h, fy + fh)
            iw = max(0, x2 - x1)
            ih = max(0, y2 - y1)
            inter = float(iw * ih)
            best = max(best, inter / box_area)
        return best

    def _box_iou(self, box_a, box_b):
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b
        x1 = max(ax, bx)
        y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw)
        y2 = min(ay + ah, by + bh)
        iw = max(0, x2 - x1)
        ih = max(0, y2 - y1)
        inter = float(iw * ih)
        if inter <= 0:
            return 0.0
        area_a = float(max(1, aw * ah))
        area_b = float(max(1, bw * bh))
        union = area_a + area_b - inter
        return inter / max(1.0, union)

    def _nms_candidates(self, candidates, iou_threshold=0.45, max_keep=5):
        if not candidates:
            return []
        sorted_candidates = sorted(candidates, key=lambda d: d["score"], reverse=True)
        selected = []
        for cand in sorted_candidates:
            keep = True
            for prev in selected:
                if self._box_iou(cand["bbox"], prev["bbox"]) > iou_threshold:
                    keep = False
                    break
            if keep:
                selected.append(cand)
            if len(selected) >= max_keep:
                break
        return selected

    def _update_metric_panel(self, metrics):
        if not metrics:
            for lbl in self.metric_labels.values():
                lbl.configure(text="-")
            return

        self.metric_labels["deskripsi"].configure(text=metrics.get("deskripsi", "-"))
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
        target_w = max(220, int(label_widget.winfo_width()))
        target_h = max(180, int(label_widget.winfo_height()))
        resized = self._resize_contain(rgb, target_w, target_h)

        photo = ImageTk.PhotoImage(Image.fromarray(resized))
        label_widget.configure(image=photo, text="")
        label_widget.image = photo

    def _resize_contain(self, rgb_image, target_w, target_h):
        src_h, src_w = rgb_image.shape[:2]
        if src_h <= 0 or src_w <= 0:
            return rgb_image

        ratio = min(target_w / float(src_w), target_h / float(src_h))
        ratio = max(ratio, 1e-6)
        new_w = max(1, int(src_w * ratio))
        new_h = max(1, int(src_h * ratio))
        interp = cv2.INTER_CUBIC if ratio > 1.0 else cv2.INTER_AREA
        resized = cv2.resize(rgb_image, (new_w, new_h), interpolation=interp)

        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        x0 = (target_w - new_w) // 2
        y0 = (target_h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
        return canvas

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
        if not self.current_metrics:
            messagebox.showwarning("Info", "Belum ada data analisis untuk disimpan.")
            return

        data = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sumber_citra": self.current_source_name,
            "metrics": self.current_metrics,
        }
        pending_path = os.path.join(self.drive_folder, "conversi_hull_pending_db.jsonl")
        try:
            with open(pending_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            self.set_status("Data disimpan ke antrian lokal. Integrasi database online bisa ditambahkan nanti.")
            messagebox.showinfo(
                "Info",
                (
                    "Data disimpan sementara ke file lokal.\n"
                    "Integrasi database online belum diaktifkan.\n\n"
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

    def _imread_unicode(self, path):
        try:
            data = np.fromfile(path, dtype=np.uint8)
            if data.size == 0:
                return None
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None

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
