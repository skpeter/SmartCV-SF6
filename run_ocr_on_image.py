#!/usr/bin/env python3
"""Run the P1 input-display OCR on a static image (e.g. a screenshot).
Usage: python run_ocr_on_image.py <image_path> [--debug]
  image_path = e.g. test_samples/input_reading/p1_inputs_screenshot.png
  --debug = print every raw OCR detection (y, x, text, conf) before row grouping
Regions are scaled from 1080p if the image size differs.
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
    args = [a for a in sys.argv[1:] if a != "--debug"]
    debug = "--debug" in sys.argv
    if not args:
        print("Usage: python run_ocr_on_image.py <image_path> [--debug]")
        return 1
    image_path = os.path.expanduser(args[0].strip())
    if not os.path.isfile(image_path):
        print(f"File not found: {image_path}")
        return 1

    p1_cfg = config.get("input_display", "p1_region", fallback="0,200,280,700")
    region_1080 = parse_region(p1_cfg)
    if not region_1080:
        print("Invalid p1_region in config")
        return 1

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        print("Could not load image (check format)")
        return 1
    h, w = img_bgr.shape[:2]
    # If image is already a narrow strip (e.g. cropped P1 column), use full image
    if w < 500:
        region = (0, 0, w, h)
        print(f"Image is narrow strip ({w}x{h}); using full image as region.\n")
    else:
        scale_x = w / 1920
        scale_y = h / 1080
        x, y, rw, rh = region_1080
        region = (int(x * scale_x), int(y * scale_y), int(rw * scale_x), int(rh * scale_y))
    img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

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
    print(f"Rows (top = newest, bottom = oldest):")
    for i, (y_pos, text) in enumerate(rows, 1):
        print(f"  {i}. {text}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
