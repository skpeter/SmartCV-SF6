#!/usr/bin/env python3
"""Extract direction-zone crops from input strip and save as templates.
  Image: python scripts/extract_direction_templates_from_image.py path/to/strip.png
  Video P1: python scripts/extract_direction_templates_from_image.py --video path/to/video.mp4
  Video P2: python scripts/extract_direction_templates_from_image.py --video path/to/video.mp4 --p2
Slices into fixed-height rows, crops middle (direction zone), resizes to 32x32.
  P1 -> img/input_directions/extracted/   P2 -> img/input_directions/extracted_p2/
"""
import os
import sys
import configparser
import cv2
import numpy as np

parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent)
os.chdir(parent)

def load_synthetic_templates():
    templates_dir = os.path.join(parent, "img", "input_directions")
    labels = ["n", "1", "2", "3", "4", "6", "7", "8", "9"]
    out = []
    for lab in labels:
        path = os.path.join(templates_dir, f"{lab}.png")
        t = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if t is not None:
            out.append((lab.upper() if lab == "n" else lab, t))
    return out

def main():
    use_video = "--video" in sys.argv
    use_p2 = "--p2" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--video", "--p2")]
    if not args:
        print("Usage: python scripts/extract_direction_templates_from_image.py <strip_image>")
        print("   or: python scripts/extract_direction_templates_from_image.py --video <video.mp4> [--p2]")
        return 1
    path = os.path.expanduser(args[0])
    if not os.path.isfile(path):
        print(f"Not found: {path}")
        return 1
    if use_video:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("Could not open video")
            return 1
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("Could not read first frame")
            return 1
        cfg = configparser.ConfigParser()
        cfg.read(os.path.join(parent, "config.ini"))
        region_key = "p2_region" if use_p2 else "p1_region"
        default = "1640,200,280,700" if use_p2 else "0,200,280,700"
        reg = cfg.get("input_display", region_key, fallback=default)
        parts = [int(p.strip()) for p in reg.split(",") if p.strip()]
        if len(parts) != 4:
            print(f"Invalid {region_key}")
            return 1
        x, y, rw, rh = parts
        h_vid, w_vid = frame.shape[:2]
        sx, sy = w_vid / 1920, h_vid / 1080
        x, y = int(x * sx), int(y * sy)
        rw, rh = int(rw * sx), int(rh * sy)
        img = frame[y : y + rh, x : x + rw]
    else:
        img = cv2.imread(path)
        if img is None:
            print("Could not load image")
            return 1
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    h, w = gray.shape[:2]
    # Fixed row height (strip is ~550px, ~15-19 rows -> ~29-36 px/row)
    row_height = max(28, h // 18)
    out_dir = os.path.join(parent, "img", "input_directions", "extracted_p2" if use_p2 else "extracted")
    os.makedirs(out_dir, exist_ok=True)
    synthetics = load_synthetic_templates()
    if not synthetics:
        print("No synthetic templates in img/input_directions/ - run scripts/generate_direction_templates.py first")
        return 1
    x1, x2 = w // 3, 2 * (w // 3)
    extracted = []
    y = row_height // 2
    while y + row_height // 2 < h:
        y1 = max(0, y - row_height // 2)
        y2 = min(h, y + row_height // 2)
        zone = gray[y1:y2, x1:x2]
        zone = cv2.resize(zone, (32, 32), interpolation=cv2.INTER_AREA)
        zone = cv2.normalize(zone, None, 0, 255, cv2.NORM_MINMAX)
        best_label, best_score = None, -2.0
        for label, tpl in synthetics:
            tpl_norm = cv2.normalize(tpl, None, 0, 255, cv2.NORM_MINMAX)
            res = cv2.matchTemplate(zone, tpl_norm, cv2.TM_CCOEFF_NORMED)
            score = float(np.max(res))
            if score > best_score:
                best_score = score
                best_label = "5" if label == "N" else label
        save_label = best_label if best_score >= 0.2 else f"row{len(extracted)}"
        if best_label == "5":
            save_name = "n.png"
        else:
            save_name = f"{save_label}.png"
        out_path = os.path.join(out_dir, save_name)
        cv2.imwrite(out_path, zone)
        extracted.append((y, save_label, best_score))
        y += row_height
    print(f"Wrote {len(extracted)} direction crops to {out_dir}")
    for y, lab, sc in extracted[:12]:
        print(f"  y={y} -> {lab} (score={sc:.2f})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
