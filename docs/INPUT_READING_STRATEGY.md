# Strategy: Reading On-Screen Inputs (SF6 Replay)

## Layout (SF6 replay input display)
- **P1 inputs:** left column; **P2 inputs:** right column. Cascade downward, newest at top.
- **Each row:** input + frame count. **N** = neutral. P/K = punch/kick; L/M/H = light/medium/heavy (blue/yellow/red on screen).
- “current” line

---

## 1. Detection approach

### Option A: Fixed regions (simplest)
- Define **two vertical strips**: left (e.g. x=0–200) and right (e.g. x=1720–1920) in 1080p coords.
- **Height:** full height or a band (e.g. y=200–880 to avoid HUD top/bottom).
- Each frame: crop left strip and right strip → run OCR (or icon detection) on each.
- **Pros:** Easy, works if layout is consistent. **Cons:** May pick up non-input UI; needs tuning.

### Option B: Locate “input column” first
- Search for a **stable visual anchor** (e.g. a vertical bar, label, or icon column) that marks the left/right input area.
- Once found, crop a fixed-width region to the left/right of that anchor.
- **Pros:** More robust if UI shifts. **Cons:** Need to define and detect the anchor.

### Option C: Icon-based (not OCR)
- If inputs are **icons** (buttons, directions), use **template matching** or a **small classifier** per icon.
- Build a set of reference images: each button (LP, MP, HP, LK, MK, HK), each direction (1–9), maybe combined (e.g. “6P” as one asset).
- Each frame: slide over the strip, match templates, output sequence.
- **Pros:** Works with non-text, robust to font. **Cons:** Need reference assets; more engineering.

**Recommendation:** Start with **Option A** (fixed regions + OCR). If the stream is **icons**, add **Option C** (templates) for the icons and use OCR only for any text labels.

---

## 2. Per-frame vs temporal stream

- **Per-frame:** Each frame we output “what’s visible in the input regions right now.” Downstream can merge/dedupe.
- **Stream over time:** Track when new icons/text appear (e.g. compare to previous frame) and append to a timeline. Gives “input log” per player.

**Recommendation:** Implement **per-frame** first (what’s in the crop this frame). Add **temporal merging** later (dedupe, order by time) if you need a single input stream.

---

## 3. Region and coordinate strategy

- **Coordinate system:** Define everything in **1080p base** (1920×1080); scale by `scale_x`, `scale_y` for other resolutions.
- **Left strip (P1):** e.g. `x=0, y=Y_TOP, w=W, h=H` (Y_TOP so the “stream” is in frame).
- **Right strip (P2):** e.g. `x=1920-W, y=Y_TOP, w=W, h=H`.
- **Config:** Put `p1_region` and `p2_region` in `config.ini` as `x,y,width,height` so you can tune without code changes.
- **Stream downward:** If new inputs appear at **top** of the strip and push down, crop the full strip; OCR will see multiple “lines” (or use a list of horizontal bands and read each). If new inputs appear at **bottom**, same idea—crop the strip and parse top-to-bottom.

---

## 4. OCR vs icon matching

- **If it’s text** (e.g. “6P”, “2MK”, “236LP”): use **OCR** with an **allowlist** (digits, P, K, L, M, H, S, etc.). One region can return multiple text blocks; order by vertical position to get “stream” order.
- **If it’s icons:** use **template images** per input type. For each strip, run template matching at multiple vertical positions (or sliding window), threshold, and output a list of (position, input_type). Then sort by position to get stream order.

**Recommendation:** Start with OCR on the two strips. If results are noisy or the game uses only icons, collect **reference icon images** and add template matching.

---

## 5. Output format

- **Payload fields:** e.g. `input_p1` and `input_p2` as **strings** (OCR result for this frame) or **arrays** (list of detected inputs this frame).
- **Optional:** `input_stream_p1` / `input_stream_p2` as arrays of `{ "input": "6P", "frame_index": N }` if you add temporal merging.
- Keep **one line per frame** in the JSON/WebSocket so the consumer can align with video time.

---

## 6. Test samples that would help

See **TEST_SAMPLES.md** (or section below) for the list of recommended samples and how to use them.

---

## 7. Implementation order

1. **Confirm layout:** Use test screenshots (see below) to lock left/right regions and “stream downward” direction.
2. **Config regions:** Add `[input_display]` `p1_region` / `p2_region` (and optional `p1_stream_top_y`, `p2_stream_top_y` if you split into bands).
3. **Per-frame read:** Crop regions → OCR (and/or icon match) → fill `input_p1` / `input_p2` (or arrays).
4. **Validate:** Run on short clips with known inputs; compare output to what you see.
5. **Temporal (optional):** Dedupe and order by time; add `input_stream_*` if needed.
