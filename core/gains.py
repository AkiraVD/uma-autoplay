"""Read the stat gains the training screen prints above each stat column.

The screen shows, per stat, up to two numbers: a bubble (white, or tinted when a
Unity bonus applies) and an orange number below it. The total the training
actually awards is **bubble + orange**; a facility with no bonus shows only the
orange number. That was confirmed against the game itself - a Power training
showing Stamina +17/+5 and Power +37/+16 moved Stamina by 22 and Power by 53
once the concurrent event bonuses were accounted for.

easyocr is not usable here: it reads the leading "+" as a digit ("+37" -> "437")
and drops narrow ones ("+16" -> "6"). The UI font is fixed, so digits are matched
against a small template bank in assets/digits/ instead, which reads 16/16 known
columns where OCR managed 2.
"""
import glob
import os

import cv2
import numpy as np
from PIL import Image, ImageGrab

import utils.constants as constants
from utils.log import debug, warning

# Canvas that glyphs are padded into. Never stretch: a narrow "1" stretched to
# a square looks like a "7".
BOX = (26, 30)
MIN_GLYPH_SCORE = 0.60
# The "+" sign is about as wide as it is tall (~1.05); the widest digit is 0.82.
MAX_DIGIT_ASPECT = 0.90
GLYPH_HEIGHT = (19, 28)
GLYPH_MIN_AREA = 45
GLYPH_MAX_WIDTH = 30
# Real digits sit within ~20px of their column centre; anything further is
# the neighbouring column or the stat header row bleeding into the window.
MAX_CENTRE_DISTANCE = 45

_bank = None


def _canon(pil):
  arr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
  h, w = arr.shape[:2]
  scale = min(BOX[1] / h, BOX[0] / w)
  arr = cv2.resize(arr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
  out = np.full((BOX[1], BOX[0], 3), 255, np.uint8)
  y = (BOX[1] - arr.shape[0]) // 2
  x = (BOX[0] - arr.shape[1]) // 2
  out[y:y + arr.shape[0], x:x + arr.shape[1]] = arr
  return out


def _load_bank():
  global _bank
  if _bank is None:
    _bank = []
    for path in glob.glob(os.path.join("assets", "digits", "*.png")):
      name = os.path.basename(path)
      if name and name[0].isdigit():
        _bank.append((name[0], _canon(Image.open(path))))
    if not _bank:
      warning("assets/digits is empty, so stat gains cannot be read.")
  return _bank


def _glyph_rows(img, cx):
  """Digit-shaped blobs in one stat column, grouped into rows, left to right."""
  x0 = cx - constants.GAIN_COLUMN_HALF
  y0, y1 = constants.GAIN_STRIP_Y
  crop = np.array(img.crop((x0, y0, cx + constants.GAIN_COLUMN_HALF, y1)).convert("RGB"))
  hsv = cv2.cvtColor(cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
  hue = hsv[:, :, 0].astype(int) * 2
  mask = (((hue <= 45) | (hue >= 340)) & (hsv[:, :, 1] > 110) & (hsv[:, :, 2] > 110)).astype(np.uint8)
  n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

  comps = []
  for i in range(1, n):
    w = stats[i, cv2.CC_STAT_WIDTH]
    h = stats[i, cv2.CC_STAT_HEIGHT]
    if stats[i, cv2.CC_STAT_AREA] < GLYPH_MIN_AREA:
      continue
    if not (GLYPH_HEIGHT[0] <= h <= GLYPH_HEIGHT[1]) or w > GLYPH_MAX_WIDTH:
      continue
    if w / h >= MAX_DIGIT_ASPECT:
      continue  # the "+" sign
    left = stats[i, cv2.CC_STAT_LEFT]
    if abs((x0 + left + w / 2) - cx) > MAX_CENTRE_DISTANCE:
      continue  # a neighbouring column's digit, or the stat header below
    comps.append((stats[i, cv2.CC_STAT_TOP], left, w, h))

  rows = []
  for c in sorted(comps):
    for row in rows:
      if abs(row[0][0] - c[0]) <= 12:
        row.append(c)
        break
    else:
      rows.append([c])
  return [[(x0 + l, y0 + t, w, h) for t, l, w, h in sorted(r, key=lambda c: c[1])] for r in rows]


def _read_row(img, row):
  bank = _load_bank()
  if not bank:
    return None
  text = ""
  for gx, gy, gw, gh in row:
    glyph = _canon(img.crop((gx, gy, gx + gw, gy + gh)))
    best, score = None, -1.0
    for ch, tpl in bank:
      s = float(cv2.matchTemplate(glyph, tpl, cv2.TM_CCOEFF_NORMED).max())
      if s > score:
        best, score = ch, s
    if score >= MIN_GLYPH_SCORE:
      text += best
  return int(text) if text.isdigit() else None


def check_stat_gains(img=None):
  """Total stat gain per column for the training currently on screen.

  Returns {"spd": n, ..., "skill": n} with only the columns that show a number.
  An empty dict means nothing was readable, and callers must fall back rather
  than treat it as "this training gives nothing".
  """
  if img is None:
    img = ImageGrab.grab()
  gains = {}
  for key, cx in constants.GAIN_COLUMN_X.items():
    values = [v for v in (_read_row(img, r) for r in _glyph_rows(img, cx)) if v is not None]
    if values:
      gains[key] = sum(values)
  if gains:
    debug(f"Stat gains on screen: {gains}")
  return gains
