# Test Samples for Input Reading (SF6 On-Screen Inputs)

Inputs appear **left and right** and **stream downward**. These samples will help implement and validate the reader.

---

## 1. Screenshots (single frame)

**What to capture:** One frame where the input display is clearly visible on both sides.

| Sample | Description | Use |
|--------|-------------|-----|
| **Static full frame** | Pause replay at a moment with several inputs visible on left and right. 1080p (or your usual res). | Define exact **p1_region** and **p2_region** (x, y, width, height) and confirm “stream downward” direction. |
| **Left strip only** | Crop to **only** the left input column (no HUD, no stage). | Tune OCR/allowlist and region height; check for false positives. |
| **Right strip only** | Same for right column. | Same as left; confirm symmetry or differences. |
| **Minimal input** | Frame with 1–2 inputs per side. | Check that we don’t require “full column” to work. |
| **Heavy input** | Frame with many inputs (fast sequence). | Test OCR on dense text/icons and vertical ordering. |

**Format:** PNG preferred. Name by content, e.g. `input_left_static.png`, `input_right_heavy.png`.

---

## 2. Short video clips (5–15 seconds)

**What to capture:** Same replay, input display ON, 1080p (or fixed res).

| Sample | Description | Use |
|--------|-------------|-----|
| **Known sequence** | Perform a **known** sequence (e.g. “6P, 2K, 236LP” on P1 only) and record. | Ground truth: compare our `input_p1` over time to the list you actually did. |
| **Both players** | Short match segment with both sides pressing buttons. | Validate P1 vs P2 separation and no cross-talk. |
| **Stream-down only** | Only inputs changing (e.g. training mode, no stage motion). | Isolate input detection from other UI/motion. |
| **Full match segment** | 30–60 s with rounds, KOs, and input display on. | Test under real conditions (state changes, camera, effects). |

**Format:** Same as your pipeline (e.g. MP4). Keep resolution and aspect ratio consistent.

---

## 3. Reference assets (if using icon matching)

If the game shows **icons** (not text):

| Sample | Description | Use |
|--------|-------------|-----|
| **Single icon per type** | One clean image per button/direction (LP, MP, HP, LK, MK, HK, 1–9, etc.). | Template images for matching. |
| **Icon grid** | One screenshot with many icons visible; label each. | Map “what we see” to “what we call it” and extract templates. |

**Format:** PNG, one file per icon or one annotated grid.

---

## 4. Ground-truth table (for validation)

A small CSV or table helps validate:

| Time (s) | P1 inputs (expected) | P2 inputs (expected) |
|----------|----------------------|----------------------|
| 0.0      | 6P                   |                      |
| 0.5      | 2K                   | 2MK                  |
| 1.0      | 236LP                | 623HK                |
| ...      | ...                  | ...                  |

Create this for **one** short clip (e.g. “known sequence” above). Then compare:
- Our `input_p1` / `input_p2` per frame (or per second) to the table.
- Count **hits** (correct), **misses** (we missed an input), **false positives** (we read something that wasn’t there).

---

## 5. Where to put samples in the repo

Suggested layout:

```
SmartCV-SF6/
  test_samples/
    input_reading/
      screenshots/
        full_frame_inputs.png
        left_strip.png
        right_strip.png
      clips/
        known_sequence_p1.mp4
        both_players_15s.mp4
      ground_truth/
        known_sequence_p1.csv
      icons/          (if using template matching)
        LP.png
        6P.png
        ...
```

---

## 6. Quick checklist before coding

- [ ] One full-frame screenshot with input display visible (both sides).
- [ ] Approximate pixel coords for “left column” and “right column” (x, y, width, height at 1080p).
- [ ] One short clip (5–15 s) with a **known** input sequence for P1 (and optionally P2).
- [ ] Ground-truth table for that clip (time → expected inputs).
- [ ] (Optional) Icon reference images if the display is icon-based.

With these, you can implement regions, OCR/icon logic, and validate against ground truth.
