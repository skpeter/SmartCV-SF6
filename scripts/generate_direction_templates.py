#!/usr/bin/env python3
"""Generate direction templates for input overlay: N (neutral) + numpad 1-9 (arrows).
Saves to img/input_directions/n.png, 1.png ... 9.png. Numpad 6 = right = 0°."""
import os
import math
import cv2
import numpy as np

SIZE = 32
CENTER = SIZE // 2
RADIUS = 12  # arrow length from center
THICKNESS = 3

# Numpad: 6=right(0°), 3=down-right(-45°), 2=down(-90°), 1=down-left(-135°), 4=left(180°), 7=up-left(225°), 8=up(270°), 9=up-forward(315°)
NUMPAD_ANGLE_DEG = {6: 0, 3: 45, 2: 90, 1: 135, 4: 180, 7: 225, 8: 270, 9: 315}
# Arrow from center outward: angle 0 = right (positive x). Our y is image y (down = positive).
# So 0° = right, 90° = down -> we use -angle for standard math (0° right, 90° down).
def angle_to_point(angle_deg):
    rad = math.radians(-angle_deg)
    dx = RADIUS * math.cos(rad)
    dy = RADIUS * math.sin(rad)
    return (int(CENTER + dx), int(CENTER + dy))

def main():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "input_directions")
    os.makedirs(out_dir, exist_ok=True)

    # N (neutral): circle + N
    n_img = np.zeros((SIZE, SIZE), dtype=np.uint8)
    n_img[:] = 40  # dark gray background
    cv2.circle(n_img, (CENTER, CENTER), 10, 255, 2)
    cv2.putText(n_img, "N", (CENTER - 6, CENTER + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1, cv2.LINE_AA)
    cv2.imwrite(os.path.join(out_dir, "n.png"), n_img)

    # Arrows 1-9 (skip 5 = neutral, use N)
    for numpad, angle_deg in NUMPAD_ANGLE_DEG.items():
        arr = np.zeros((SIZE, SIZE), dtype=np.uint8)
        arr[:] = 40
        pt2 = angle_to_point(angle_deg)
        cv2.arrowedLine(arr, (CENTER, CENTER), pt2, 255, THICKNESS, tipLength=0.4)
        cv2.imwrite(os.path.join(out_dir, f"{numpad}.png"), arr)

    print(f"Wrote templates to {out_dir}: n.png, 1-9 (no 5). 5 = neutral = use N.")

if __name__ == "__main__":
    main()
