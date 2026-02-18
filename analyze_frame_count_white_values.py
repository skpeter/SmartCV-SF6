#!/usr/bin/env python3
"""Analyze grayscale values in a known-correct frame-count cell to tune white_threshold.
Usage: python analyze_frame_count_white_values.py [video_path] [--p1|--p2] [--row N]
  Default: P2, row 19 (oldest). Row 1 = newest, 19 = oldest.
Output: min, max, mean, percentiles, and suggested threshold. Saves crop to dev/frame_count_sample_*.png
"""
import sys
import os
import argparse
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

def main():
    parser = argparse.ArgumentParser(description="Analyze white/dark pixel values in a frame-count cell")
    parser.add_argument("video_path", nargs="?", help="Video file (default from config)")
    parser.add_argument("--p1", action="store_true", help="Analyze P1 frame-count column (default: P2)")
    parser.add_argument("--p2", action="store_true", help="Analyze P2 frame-count column")
    parser.add_argument("--row", type=int, default=19, help="Row number 1–19 (1=newest, 19=oldest). Default 19")
    parser.add_argument("--no-contrast", action="store_true", help="Skip contrast boost (analyze raw crop)")
    args = parser.parse_args()

    video_path = args.video_path or config.get("settings", "video_path", fallback="inputs_on_sample.mp4")
    video_path = os.path.expanduser(video_path.strip())
    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        return 1

    use_p1 = args.p1 and not args.p2
    row_index = max(1, min(19, args.row)) - 1  # 0-based

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
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    from core.core import row_bounds_from_frame_count_ocr, get_p2_content_insets
    p1_left_inset = int(float(config.get("input_display", "p1_left_inset", fallback="50")) * scale_x)
    p1_frm_ratio = float(config.get("input_display", "p1_frm_width_ratio", fallback="0.20"))
    row_boundaries_method = config.get("input_display", "row_boundaries_method", fallback="fade_equal").strip().lower()
    rows_per_player = config.getint("input_display", "rows_per_player", fallback=19)

    x1, y1, rw1, rh1 = region1
    x2, y2, rw2, rh2 = region2
    crop2_bgr = frame[y2:y2+rh2, x2:x2+rw2]

    if use_p1:
        region1_for_guide = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, rh1)
        rb = row_bounds_from_frame_count_ocr(img, region1_for_guide, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=False, frm_width_ratio=p1_frm_ratio)
        region_content = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, rb[-1][1] if rb else rh1)
        frm_width = int(region_content[2] * p1_frm_ratio)
        col_left = True
    else:
        rb = row_bounds_from_frame_count_ocr(img, region2, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=True)
        if rb is not None and len(rb) >= 2:
            _, _, rw2_early, rh2_early = region2
            last = rb[-1]
            row_h = last[1] - last[0]
            new_bottom = (last[1], min(last[1] + row_h, rh2_early))
            rb = rb[1:] + [new_bottom]
        p2_left_inset_px, p2_right_inset_px = get_p2_content_insets(crop2_bgr, rb, margin=5) if rb else (0, 0)
        region_content = (x2 + p2_left_inset_px, y2, max(1, rw2 - p2_left_inset_px - p2_right_inset_px), rh2)
        frm_width = int(region_content[2] * 0.35)
        col_left = False

    if rb is None or len(rb) <= row_index:
        print("Row bounds not available or row index out of range")
        return 1

    xc, yc, wc, hc = region_content
    y1_crop, y2_crop = rb[row_index][0], rb[row_index][1]
    pad = 2
    y1_use = max(0, y1_crop - pad)
    y2_use = min(hc, y2_crop + pad)
    if col_left:
        band_region = (xc, yc + y1_use, frm_width, y2_use - y1_use)
    else:
        band_region = (xc + wc - frm_width, yc + y1_use, frm_width, y2_use - y1_use)

    bx, by, bw, bh = band_region
    img_band = img.crop((bx, by, bx + bw, by + bh))
    band_np = np.array(img_band)
    bgr = cv2.cvtColor(band_np, cv2.COLOR_RGB2BGR)
    if not args.no_contrast:
        bgr = cv2.convertScaleAbs(bgr, alpha=2, beta=-(2 * 50))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    flat = gray.ravel()

    player = "P1" if use_p1 else "P2"
    print(f"Frame-count column sample: {player} row {args.row} (1=newest, 19=oldest)")
    print(f"Crop size: {bw}x{bh} px (after contrast: {not args.no_contrast})")
    print()
    print("Grayscale (0–255):")
    print(f"  min={int(flat.min())}, max={int(flat.max())}, mean={flat.mean():.1f}, std={flat.std():.1f}")
    print(f"  percentiles: p5={int(np.percentile(flat, 5))}, p25={int(np.percentile(flat, 25))}, p50={int(np.percentile(flat, 50))}, p75={int(np.percentile(flat, 75))}, p95={int(np.percentile(flat, 95))}")
    bright = flat[flat >= 128]
    dark = flat[flat < 128]
    if len(bright) > 0:
        print(f"  pixels >= 128 (likely digit): count={len(bright)}, mean={bright.mean():.1f}, min={int(bright.min())}, max={int(bright.max())}")
    if len(dark) > 0:
        print(f"  pixels < 128 (likely background): count={len(dark)}, mean={dark.mean():.1f}, min={int(dark.min())}, max={int(dark.max())}")
    if len(dark) > 0 and len(bright) > 0:
        mid_cluster = (int(dark.max()) + int(bright.min())) / 2
    else:
        mid_cluster = (int(flat.min()) + int(flat.max())) / 2
    print()
    print("Suggested threshold (between background and digit):")
    print(f"  p2_frame_count_white_threshold = {int(np.percentile(flat, 25))}  (include more grey as digit)")
    print(f"  p2_frame_count_white_threshold = {int(round(mid_cluster))}  (between clusters)")
    print(f"  p2_frame_count_white_threshold = {int(np.percentile(flat, 75))}  (stricter: only bright as digit)")

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev"), exist_ok=True)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dev", f"frame_count_sample_{player.lower()}_row{args.row}.png")
    cv2.imwrite(out_path, bgr)
    print(f"\nSaved crop: {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
