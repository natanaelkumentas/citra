# services/hull_service.py — Convex hull, background removal, face detection
# Diambil dari ConversiHullWindow.


import os
import cv2
import numpy as np

try:
    from rembg import remove as rembg_remove
    _REMBG_AVAILABLE = True
except Exception:
    rembg_remove = None
    _REMBG_AVAILABLE = False


def _load_cascade(filename):
    try:
        path = os.path.join(cv2.data.haarcascades, filename)
        if os.path.exists(path):
            return cv2.CascadeClassifier(path)
    except Exception:
        pass
    return None

def _normalize_bgr(image):
    if image is None or image.size == 0:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image.copy()

def _crop_active_region(bgr):
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

def _detect_faces(gray):
    faces_all = []
    for cascade in (_load_cascade('haarcascade_frontalface_default.xml'), _load_cascade('haarcascade_frontalface_alt2.xml')):
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
            if _box_iou(f, prev) > 0.35:
                keep = False
                break
        if keep:
            dedup.append(f)
    return dedup

def _build_person_mask(bgr):
    h, w = bgr.shape[:2]
    person_mask = np.zeros((h, w), dtype=np.uint8)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _detect_faces(gray)

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

def _extract_rembg_mask(bgr):
    if _REMBG_AVAILABLE is False or rembg_remove is None:
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
        rembg_enabled = False
        return None

def _build_candidate_masks(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    masks = []

    rembg_mask = _extract_rembg_mask(bgr)
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

def compute_convex_hull(bgr):
    image_bgr = _normalize_bgr(bgr)
    if image_bgr is None:
        return bgr, None

    work_bgr, off_x, off_y = _crop_active_region(image_bgr)
    person_mask, faces = _build_person_mask(work_bgr)
    candidates = _detect_candidate_contours(work_bgr, person_mask, faces)
    selected = _nms_candidates(candidates, iou_threshold=0.45, max_keep=5)

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
            "pixel_objek": 0,
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
    mask_objek = np.zeros(work_bgr.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask_objek, [best["contour"]], -1, 255, -1)
    pixel_objek = int(np.count_nonzero(mask_objek))

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
        "pixel_objek": pixel_objek,
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

def _detect_candidate_contours(bgr, person_mask, faces):
    h, w = bgr.shape[:2]
    img_area = float(h * w)
    min_area = max(1300.0, img_area * 0.0028)
    max_area = img_area * 0.72

    masks = _build_candidate_masks(bgr)
    candidates = []
    for source, mask in masks:
        candidates.extend(
            _extract_valid_contours(
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

def _extract_valid_contours(mask,
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
        face_ratio = _face_overlap_ratio((x, y, w, h), faces)
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

def _face_overlap_ratio(box, faces):
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

def _box_iou(box_a, box_b):
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

def _nms_candidates(candidates, iou_threshold=0.45, max_keep=5):
    if not candidates:
        return []
    sorted_candidates = sorted(candidates, key=lambda d: d["score"], reverse=True)
    selected = []
    for cand in sorted_candidates:
        keep = True
        for prev in selected:
            if _box_iou(cand["bbox"], prev["bbox"]) > iou_threshold:
                keep = False
                break
        if keep:
            selected.append(cand)
        if len(selected) >= max_keep:
            break
    return selected

