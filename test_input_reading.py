#!/usr/bin/env python3
"""Test different OCR/reading approaches on the same P1 frame; compare outputs.
Usage: python test_input_reading.py [video_path]
Uses first frame. Ground truth (for comparison): top rows 3 19, 6 4, 6 5; 4th = 5HP 5; bottom = N 1.
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

# Ground truth tokens we expect to see (direction/button/frames)
GROUND_TRUTH_TOKENS = {"3", "6", "5", "N", "4", "HP", "19", "4", "5", "1", "14"}

def get_frame_and_region(video_path):
    video_path = os.path.expanduser(video_path.strip())
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None, None, None
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None, None, None
    h, w = frame.shape[:2]
    scale_x, scale_y = w / 1920, h / 1080
    p1 = config.get("input_display", "p1_region", fallback="0,200,280,700")
    parts = [int(p.strip()) for p in p1.split(",") if p.strip()]
    if len(parts) != 4:
        return None, None, None
    x, y, rw, rh = parts
    region = (int(x * scale_x), int(y * scale_y), int(rw * scale_x), int(rh * scale_y))
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return img, region, frame

def run_approach(name, img, region, reader, **kwargs):
    """Run reader on crop; return list of (y, x, text). reader(img_crop_np, **kwargs) -> list of (y, x, text) or raw."""
    x, y, w, h = region
    crop = img.crop((x, y, x + w, y + h))
    crop_np = np.array(crop)
    return reader(crop_np, **kwargs)

def main():
    video_path = sys.argv[1] if len(sys.argv) > 1 else config.get("settings", "video_path", fallback="inputs_on_sample.mp4")
    img, region, frame_bgr = get_frame_and_region(video_path)
    if img is None:
        print("Could not load frame or region.")
        return 1

    from core.core import reader

    x, y, w, h = region
    crop_rgb = np.array(img.crop((x, y, x + w, y + h)))
    crop_gray = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
    allowlist = "0123456789NLPKMH+- "

    approaches = []

    # 1) Baseline: grayscale, contrast 2, allowlist
    gray_c2 = cv2.convertScaleAbs(crop_gray, alpha=2, beta=-100)
    raw1 = reader.readtext(gray_c2, paragraph=False, allowlist=allowlist, low_text=0.3)
    texts1 = [t[1].strip() for t in raw1]
    approaches.append(("Baseline (gray, contrast=2, allowlist)", texts1))

    # 2) No allowlist
    raw2 = reader.readtext(gray_c2, paragraph=False, low_text=0.3)
    texts2 = [t[1].strip() for t in raw2]
    approaches.append(("No allowlist", texts2))

    # 3) Lower contrast (1.5)
    gray_c15 = cv2.convertScaleAbs(crop_gray, alpha=1.5, beta=-75)
    raw3 = reader.readtext(gray_c15, paragraph=False, allowlist=allowlist, low_text=0.3)
    texts3 = [t[1].strip() for t in raw3]
    approaches.append(("Contrast 1.5", texts3))

    # 4) Higher contrast (2.5)
    gray_c25 = cv2.convertScaleAbs(crop_gray, alpha=2.5, beta=-125)
    raw4 = reader.readtext(gray_c25, paragraph=False, allowlist=allowlist, low_text=0.3)
    texts4 = [t[1].strip() for t in raw4]
    approaches.append(("Contrast 2.5", texts4))

    # 5) More sensitive (low_text=0.2)
    raw5 = reader.readtext(gray_c2, paragraph=False, allowlist=allowlist, low_text=0.2)
    texts5 = [t[1].strip() for t in raw5]
    approaches.append(("low_text=0.2", texts5))

    # 6) Color (BGR) - EasyOCR can take color
    raw6 = reader.readtext(cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR), paragraph=False, allowlist=allowlist, low_text=0.3)
    texts6 = [t[1].strip() for t in raw6]
    approaches.append(("Color (BGR)", texts6))

    # 7) Inverted (white on black)
    inv = cv2.bitwise_not(gray_c2)
    raw7 = reader.readtext(inv, paragraph=False, allowlist=allowlist, low_text=0.3)
    texts7 = [t[1].strip() for t in raw7]
    approaches.append(("Inverted (white on black)", texts7))

    # Score: how many ground-truth tokens appear (as substring) in the detected text
    def score(texts):
        full = " ".join(texts)
        found = [t for t in GROUND_TRUTH_TOKENS if t in full]
        return len(found), found

    print("Ground truth tokens we want: ", sorted(GROUND_TRUTH_TOKENS))
    print()
    print("Approach                                    | # detections | Score (GT tokens found) | All detected text")
    print("-" * 120)
    best_score, best_name = -1, None
    for name, texts in approaches:
        sc, found = score(texts)
        if sc > best_score:
            best_score, best_name = sc, name
        text_preview = " ".join(texts)[:55] + ("..." if len(" ".join(texts)) > 55 else "")
        print(f"{name:42} | {len(texts):12} | {sc:2} {str(found):22} | {text_preview}")
    print()
    print(f"Best so far: {best_name} (score {best_score})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
