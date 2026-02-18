# SF6 input display: on-screen icons

The replay input overlay uses **icons** (not text) for directions and buttons. This doc maps what you see on screen to our notation (numpad + P/K, L/M/H) for icon/template matching.

## Direction (character movement)

- **Direction arrows** = movement of the character. Map to **numpad notation** (1–9):
  - Arrow direction on screen ↔ same numpad (e.g. right = 6, down-left = 1, etc.; see `NUMPAD_NOTATION.md`).
- **White “N” in a circle** = **neutral** (numpad 5, no direction).

## Attack icons (color = strength, shape = punch vs kick)

| Color   | Meaning   | Fist icon | Foot icon |
|---------|-----------|-----------|-----------|
| **Red**   | Heavy (H) | HP        | HK        |
| **Blue**  | Medium (M)| MP        | MK        |
| **Yellow**| Light (L) | LP        | LK        |

- So: **red fist** = HP, **blue fist** = MP, **yellow fist** = LP; **red foot** = HK, **blue foot** = MK, **yellow foot** = LK.

## Row on screen

Each row = **direction** (arrow or N) + optional **attack** (colored fist/foot) + **frame count** (number).  
Example: right arrow + red fist + “5” → `6HP 5`.

## Button detection (implementation)

- Set **`direction_enabled = false`** in `[input_display]` to skip arrow detection.
- **Button (H/M/L):** Right third of each row is the button zone; HSV color counts (red/blue/yellow) → H, M, or L. P vs K not yet distinguished.

## Direction detection (implementation)

- **Templates:** `img/input_directions/` has synthetic arrow/N templates (from `scripts/generate_direction_templates.py`). Game-art templates can be extracted to `img/input_directions/extracted/` from a strip screenshot or from the video’s first frame:  
  `python scripts/extract_direction_templates_from_image.py --video inputs_on_sample.mp4`
- **P2 (rotation-based):** One arrow (6 = right) rotated 0°, 45°, …, 315° CCW; best match → numpad. Prefer arrow over N when arrow scores higher.
- **Row centers:** Evenly spaced; P2 last row: multiple y samples, take best score.

### Alternative: contour-based (no templates)

Set **`direction_method = contour`** in `config.ini` under `[input_display]`. This method:

1. Crops the same direction zone, then thresholds (Otsu) to get a binary shape.
2. Finds contours; ignores very round ones (N is detected as a circle).
3. For the best arrow-like contour: **centroid** and **tip** = contour point farthest from centroid.
4. **Angle** = atan2(tip − center) → rounded to 45° → numpad (0°→6, 90°→2, 180°→4, 270°→8, etc.).

**Pros:** No template assets; works from geometry (right = 6, 90° CW = 2).  
**Cons:** Sensitive to threshold and to other shapes in the crop (numbers, buttons); may mis-detect if the zone isn’t just the arrow. Try it if template matching is wrong on your capture; switch back to `template` if results are worse.
