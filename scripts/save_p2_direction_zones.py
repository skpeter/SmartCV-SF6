#!/usr/bin/env python3
"""Save the 6 oldest P2 direction-zone crops to a single debug image.
Usage: python scripts/save_p2_direction_zones.py [video_path]
  video_path = from config.ini if omitted.
Writes: debug/p2_dir_zones.png (one file, all 6 rows stacked vertically).
"""
import sys
import os
import configparser
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

    from PIL import Image
    from core.core import (
        get_region_crop_np,
        row_bounds_from_frame_count_ocr,
        get_p2_content_insets,
        get_p2_direction_zone_crops,
    )

    p2_cfg = config.get("input_display", "p2_region", fallback="1640,200,280,700")
    region2_1080 = parse_region(p2_cfg)
    if not region2_1080:
        print("Invalid p2_region in config")
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

    region2 = scale_region(region2_1080)
    x2, y2, rw2, rh2 = region2
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    crop2 = get_region_crop_np(img, region2, contrast=2)

    rows_per_player = config.getint("input_display", "rows_per_player", fallback=19)
    rb2 = row_bounds_from_frame_count_ocr(
        img, region2, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=True
    )
    if rb2 is None or len(rb2) < 6:
        print("Could not get P2 row bounds (need at least 6 rows)")
        return 1
    # Same as main script: drop first row, add one at bottom
    if len(rb2) >= 2:
        last = rb2[-1]
        row_h = last[1] - last[0]
        new_bottom = (last[1], min(last[1] + row_h, rh2))
        rb2 = rb2[1:] + [new_bottom]
    p2_left_inset_px, p2_right_inset_px = get_p2_content_insets(crop2, rb2, margin=5)
    region2_eff = (x2 + p2_left_inset_px, y2, max(1, rw2 - p2_left_inset_px - p2_right_inset_px), rh2)
    crop2 = get_region_crop_np(img, region2_eff, contrast=2)
    rw2, rh2 = region2_eff[2], region2_eff[3]

    zones = get_p2_direction_zone_crops(crop2, rb2, rw2, rh2, num_oldest=6)
    debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug")
    os.makedirs(debug_dir, exist_ok=True)
    gap = 2
    rows_list = [z for _, z in zones]
    h = sum(z.shape[0] for z in rows_list) + gap * (len(rows_list) - 1)
    w = max(z.shape[1] for z in rows_list)
    composite = np.zeros((h, w, 3), dtype=np.uint8)
    composite[:] = 255
    y = 0
    for _, zone in zones:
        if zone.ndim == 2:
            zone = cv2.cvtColor(zone, cv2.COLOR_GRAY2BGR)
        hz, wz = zone.shape[:2]
        composite[y : y + hz, :wz] = zone
        y += hz + gap
    path = os.path.join(debug_dir, "p2_dir_zones.png")
    cv2.imwrite(path, composite)
    print(f"Saved: {path}  (6 rows stacked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
