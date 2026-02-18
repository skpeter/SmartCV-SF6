#!/usr/bin/env python3
"""Read P1 and P2 input display from the first frame of the video.
Usage: python read_first_frame_inputs.py [video_path]
  video_path = from config.ini if omitted.
Prints raw OCR text and row-by-row (newest at top) for both players.
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
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    from core.core import (
        read_text,
        read_text_with_positions,
        read_rows_fixed,
        read_p1_frame_counts_full_column,
        read_p1_frame_counts_per_row,
        read_p2_frame_counts_full_column,
        read_p2_buttons_column,
        read_p2_direction_column,
        get_region_crop_np,
        detect_fade_line_ys,
        row_bounds_from_frame_count_ocr,
        get_p2_content_insets,
        detect_input_directions_for_rows,
        detect_buttons_for_rows,
    )
    direction_enabled = config.getboolean("input_display", "direction_enabled", fallback=False)
    allowlist = "0123456789NLPKMH+- "
    rows_per_player = config.getint("input_display", "rows_per_player", fallback=0)
    margin_top = int(int(config.get("input_display", "row_margin_top", fallback="0")) * scale_y)
    margin_bottom = int(int(config.get("input_display", "row_margin_bottom", fallback="0")) * scale_y)
    p1_left_inset = int(config.get("input_display", "p1_left_inset", fallback="50")) * scale_x
    p1_left_inset = int(p1_left_inset)
    p1_frm_ratio = float(config.get("input_display", "p1_frm_width_ratio", fallback="0.20"))
    use_detected_boundaries = config.getboolean("input_display", "use_detected_row_boundaries", fallback=False)
    row_boundaries_method = config.get("input_display", "row_boundaries_method", fallback="fade_equal").strip().lower()
    row_bottom_padding = int(float(config.get("input_display", "row_bottom_padding", fallback="2")) * scale_y)
    row_top_padding = int(float(config.get("input_display", "row_top_padding", fallback="0")) * scale_y)
    row_band_overlap = int(float(config.get("input_display", "row_band_overlap", fallback="0")) * scale_y)
    p1_oldest_keep = config.getint("input_display", "p1_frame_count_oldest_keep", fallback=6)
    p1_top_contrast = config.getfloat("input_display", "p1_frame_count_top_contrast", fallback=2.5)
    p1_top_low_text = config.getfloat("input_display", "p1_frame_count_top_low_text", fallback=0.08)
    p2_oldest_keep = config.getint("input_display", "p2_frame_count_oldest_keep", fallback=6)
    p2_top_contrast = config.getfloat("input_display", "p2_frame_count_top_contrast", fallback=2.5)
    p2_top_low_text = config.getfloat("input_display", "p2_frame_count_top_low_text", fallback=0.1)
    p2_white_on_dark = config.getboolean("input_display", "p2_frame_count_white_on_dark", fallback=True)
    p2_white_threshold = config.getint("input_display", "p2_frame_count_white_threshold", fallback=140)
    _p1_known_str = config.get("input_display", "p1_frame_count_known_oldest_6", fallback="").strip()
    p1_known_oldest_6 = [str(v).strip() for v in _p1_known_str.split(",") if v.strip()] if _p1_known_str else []
    _p2_btn_rows_str = config.get("input_display", "p2_button_rows_oldest_6", fallback="").strip()
    p2_button_rows_oldest_6 = set(int(v.strip()) for v in _p2_btn_rows_str.split(",") if v.strip()) if _p2_btn_rows_str else set()

    # Raw concatenated text (same as payload input_p1 / input_p2)
    t1 = read_text(img, region1, colored=True, contrast=2, allowlist=allowlist, low_text=0.3)
    t2 = read_text(img, region2, colored=True, contrast=2, allowlist=allowlist, low_text=0.3)
    raw_p1 = " ".join(t1).strip() if t1 else ""
    raw_p2 = " ".join(t2).strip() if t2 else ""

    x1, y1, rw1, rh1 = region1
    crop1 = get_region_crop_np(img, region1, contrast=2)
    crop2 = get_region_crop_np(img, region2, contrast=2)
    rows2_btn_ocr = []
    rows2_dir_ocr = []

    # Row-by-row: row bounds from frame_count_guide (OCR positions), fade_equal, or fade_detected
    if rows_per_player > 0:
        rb1 = None
        rb2 = None
        if row_boundaries_method == "frame_count_guide":
            # P1: frame column is in content region (left inset); use full height for guide
            region1_for_guide = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, rh1)
            rb1 = row_bounds_from_frame_count_ocr(img, region1_for_guide, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=False, frm_width_ratio=p1_frm_ratio)
            rb2 = row_bounds_from_frame_count_ocr(img, region2, rows_per_player, contrast=2, allowlist="0123456789 ", low_text=0.3, is_p2=True)
        if rb1 is None or rb2 is None:
            row_bounds1 = detect_fade_line_ys(crop1, use_detected_boundaries=use_detected_boundaries)
            row_bounds2 = detect_fade_line_ys(crop2, use_detected_boundaries=use_detected_boundaries)
            if rb1 is None:
                rb1 = row_bounds1 if row_bounds1 is not None and len(row_bounds1) >= 2 else None
            if rb2 is None:
                rb2 = row_bounds2 if row_bounds2 is not None and len(row_bounds2) >= 2 else None
        if rb1 is None and rb2 is not None:
            rb1 = rb2
        if rb2 is None and rb1 is not None:
            rb2 = rb1
        # P1: keep all rows so printed row 1 = top physical row, row 19 = bottom physical row (no drop/add).
        # P2: drop first (newest) row and add one row at the bottom (P2 Frm right).
        if rb2 is not None and len(rb2) >= 2:
            _, _, rw2_early, rh2_early = region2
            last = rb2[-1]
            row_h = last[1] - last[0]
            new_bottom = (last[1], min(last[1] + row_h, rh2_early))
            rb2 = rb2[1:] + [new_bottom]
        if rb1 is not None:
            heights1 = [b[1] - b[0] for b in rb1]
            same1 = len(set(heights1)) == 1
            print("(P1 row heights px):", heights1, "- all same:", same1)
        if rb2 is not None:
            heights2 = [b[1] - b[0] for b in rb2]
            same2 = len(set(heights2)) == 1
            print("(P2 row heights px):", heights2, "- all same:", same2)
        # P2: crop width using second-oldest row as guide (button + frame count)
        x2, y2, rw2, rh2 = region2
        region2_eff = region2
        if rb2 is not None:
            p2_left_inset_px, p2_right_inset_px = get_p2_content_insets(crop2, rb2, margin=5)
            region2_eff = (x2 + p2_left_inset_px, y2, max(1, rw2 - p2_left_inset_px - p2_right_inset_px), rh2)
            crop2 = get_region_crop_np(img, region2_eff, contrast=2)
        # P1 content region: drop empty first column, bottom = oldest row
        h1_content = rb1[-1][1] if rb1 else rh1
        region1_content = (x1 + p1_left_inset, y1, rw1 - p1_left_inset, h1_content)
        # P1 calibration: if known oldest values given (5 or 6), try both columns and thresholds; use best (column, threshold)
        p1_white_threshold = p2_white_threshold
        p1_calibration_column = 0  # 0 = first (frame), 1 = second (same white-on-grey style)
        n_known = len(p1_known_oldest_6)
        if n_known >= 5 and p2_white_on_dark:
            best_score, best_th, best_col = -1, p2_white_threshold, 0
            for th in [100, 120, 140, 160, 180]:
                for col_idx in (0, 1):
                    trial = read_p1_frame_counts_full_column(img, region1_content, rb1, contrast=2, low_text=0.15, white_on_dark=True, white_threshold=th, frm_width_ratio=p1_frm_ratio, column_index=col_idx)
                    if len(trial) >= n_known:
                        last_n = [(trial[i][1] or "").strip() for i in range(-n_known, 0)]
                        score = sum(1 for i in range(n_known) if last_n[i] == p1_known_oldest_6[i])
                        if score > best_score:
                            best_score, best_th, best_col = score, th, col_idx
            p1_white_threshold = best_th
            p1_calibration_column = best_col
            col_label = "first" if best_col == 0 else "second"
            print(f"(P1 calibration from known oldest {n_known}: best column={col_label}, threshold={best_th}, matches={best_score}/{n_known})")
        rows1_bands = read_rows_fixed(img, region1_content, rows_per_player, contrast=2, allowlist=allowlist, low_text=0.3, margin_top=margin_top, margin_bottom=margin_bottom, row_bounds=rb1, frame_count_only=True, is_p2=False, frm_width_ratio=p1_frm_ratio, row_bottom_padding=row_bottom_padding, row_top_padding=row_top_padding, row_band_overlap=row_band_overlap)
        rows1_full = read_p1_frame_counts_full_column(img, region1_content, rb1, contrast=2, low_text=0.15, white_on_dark=p2_white_on_dark, white_threshold=p1_white_threshold, frm_width_ratio=p1_frm_ratio, column_index=p1_calibration_column)
        rows1_per_row = read_p1_frame_counts_per_row(img, region1_content, rb1, contrast=2, frm_width_ratio=p1_frm_ratio, band_padding=4, low_text=0.08, vote_thresholds=[100, 120, 140, 160])
        rows1 = []
        for i in range(len(rows1_bands)):
            y_center, text_band = rows1_bands[i][0], (rows1_bands[i][1] or "").strip()
            text_full = (rows1_full[i][1] if i < len(rows1_full) else "").strip()
            text_voted = (rows1_per_row[i][1] if i < len(rows1_per_row) else "").strip()
            text = text_full or text_voted or text_band
            rows1.append((y_center, text))
        n1 = len(rows1)
        n_oldest_keep_p1 = max(0, min(p1_oldest_keep, n1))
        n_newer_p1 = max(0, n1 - n_oldest_keep_p1)
        if n_newer_p1 > 0 and rb1 is not None and len(rb1) >= n_newer_p1:
            x1c, y1c, w1c, h1c = region1_content
            top_height_p1 = rb1[n_newer_p1 - 1][1]
            top_region_p1 = (x1c, y1c, w1c, min(top_height_p1, h1c))
            rows1_top = read_p1_frame_counts_full_column(img, top_region_p1, rb1[:n_newer_p1], contrast=p1_top_contrast, low_text=p1_top_low_text, white_on_dark=p2_white_on_dark, white_threshold=p1_white_threshold, frm_width_ratio=p1_frm_ratio, column_index=p1_calibration_column)
            for i in range(min(n_newer_p1, len(rows1_top))):
                t = (rows1_top[i][1] or "").strip()
                current = (rows1[i][1] or "").strip()
                if t and not current:
                    rows1[i] = (rows1[i][0], t)
        rows2_bands = read_rows_fixed(img, region2_eff, rows_per_player, contrast=2, allowlist=allowlist, low_text=0.3, margin_top=margin_top, margin_bottom=margin_bottom, row_bounds=rb2, frame_count_only=True, is_p2=True, row_bottom_padding=row_bottom_padding, row_top_padding=row_top_padding, row_band_overlap=row_band_overlap)
        rows2_full = read_p2_frame_counts_full_column(img, region2_eff, rb2, contrast=2, low_text=0.15, white_on_dark=p2_white_on_dark, white_threshold=p2_white_threshold)
        rows2 = []
        for i in range(len(rows2_bands)):
            y_center, text_band = rows2_bands[i][0], (rows2_bands[i][1] or "").strip()
            text_full = (rows2_full[i][1] if i < len(rows2_full) else "").strip()
            text = text_full if text_full else text_band
            rows2.append((y_center, text))
        n2 = len(rows2)
        n_oldest_keep = max(0, min(p2_oldest_keep, n2))
        n_newer = max(0, n2 - n_oldest_keep)
        if n_newer > 0 and rb2 is not None and len(rb2) >= n_newer:
            x2e, y2e, w2e, h2e = region2_eff
            top_height = rb2[n_newer - 1][1]
            top_region = (x2e, y2e, w2e, min(top_height, h2e))
            rows2_top = read_p2_frame_counts_full_column(img, top_region, rb2[:n_newer], contrast=p2_top_contrast, low_text=p2_top_low_text, white_on_dark=p2_white_on_dark, white_threshold=p2_white_threshold)
            for i in range(min(n_newer, len(rows2_top))):
                t = (rows2_top[i][1] or "").strip()
                current = (rows2[i][1] or "").strip()
                if t and not current:
                    rows2[i] = (rows2[i][0], t)
        crop1 = get_region_crop_np(img, region1_content, contrast=2)
        rw1, rh1 = region1_content[2], region1_content[3]
        rw2, rh2 = region2_eff[2], region2_eff[3]
        # P2: read each column per row (Btn, Dir, Frm) for full input
        if rb2 is not None and len(rb2) == len(rows2):
            rows2_btn_ocr = read_p2_buttons_column(img, region2_eff, rb2, contrast=2, low_text=0.15, white_on_dark=p2_white_on_dark, white_threshold=p2_white_threshold)
            rows2_dir_ocr = read_p2_direction_column(img, region2_eff, rb2, contrast=2, low_text=0.15, white_on_dark=p2_white_on_dark, white_threshold=p2_white_threshold)
    else:
        rows1 = read_text_with_positions(img, region1, contrast=2, allowlist=allowlist, low_text=0.3)
        rows2 = read_text_with_positions(img, region2, contrast=2, allowlist=allowlist, low_text=0.3)
        _, _, rw2, rh2 = region2
    if direction_enabled:
        dirs1 = detect_input_directions_for_rows(crop1, [r[0] for r in rows1], rw1, rh1, template_key="p1") if rows1 else []
        dirs2 = detect_input_directions_for_rows(crop2, [r[0] for r in rows2], rw2, rh2, template_key="p2") if rows2 else []
    else:
        dirs1 = [None] * len(rows1) if rows1 else []
        dirs2 = [None] * len(rows2) if rows2 else []
    btns1 = detect_buttons_for_rows(crop1, [r[0] for r in rows1], rw1, rh1) if rows1 else []
    btns2 = detect_buttons_for_rows(crop2, [r[0] for r in rows2], rw2, rh2, is_p2=True) if rows2 else []
    # P2: only rows listed in p2_button_rows_oldest_6 have button circles in the 6 oldest; rest = no button
    if rows2 and p2_button_rows_oldest_6 and len(btns2) >= len(rows2):
        n2_btn = len(rows2)
        for i in range(max(0, n2_btn - 6), n2_btn):
            if (i + 1) not in p2_button_rows_oldest_6:
                btns2[i] = None

    print("First frame — inputs")
    print("====================")
    print("P1 (raw):", repr(raw_p1))
    print("P2 (raw):", repr(raw_p2))
    print()
    # Full input: per row, per column (Frm | Dir | Btn for P1, Btn | Dir | Frm for P2)
    def dir_label(d):
        if d is None:
            return "—"
        return "N" if d == "5" else str(d)
    if rows1 and len(rows1) > 0:
        print("P1 full input (per row, per column). Columns: Frm | Dir | Btn (left→right). Row 1 = newest, Row N = oldest.")
        for i in range(len(rows1)):
            frm = (rows1[i][1] or "").strip() or "—"
            d = dirs1[i] if i < len(dirs1) else None
            btn = (btns1[i] if i < len(btns1) else None) or "—"
            print(f"  Row {i+1:2}:  Frm={frm:>3}  Dir={dir_label(d):>2}  Btn={btn}")
        print()
    if rows2 and len(rows2) > 0:
        print("P2 full input (per row, per column). Columns: Btn | Dir | Frm (left→right). Row 1 = newest, Row N = oldest.")
        n2 = len(rows2)
        for i in range(n2):
            if p2_button_rows_oldest_6 and i >= n2 - 6 and (i + 1) not in p2_button_rows_oldest_6:
                btn = "—"
            else:
                btn = (btns2[i] if i < len(btns2) else None) or (rows2_btn_ocr[i][1].strip() if rows2_btn_ocr and i < len(rows2_btn_ocr) and rows2_btn_ocr[i][1] else "") or "—"
            d = dirs2[i] if i < len(dirs2) else None
            dir_val = dir_label(d)
            if dir_val == "—" and rows2_dir_ocr and i < len(rows2_dir_ocr) and (rows2_dir_ocr[i][1] or "").strip():
                dir_val = (rows2_dir_ocr[i][1] or "").strip().upper()
                if dir_val == "5":
                    dir_val = "N"
            frm = (rows2[i][1] or "").strip() or "—"
            print(f"  Row {i+1:2}:  Btn={btn}  Dir={dir_val:>2}  Frm={frm:>3}")
        # Oldest 6 P2 inputs (rows 14–19 when N=19; last 6 rows)
        k = 6
        oldest_6_start = max(0, n2 - k)
        oldest_6_rows = []
        for i in range(oldest_6_start, n2):
            if p2_button_rows_oldest_6 and (i + 1) not in p2_button_rows_oldest_6:
                btn = "—"
            else:
                btn = (btns2[i] if i < len(btns2) else None) or (rows2_btn_ocr[i][1].strip() if rows2_btn_ocr and i < len(rows2_btn_ocr) and rows2_btn_ocr[i][1] else "") or "—"
            d = dirs2[i] if i < len(dirs2) else None
            dir_val = dir_label(d)
            if dir_val == "—" and rows2_dir_ocr and i < len(rows2_dir_ocr) and (rows2_dir_ocr[i][1] or "").strip():
                dir_val = (rows2_dir_ocr[i][1] or "").strip().upper()
                if dir_val == "5":
                    dir_val = "N"
            frm = (rows2[i][1] or "").strip() or "—"
            oldest_6_rows.append(f"Row {i+1}: Btn={btn} Dir={dir_val} Frm={frm}")
        print("  → Oldest 6 P2 inputs (oldest last):", " | ".join(oldest_6_rows))
        print()
    print("P1 rows (top = newest). Each row = Direction | Button | Frame count:")
    print("  (Direction = off; Button = color H/M/L; Frame count = OCR)")
    for i, (row, direction, btn) in enumerate(zip(rows1, dirs1, btns1), 1):
        _, text = row
        dir_label = "—" if not direction_enabled else ("N" if direction == "5" else (direction if direction else "?"))
        btn_label = btn if btn else "—"
        print(f"  {i}. Direction: {dir_label} | Button: {btn_label} | Frame count: {text}")
    if not rows1:
        print("  (none)")
    elif rows1:
        # Rows where OCR shows N and 1 (neutral for 1 frame)
        p1_n1_rows = [i for i, r in enumerate(rows1, 1) if r[1] and "N" in r[1].upper() and "1" in r[1]]
        if p1_n1_rows:
            print("  → Row(s) with N for 1 frame (OCR):", ", ".join(map(str, p1_n1_rows)))
        b1 = btns1[0] if btns1 else "—"
        d1_label = "—" if not direction_enabled else ("N" if dirs1[0] == "5" else (dirs1[0] if dirs1[0] else "?"))
        print(f"  → Newest P1: Direction: {d1_label} | Button: {b1} | Frame count: {rows1[0][1]}")
        b1_old = btns1[-1] if btns1 else "—"
        d1_old_label = "—" if not direction_enabled else ("N" if dirs1[-1] == "5" else (dirs1[-1] if dirs1[-1] else "?"))
        print(f"  → Oldest P1:  Direction: {d1_old_label} | Button: {b1_old} | Frame count: {rows1[-1][1]}")
        # Four oldest P1 frame counts (oldest last)
        n = len(rows1)
        oldest_four = [rows1[i][1] or "(empty)" for i in range(max(0, n - 4), n)]
        if oldest_four:
            print("  → Four oldest P1 frame counts:", ", ".join(oldest_four))
        # First column (frame count) per row: row number → value
        first_col = [f"{i}: {rows1[i-1][1] or '—'}" for i in range(1, n + 1)]
        print("  → P1 first column (numbers) per row:", ", ".join(first_col))
        # Second column (same white-on-grey style) for comparison
        if rb1 is not None and len(rb1) == n:
            rows1_col2 = read_p1_frame_counts_full_column(img, region1_content, rb1, contrast=2, low_text=0.15, white_on_dark=p2_white_on_dark, white_threshold=p1_white_threshold, frm_width_ratio=p1_frm_ratio, column_index=1)
            second_col = [f"{i}: {(rows1_col2[i-1][1] or '').strip() or '—' if i - 1 < len(rows1_col2) else '—'}" for i in range(1, n + 1)]
            print("  → P1 second column (numbers) per row:", ", ".join(second_col))
    print()
    print("P2 rows (top = newest). Each row = Direction | Button | Frame count:")
    for i, (row, direction, btn) in enumerate(zip(rows2, dirs2, btns2), 1):
        _, text = row
        dir_label = "—" if not direction_enabled else ("N" if direction == "5" else (direction if direction else "?"))
        btn_label = btn if btn else "—"
        print(f"  {i}. Direction: {dir_label} | Button: {btn_label} | Frame count: {text}")
    if not rows2:
        print("  (none)")
    elif rows2:
        b2 = btns2[0] if btns2 else "—"
        d2_label = "—" if not direction_enabled else ("N" if dirs2[0] == "5" else (dirs2[0] if dirs2[0] else "?"))
        print(f"  → Newest P2: Direction: {d2_label} | Button: {b2} | Frame count: {rows2[0][1]}")
        b2_old = btns2[-1] if btns2 else "—"
        d2_old_label = "—" if not direction_enabled else ("N" if dirs2[-1] == "5" else (dirs2[-1] if dirs2[-1] else "?"))
        print(f"  → Oldest P2:  Direction: {d2_old_label} | Button: {b2_old} | Frame count: {rows2[-1][1]}")
        n2 = len(rows2)
        oldest_four_p2 = [rows2[i][1] or "(empty)" for i in range(max(0, n2 - 4), n2)]
        if oldest_four_p2:
            print("  → Four oldest P2 frame counts:", ", ".join(oldest_four_p2))
        # All P2 frame counts, row 1 (newest) to row N (oldest). Every row has a number on the overlay; "—" = OCR missed it.
        all_p2_fc = [rows2[i][1] or "—" for i in range(n2)]
        print("  → All P2 frame counts:", ", ".join(all_p2_fc))
        # Second oldest P2: column 1 = Button, column 2 = Direction, column 3 = Frame count
        idx_2nd_oldest = n2 - 2
        if idx_2nd_oldest >= 0:
            btn_2 = (btns2[idx_2nd_oldest] if btns2 and idx_2nd_oldest < len(btns2) else None) or "—"
            dir_2 = dirs2[idx_2nd_oldest] if dirs2 and idx_2nd_oldest < len(dirs2) else None
            dir_2_label = "—" if not direction_enabled else ("N" if dir_2 == "5" else (dir_2 if dir_2 else "?"))
            fc_2 = rows2[idx_2nd_oldest][1] or "—"
            print("  → Second oldest P2: Column 1 (Button):", btn_2, "| Column 2 (Direction):", dir_2_label, "| Column 3 (Frame count):", fc_2)
    return 0

if __name__ == "__main__":
    sys.exit(main())
