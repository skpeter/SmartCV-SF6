#!/usr/bin/env python3
"""Report the last 6 inputs for P2 by reading each cell the same way as detector_crop:
  for each (row, column) get the crop with get_row_column_crop, then run the single-cell
  detector (detect_direction_from_zone, detect_button_from_zone, read_frame_count_from_zone).
  This matches the accuracy of save_detector_crop + manual read.

Usage: python read_oldest_6_p2_by_cell.py [video_path]
  video_path = from config.ini if omitted.
"""
import sys
import os
import configparser
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

config = configparser.ConfigParser()
config.read("config.ini")


def parse_region(s):
    parts = [int(p.strip()) for p in s.split(",") if p.strip()]
    return tuple(parts) if len(parts) == 4 else None


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
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    crop1_raw = frame[y1 : y1 + rh1, x1 : x1 + rw1]
    crop2_raw = frame[y2 : y2 + rh2, x2 : x2 + rw2]

    from core.core import (
        get_region_crop_np,
        detect_fade_line_ys,
        row_bounds_from_frame_count_ocr,
        get_p2_content_insets,
        get_row_column_crop,
        detect_direction_from_zone,
        detect_button_from_zone,
        read_frame_count_from_zone,
    )

    rows_per_player = config.getint("input_display", "rows_per_player", fallback=19)
    row_boundaries_method = config.get("input_display", "row_boundaries_method", fallback="fade_equal").strip().lower()
    p1_left_inset_1080 = int(config.get("input_display", "p1_left_inset", fallback="50"))
    p1_left_inset = int(p1_left_inset_1080 * scale_x)
    p1_frm_ratio = float(config.get("input_display", "p1_frm_width_ratio", fallback="0.20"))
    p2_white_threshold = config.getint("input_display", "p2_frame_count_white_threshold", fallback=140)

    rb1 = rb2 = None
    if row_boundaries_method == "frame_count_guide" and rows_per_player > 0:
        region1_for_guide = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, rh1)
        rb1 = row_bounds_from_frame_count_ocr(img, region1_for_guide, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=False, frm_width_ratio=p1_frm_ratio)
        rb2 = row_bounds_from_frame_count_ocr(img, region2, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=True)
    if rb1 is None or rb2 is None:
        use_detected = config.getboolean("input_display", "use_detected_row_boundaries", fallback=False)
        row_bounds1 = detect_fade_line_ys(crop1_raw, use_detected_boundaries=use_detected)
        row_bounds2 = detect_fade_line_ys(crop2_raw, use_detected_boundaries=use_detected)
        if rb1 is None:
            rb1 = row_bounds1 if row_bounds1 and len(row_bounds1) >= 2 else None
        if rb2 is None:
            rb2 = row_bounds2 if row_bounds2 and len(row_bounds2) >= 2 else None
    if rb1 is None and rb2 is not None:
        rb1 = rb2
    if rb2 is None and rb1 is not None:
        rb2 = rb1
    if rb2 is not None and len(rb2) >= 2:
        last = rb2[-1]
        row_h = last[1] - last[0]
        new_bottom = (last[1], min(last[1] + row_h, rh2))
        rb2 = rb2[1:] + [new_bottom]

    region2_eff = region2
    crop2 = get_region_crop_np(img, region2, contrast=2)
    if rb2 is not None:
        p2_left_inset_px, p2_right_inset_px = get_p2_content_insets(crop2, rb2, margin=5)
        region2_eff = (x2 + p2_left_inset_px, y2, max(1, rw2 - p2_left_inset_px - p2_right_inset_px), rh2)
        crop2 = get_region_crop_np(img, region2_eff, contrast=2)
    rw2e, rh2e = region2_eff[2], region2_eff[3]

    n_rows = len(rb2) if rb2 else 0
    k = 6
    oldest_6_start = max(0, n_rows - k)
    oldest_rows_1based = list(range(oldest_6_start + 1, n_rows + 1))  # e.g. [14,15,16,17,18,19]

    if n_rows < k:
        print(f"Only {n_rows} rows; need at least {k} for oldest 6.")
        return 1

    def dir_label(d):
        if d is None:
            return "—"
        return "N" if d == "5" else str(d)

    # Per-cell read: same process as detector_crop for each (row, column), then report value
    results = []
    for row_1 in oldest_rows_1based:
        btn_crop = get_row_column_crop(crop2, rb2, rw2e, rh2e, "p2", row_1, "btn", p1_frm_width_ratio=0.35)
        dir_crop = get_row_column_crop(crop2, rb2, rw2e, rh2e, "p2", row_1, "dir", p1_frm_width_ratio=0.35)
        frm_crop = get_row_column_crop(crop2, rb2, rw2e, rh2e, "p2", row_1, "frm", p1_frm_width_ratio=0.35)

        btn = detect_button_from_zone(btn_crop) if btn_crop is not None and btn_crop.size else None
        dir_val = detect_direction_from_zone(dir_crop, template_key="p2") if dir_crop is not None and dir_crop.size else None
        frm = read_frame_count_from_zone(frm_crop, contrast=2.0, white_on_dark=True, white_threshold=p2_white_threshold) if frm_crop is not None and frm_crop.size else ""

        btn_s = (btn or "—").strip() if btn else "—"
        dir_s = dir_label(dir_val)
        frm_s = (frm or "").strip() or "—"
        results.append((row_1, btn_s, dir_s, frm_s))

    print("Oldest 6 P2 inputs (by-cell read: same process as detector_crop for each cell)")
    print("Columns: Btn | Dir | Frm. Row 14 = 6th-oldest, Row 19 = 1st-oldest.")
    print()
    for j, (row_1, btn_s, dir_s, frm_s) in enumerate(results, 1):
        print(f"  {j}. Row {row_1:2}:  Btn={btn_s}  Dir={dir_s:>2}  Frm={frm_s:>3}")
    print()
    one_line = " | ".join(f"Row {r[0]}: Btn={r[1]} Dir={r[2]} Frm={r[3]}" for r in results)
    print("  → One line:", one_line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
