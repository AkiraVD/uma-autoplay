import easyocr
from PIL import Image
import numpy as np
import re
from typing import List, Tuple
from utils.screenshot import enhance_image_for_ocr_2, enhance_image_for_ocr

reader = easyocr.Reader(["en"], gpu=False)

DIGITS = "0123456789"
# Boxes under this are background noise (character art, UI edges), not a reading.
NUMBER_MIN_CONFIDENCE = 0.4

def box_rect(box):
  xs = [point[0] for point in box]
  ys = [point[1] for point in box]
  return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

def reading_order(results, line_tolerance=12):
  """easyocr returns boxes in detection order, which stops being reading order as
  soon as there is background noise in the region. Sort top-down, then left-right.

  Lines are grouped by how close boxes are to each other, not by rounding their
  y to a fixed grid. Rounding splits a line whenever two boxes straddle a bucket
  edge, however little they actually differ: reading the skill name
  "Dazzl'n ♪ Diver", easyocr returned "Dazzl'n" at y=7 and "♪ Diver" at
  y=5 - two pixels apart, plainly one line - and round(y / 12) put them in
  buckets 1 and 0, so the name came back as "$ Diver Dazzl'n" and matched no
  real skill. "Front Runner Savvy ○" broke the same way.

  Boxes are compared on their vertical centre rather than their top, because a
  line mixes glyph heights - a musical note and a capital D do not start at the
  same y even when they sit on the same line.
  """
  rects = sorted(((box_rect(r[0]), r) for r in results),
                 key=lambda pair: (pair[0][1] + pair[0][3] / 2, pair[0][0]))
  lines = []
  for (x, y, w, h), result in rects:
    centre = y + h / 2
    if lines and abs(centre - lines[-1][0]) <= line_tolerance:
      lines[-1][1].append((x, result))
    else:
      lines.append((centre, [(x, result)]))
  ordered = []
  for _, items in lines:
    ordered.extend(result for _, result in sorted(items, key=lambda pair: pair[0]))
  return ordered

def in_range(value, value_range) -> bool:
  if value_range is None:
    return True
  low, high = value_range
  return low <= value <= high

def extract_text(pil_img: Image.Image) -> str:
  img_np = np.array(pil_img)
  result = reading_order(reader.readtext(img_np))
  texts = [text[1] for text in result]
  return " ".join(texts)

def read_boxes(pil_img: Image.Image, allowlist: str = None) -> List[Tuple[str, float, tuple]]:
  """Recognized text as (text, confidence, (x, y, w, h)) in reading order.

  Callers that need to know *where* a number sat relative to its label - the
  failure bubble is the one that matters - use this instead of extract_text,
  which throws the geometry and the confidence away."""
  kwargs = {"allowlist": allowlist} if allowlist else {}
  results = reading_order(reader.readtext(np.array(pil_img), **kwargs))
  return [(text, float(conf), box_rect(box)) for box, text, conf in results]

def extract_number(pil_img: Image.Image, value_range=None, min_confidence: float = NUMBER_MIN_CONFIDENCE) -> int:
  """Read a single integer, returning -1 when the read is not trustworthy.

  A wrong-but-plausible number is far more damaging than a refusal: on -1 a
  caller can retry or fall back, but nothing downstream can tell that a 3 was
  meant to be a 39. So low-confidence boxes, boxes that belong to a different
  line than the number, and out-of-range values are all rejected rather than
  blindly concatenated into whatever integer falls out."""
  boxes = [b for b in read_boxes(pil_img, allowlist=DIGITS) if b[1] >= min_confidence]
  boxes = [b for b in boxes if re.sub(r"[^\d]", "", b[0])]
  if not boxes:
    return -1

  # easyocr splits a single number into neighbouring boxes often enough that we
  # have to join them, but only when they sit on the same line as the strongest
  # box - otherwise a digit from an adjacent field gets appended silently.
  anchor = max(boxes, key=lambda b: b[1])
  ax, ay, aw, ah = anchor[2]
  anchor_middle = ay + ah / 2
  same_line = [b for b in boxes if abs((b[2][1] + b[2][3] / 2) - anchor_middle) <= ah]
  same_line.sort(key=lambda b: b[2][0])

  digits = "".join(re.sub(r"[^\d]", "", text) for text, conf, rect in same_line)
  if not digits:
    return -1

  value = int(digits)
  return value if in_range(value, value_range) else -1

def get_text_results(processed_img):
  img_np = np.array(processed_img)
  results = reader.readtext(img_np)
  # Fallback to recognize if readtext returns nothing
  if not results:
    try:
      raw_results = reader.recognize(img_np)
      # Normalize to (bbox, text, confidence)
      return [(r[0], r[1], float(r[2])) for r in raw_results]
    except AttributeError:
      return []
  return results

def extract_text_improved(pil_img: Image.Image) -> str:
  """
    Heavier than other extract text but more accurate
  """
  scale_try = [1.0, 2.0, 3.0]
  all_results: List[List[Tuple[List[List[float]], str, float]]] = []

  # try raw image first
  results = get_text_results(pil_img)
  if results:
      all_results.append(results)

  for scale in scale_try:
    proc_img = enhance_image_for_ocr(pil_img, scale)
    results = get_text_results(proc_img)
    if results:
      all_results.append(results)

    # user different enhancer
    proc_img = enhance_image_for_ocr_2(pil_img, scale)
    results = get_text_results(proc_img)
    if results:
      all_results.append(results)

  # Pick the result array with the highest total confidence
  if all_results:
    best_result_array = max(all_results, key=lambda arr: sum(r[2] for r in arr))
    final_text = " ".join(r[1] for r in reading_order(best_result_array))

    # Normalize spaces and strip extra whitespace
    final_text = " ".join(final_text.split())
    return final_text

  return ""
