#!/usr/bin/env python3
"""Draw first frame of video with bounding boxes for P1/P2 input regions.
Row boundaries from config: frame_count_guide (OCR), fade_equal, or fade_detected.
P1 columns left→right: Frm | Dir | Btn.  P2: Btn | Dir | Frm.
Usage: python draw_first_frame_boxes.py [video_path]
Output: first_frame_input_boxes.png
"""
import sys
import os
import configparser
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

config = configparser.ConfigParser()
config.read("config.ini")

def parse_region(s):
    parts = [int(p.strip()) for p in s.split(",") if p.strip()]
    return tuple(parts) if len(parts) == 4 else None


def detect_fade_line_ys(crop_bgr, min_gap=3, min_row_height=4):
    """Detect horizontal fade lines; return equal-height row (y1,y2) with bottom on fade line."""
    if crop_bgr is None or crop_bgr.size == 0:
        return None
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    sobel_y = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
    row_strength = np.sum(sobel_y, axis=1) / (w + 1e-6)
    k = max(3, min(15, h // 30))
    kernel = np.ones(k, dtype=np.float64) / k
    smoothed = np.convolve(row_strength, kernel, mode="same")
    neighborhood = max(4, h // 60)
    peaks_y = []
    for i in range(neighborhood, h - neighborhood):
        if smoothed[i] <= 0:
            continue
        is_peak = True
        for j in range(1, neighborhood + 1):
            if smoothed[i - j] >= smoothed[i] or smoothed[i + j] >= smoothed[i]:
                is_peak = False
                break
        if is_peak and smoothed[i] > np.percentile(smoothed, 40):
            peaks_y.append(i)
    if len(peaks_y) < 1:
        return None
    peaks_y = sorted(peaks_y)
    merged = [peaks_y[0]]
    for py in peaks_y[1:]:
        if py - merged[-1] >= min_gap:
            merged.append(py)
    if len(merged) < 2:
        return None
    use_detected = config.getboolean("input_display", "use_detected_row_boundaries", fallback=True)
    if use_detected:
        # Use detected line positions directly: row heights can vary (matches actual fade lines).
        boundaries = [0] + list(merged)
        row_bounds = []
        for i in range(len(boundaries) - 1):
            y1, y2 = int(boundaries[i]), int(boundaries[i + 1])
            if y2 - y1 < min_row_height:
                y2 = y1 + min_row_height
            row_bounds.append((y1, y2))
        return row_bounds if len(row_bounds) >= 2 else None
    # Equal spacing: exact float boundaries, round per row (no cumulative drift).
    n_lines = len(merged)
    first_y = float(merged[0])
    last_y = float(merged[-1])
    spacing = (last_y - first_y) / (n_lines - 1)
    top = first_y - spacing
    row_bounds = []
    for i in range(n_lines):
        y1_f = top + i * spacing
        y2_f = top + (i + 1) * spacing
        y1 = int(round(y1_f))
        y2 = int(round(y2_f))
        if y2 - y1 < min_row_height:
            y2 = y1 + min_row_height
        row_bounds.append((y1, y2))
    return row_bounds if len(row_bounds) >= 2 else None


def main():
    video_path = config.get("settings", "video_path", fallback="inputs_on_sample.mp4")
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    video_path = os.path.expanduser(video_path.strip())
    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        return 1

    p1_cfg = config.get("input_display", "p1_region", fallback="0,200,280,700")
    p2_cfg = config.get("input_display", "p2_region", fallback="1640,200,280,700")
    r1_1080 = parse_region(p1_cfg)
    r2_1080 = parse_region(p2_cfg)
    if not r1_1080 or not r2_1080:
        print("Invalid p1_region or p2_region in config")
        return 1

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Could not open video")
        return 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Could not read first frame")
        return 1

    h, w = frame.shape[:2]
    scale_x = w / 1920
    scale_y = h / 1080
    def scale_region(r):
        x, y, rw, rh = r
        return (int(x * scale_x), int(y * scale_y), int(rw * scale_x), int(rh * scale_y))
    region1 = scale_region(r1_1080)
    region2 = scale_region(r2_1080)
    x1, y1, rw1, rh1 = region1
    x2, y2, rw2, rh2 = region2

    p1_left_inset_1080 = int(config.get("input_display", "p1_left_inset", fallback="50"))
    p1_frm_ratio = float(config.get("input_display", "p1_frm_width_ratio", fallback="0.20"))
    left_inset = int(p1_left_inset_1080 * scale_x)
    p2_dir_left_1080 = int(config.get("input_display", "p2_dir_left_inset", fallback="15"))
    p2_dir_right_1080 = int(config.get("input_display", "p2_dir_right_inset", fallback="10"))
    p2_dir_left_px = int(p2_dir_left_1080 * scale_x)
    p2_dir_right_px = int(p2_dir_right_1080 * scale_x)
    p2_first_col_ext_1080 = int(config.get("input_display", "p2_first_col_right_extension", fallback="0"))
    p2_first_col_ext_px = int(p2_first_col_ext_1080 * scale_x)
    row_top_padding_px = int(float(config.get("input_display", "row_top_padding", fallback="0")) * scale_y)

    crop1 = frame[y1 : y1 + rh1, x1 : x1 + rw1]
    crop2 = frame[y2 : y2 + rh2, x2 : x2 + rw2]
    w1_c = rw1 - left_inset
    rows_per_player = config.getint("input_display", "rows_per_player", fallback=19)
    row_boundaries_method = config.get("input_display", "row_boundaries_method", fallback="fade_equal").strip().lower()
    row_bounds = None
    row_bounds_p2 = None
    if row_boundaries_method == "frame_count_guide" and rows_per_player > 0:
        from core.core import row_bounds_from_frame_count_ocr
        img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        region1_for_guide = (x1 + left_inset, y1, w1_c, rh1)
        row_bounds = row_bounds_from_frame_count_ocr(img_pil, region1_for_guide, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=False, frm_width_ratio=p1_frm_ratio)
        row_bounds_p2 = row_bounds_from_frame_count_ocr(img_pil, region2, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=True)
    if row_bounds is None or row_bounds_p2 is None:
        row_bounds1 = detect_fade_line_ys(crop1)
        row_bounds2 = detect_fade_line_ys(crop2)
        if row_bounds is None:
            row_bounds = row_bounds1 if row_bounds1 is not None and len(row_bounds1) >= 2 else None
        if row_bounds_p2 is None:
            row_bounds_p2 = row_bounds2 if row_bounds2 is not None and len(row_bounds2) >= 2 else None
    if row_bounds is None and row_bounds_p2 is not None:
        row_bounds = row_bounds_p2
    if row_bounds_p2 is None and row_bounds is not None:
        row_bounds_p2 = row_bounds
    if row_bounds is None or row_bounds_p2 is None:
        n_fallback = max(19, rows_per_player or 19)
        row_bounds = [(int(i * rh1 / n_fallback), int((i + 1) * rh1 / n_fallback)) for i in range(n_fallback)]
        row_bounds_p2 = [(int(i * rh2 / n_fallback), int((i + 1) * rh2 / n_fallback)) for i in range(n_fallback)]

    # P1 and P2: same row handling — drop first (newest) row and add one row at the bottom
    if row_bounds is not None and len(row_bounds) >= 2:
        last = row_bounds[-1]
        row_h = last[1] - last[0]
        new_bottom = (last[1], min(last[1] + row_h, rh1))
        row_bounds = row_bounds[1:] + [new_bottom]
    if row_bounds_p2 is not None and len(row_bounds_p2) >= 2:
        last = row_bounds_p2[-1]
        row_h = last[1] - last[0]
        new_bottom = (last[1], min(last[1] + row_h, rh2))
        row_bounds_p2 = row_bounds_p2[1:] + [new_bottom]

    # P2: crop width using second-oldest row as guide (button + frame count extent)
    from core.core import get_p2_content_insets
    p2_left_inset_px, p2_right_inset_px = get_p2_content_insets(crop2, row_bounds_p2, margin=5)
    x2_eff = x2 + p2_left_inset_px
    rw2_eff = max(1, rw2 - p2_left_inset_px - p2_right_inset_px)
    region2_eff = (x2_eff, y2, rw2_eff, rh2)

    col_p1_outer = (0, 255, 0)
    col_p2_outer = (255, 255, 0)
    col_row = (0, 255, 255)
    col_frame = (255, 255, 255)
    col_direction = (255, 0, 255)
    col_button = (0, 165, 255)
    thick_outer = 3
    thick_inner = 1

    # P2 column boundaries (used for both P2 draw and P1 mirror)
    w_f2 = int(rw2_eff * 0.35)
    w_d2 = int(rw2_eff * 0.35)
    btn_right_x2 = x2_eff + rw2_eff - w_f2 - w_d2 + p2_dir_left_px + p2_first_col_ext_px
    dir_left_x2 = btn_right_x2
    dir_right_x2 = x2_eff + rw2_eff - w_f2 + p2_dir_right_px
    p2_btn_width = btn_right_x2 - x2_eff
    p2_dir_width = dir_right_x2 - dir_left_x2
    p2_frm_width = (x2_eff + rw2_eff) - dir_right_x2

    # P1: mirrored position and dimensions from P2. Mirror = same width (rw2_eff), same height (rh2), same rows (row_bounds_p2), at left-side screen position.
    x1_mirror = w - x2_eff - rw2_eff
    y1_mirror = y2
    region1_mirror = (x1_mirror, y1_mirror, rw2_eff, rh2)
    cv2.rectangle(frame, (x1_mirror, y1_mirror), (x1_mirror + rw2_eff, y1_mirror + rh2), col_p1_outer, thick_outer)
    for (yc1, yc2) in row_bounds_p2:
        yc1_use = max(0, yc1 - row_top_padding_px)
        yc2_use = yc2 - row_top_padding_px
        if yc2_use <= yc1_use:
            yc1_use, yc2_use = yc1, yc2
        y1_abs = y1_mirror + yc1_use
        y2_abs = y1_mirror + yc2_use
        if y2_abs <= y1_abs:
            y2_abs = y1_abs + 1
        cv2.rectangle(frame, (x1_mirror, y1_abs), (x1_mirror + rw2_eff, y2_abs), col_row, thick_inner)
        cv2.rectangle(frame, (x1_mirror, y1_abs), (x1_mirror + p2_frm_width, y2_abs), col_frame, thick_inner)
        cv2.rectangle(frame, (x1_mirror + p2_frm_width, y1_abs), (x1_mirror + p2_frm_width + p2_dir_width, y2_abs), col_direction, thick_inner)
        cv2.rectangle(frame, (x1_mirror + p2_frm_width + p2_dir_width, y1_abs), (x1_mirror + rw2_eff, y2_abs), col_button, thick_inner)

    def draw_region_boxes(img, region, row_bounds_list, is_p1, p2_dir_left=0, p2_dir_right=0, p2_first_col_ext=0, top_padding=0):
        x, y, rw, rh = region
        outer_color = col_p1_outer if is_p1 else col_p2_outer
        cv2.rectangle(img, (x, y), (x + rw, y + rh), outer_color, thick_outer)
        w_f = int(rw * 0.35)
        w_d = int(rw * 0.35)
        for (yc1, yc2) in row_bounds_list:
            yc1_use = max(0, yc1 - top_padding)
            yc2_use = yc2 - top_padding
            if yc2_use <= yc1_use:
                yc1_use, yc2_use = yc1, yc2
            y1_abs = y + yc1_use
            y2_abs = y + yc2_use
            if y2_abs <= y1_abs:
                y2_abs = y1_abs + 1
            cv2.rectangle(img, (x, y1_abs), (x + rw, y2_abs), col_row, thick_inner)
            if is_p1:
                cv2.rectangle(img, (x, y1_abs), (x + w_f, y2_abs), col_frame, thick_inner)
                cv2.rectangle(img, (x + w_f, y1_abs), (x + w_f + w_d, y2_abs), col_direction, thick_inner)
                cv2.rectangle(img, (x + w_f + w_d, y1_abs), (x + rw, y2_abs), col_button, thick_inner)
            else:
                # P2: Btn | Dir | Frm. First col (Btn) right edge extended to go over arrows/N
                btn_right = x + rw - w_f - w_d + p2_dir_left + p2_first_col_ext
                dir_left = btn_right
                dir_right = x + rw - w_f + p2_dir_right
                cv2.rectangle(img, (x, y1_abs), (btn_right, y2_abs), col_button, thick_inner)
                cv2.rectangle(img, (dir_left, y1_abs), (dir_right, y2_abs), col_direction, thick_inner)
                cv2.rectangle(img, (dir_right, y1_abs), (x + rw, y2_abs), col_frame, thick_inner)

    draw_region_boxes(frame, region2_eff, row_bounds_p2, is_p1=False, p2_dir_left=p2_dir_left_px, p2_dir_right=p2_dir_right_px, p2_first_col_ext=p2_first_col_ext_px, top_padding=row_top_padding_px)

    font = cv2.FONT_HERSHEY_SIMPLEX
    nr_p2 = len(row_bounds_p2)
    row0_y_p1 = y1_mirror + (row_bounds_p2[0][0] + row_bounds_p2[0][1]) // 2 if nr_p2 else y1_mirror + rh2 // 2
    row0_y_p2 = y2 + (row_bounds_p2[0][0] + row_bounds_p2[0][1]) // 2 if nr_p2 else y2 + rh2 // 2
    cv2.putText(frame, "P1", (x1_mirror, max(20, y1_mirror - 8)), font, 0.7, col_p1_outer, 2)
    cv2.putText(frame, "P2", (x2_eff, max(20, y2 - 8)), font, 0.7, col_p2_outer, 2)
    cv2.putText(frame, "Frm", (x1_mirror + 4, row0_y_p1 + 4), font, 0.4, col_frame, 1)
    cv2.putText(frame, "Dir", (x1_mirror + p2_frm_width + 4, row0_y_p1 + 4), font, 0.4, col_direction, 1)
    cv2.putText(frame, "Btn", (x1_mirror + p2_frm_width + p2_dir_width + 4, row0_y_p1 + 4), font, 0.4, col_button, 1)
    cv2.putText(frame, "Btn", (x2_eff + 4, row0_y_p2 + 4), font, 0.4, col_button, 1)
    cv2.putText(frame, "Dir", (dir_left_x2 + 4, row0_y_p2 + 4), font, 0.4, col_direction, 1)
    cv2.putText(frame, "Frm", (dir_right_x2 + 4, row0_y_p2 + 4), font, 0.4, col_frame, 1)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "first_frame_input_boxes.png")
    cv2.imwrite(out_path, frame)
    print(f"Saved: {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
