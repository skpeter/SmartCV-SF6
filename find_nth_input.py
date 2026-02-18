#!/usr/bin/env python3
"""Read video frame, OCR P1 input region with row order, print the Nth input from the top.
Usage: python find_nth_input.py [n] [video_path] [--debug]
  n = 4 (default) = 4th input from top
  video_path = inputs_on_sample.mp4 (default from config)
  --debug = print every raw OCR detection (y, x, text) before grouping
"""
import sys
import os
import configparser
import cv2
from PIL import Image

# Run from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

config = configparser.ConfigParser()
config.read("config.ini")

def parse_region(s):
    parts = [int(p.strip()) for p in s.split(",") if p.strip()]
    return tuple(parts) if len(parts) == 4 else None

def main():
    args = [a for a in sys.argv[1:] if a != "--debug"]
    debug = "--debug" in sys.argv
    n = int(args[0]) if args else 4
    video_path = args[1] if len(args) > 1 else config.get("settings", "video_path", fallback="inputs_on_sample.mp4")
    video_path = os.path.expanduser(video_path.strip())
    if not os.path.isfile(video_path):
        print(f"Video not found: {video_path}")
        return 1

    p1_cfg = config.get("input_display", "p1_region", fallback="0,200,280,700")
    region_1080 = parse_region(p1_cfg)
    if not region_1080:
        print("Invalid p1_region in config")
        return 1

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Could not open video")
        return 1
    # First frame (inputs already on screen from start)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Could not read frame")
        return 1

    h, w = frame.shape[:2]
    scale_x = w / 1920
    scale_y = h / 1080
    x, y, rw, rh = region_1080
    region = (int(x * scale_x), int(y * scale_y), int(rw * scale_x), int(rh * scale_y))
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    from core.core import read_text_with_positions, read_input_raw_detections
    allowlist = "0123456789NLPKMH+- "
    if debug:
        raw_list = read_input_raw_detections(img, region, contrast=2, allowlist=allowlist, low_text=0.3)
        print("Raw OCR detections (top_y, left_x, text, conf) — top to bottom, then left to right:")
        for i, (top_y, left_x, text, conf) in enumerate(raw_list, 1):
            print(f"  {i}. y={top_y:4d} x={left_x:4d}  {repr(text):20s}  conf={conf:.2f}")
        print()
    rows = read_text_with_positions(img, region, contrast=2, allowlist=allowlist, low_text=0.3)

    if not rows:
        print("No text detected in P1 region.")
        return 0
    print(f"Top {min(15, len(rows))} rows (top to bottom), each row = direction + button + frames:")
    for i, (y_pos, text) in enumerate(rows[:15], 1):
        marker = " <-- 4th" if i == n else ""
        print(f"  {i}. {text}{marker}")
    if len(rows) > 15:
        print(f"  ... ({len(rows)} rows total)")
    if n < 1 or n > len(rows):
        print(f"Row {n} not in range 1..{len(rows)}.")
    else:
        y_pos, text = rows[n - 1]
        print(f"\nPlayer 1, {n}th input from top: {text}")
    # Bottom = last row (oldest input in cascade)
    if rows:
        y_bot, text_bot = rows[-1]
        print(f"Player 1, bottom (oldest) input: {text_bot}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
