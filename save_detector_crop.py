#!/usr/bin/env python3
"""Save the exact crop the detector uses for any player, row, and column.
Purpose: see what the detector sees (debug input regions).

Usage:
  python save_detector_crop.py <player> <row> <column> [video_path]
  python save_detector_crop.py p2 15 dir
  python save_detector_crop.py p2 19 btn
  python save_detector_crop.py p1 1 frm inputs_on_sample.mp4

  player: p1 | p2
  row: 1-based row (1=newest, 19=oldest) — any row
  column: btn | dir | frm — any column

Output: only one file is updated per run — debug/detector_crop.png (overwrites each time).
  Use -o to override path if needed. With --save-32 for dir column, also writes debug/detector_crop_32x32.png.
  Do not create multiple files (e.g. detector_crop_r14_btn.png); always overwrite the same detector_crop.png.
"""
import sys
import os
import configparser
import cv2
import argparse
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

config = configparser.ConfigParser()
config.read("config.ini")


def parse_region(s):
    parts = [int(p.strip()) for p in s.split(",") if p.strip()]
    return tuple(parts) if len(parts) == 4 else None


def main():
    ap = argparse.ArgumentParser(description="Save the crop the detector uses for a row/column (see what the detector sees).")
    ap.add_argument("player", choices=["p1", "p2"], help="p1 or p2")
    ap.add_argument("row", type=int, help="1-based row (1=newest)")
    ap.add_argument("column", choices=["btn", "dir", "frm"], help="btn, dir, or frm")
    ap.add_argument("video_path", nargs="?", default=None, help="Video path (default: from config)")
    ap.add_argument("-o", "--out", default=None, help="Output path (default: debug/detector_crop.png)")
    ap.add_argument("--save-32", action="store_true", help="Also save 32x32 normalized crop for dir column")
    args = ap.parse_args()

    video_path = args.video_path or config.get("settings", "video_path", fallback="inputs_on_sample.mp4")
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
    )

    rows_per_player = config.getint("input_display", "rows_per_player", fallback=19)
    row_boundaries_method = config.get("input_display", "row_boundaries_method", fallback="fade_equal").strip().lower()
    p1_left_inset_1080 = int(config.get("input_display", "p1_left_inset", fallback="50"))
    p1_left_inset = int(p1_left_inset_1080 * scale_x)
    p1_frm_ratio = float(config.get("input_display", "p1_frm_width_ratio", fallback="0.20"))

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
    h1_content = rb1[-1][1] if rb1 else rh1
    region1_content = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, h1_content)
    crop1 = get_region_crop_np(img, region1_content, contrast=2)

    rw1c, rh1c = region1_content[2], region1_content[3]
    rw2e, rh2e = region2_eff[2], region2_eff[3]

    if args.player == "p2":
        crop = crop2
        row_bounds = rb2
        region_w, region_h = rw2e, rh2e
        p1_frm_ratio_arg = 0.35
    else:
        crop = crop1
        row_bounds = rb1
        region_w, region_h = rw1c, rh1c
        p1_frm_ratio_arg = p1_frm_ratio

    if not row_bounds or args.row < 1 or args.row > len(row_bounds):
        print(f"Row must be 1..{len(row_bounds) or 0}")
        return 1

    out_crop = get_row_column_crop(crop, row_bounds, region_w, region_h, args.player, args.row, args.column, p1_frm_width_ratio=p1_frm_ratio_arg)
    if out_crop is None:
        print("Could not extract crop (invalid column or bounds)")
        return 1

    debug_dir = os.path.join(os.path.dirname(__file__), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    out_path = args.out or os.path.join(debug_dir, "detector_crop.png")
    cv2.imwrite(out_path, out_crop)
    print(f"Saved: {out_path}  ({args.player} row {args.row} {args.column})")

    if args.save_32 and args.column == "dir":
        gray = out_crop
        if gray.ndim == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        zone = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        zone = cv2.normalize(zone, None, 0, 255, cv2.NORM_MINMAX).astype("uint8")
        path_32 = os.path.join(debug_dir, "detector_crop_32x32.png")
        cv2.imwrite(path_32, zone)
        print(f"Saved (32x32): {path_32}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
