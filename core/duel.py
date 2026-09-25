"""The URA Finale duel with Happy Meek: reading the board and picking a contest.

Training a facility that carries the `Duel!` badge starts a duel, which offers
three contests. Option 1 is always the trained facility's own stat; the other
two are drawn from the five stats plus Energy. Winning one pays a stat, a +4
stat cap, 30 skill points and - the reason any of this exists - a hint level for
the matching `Racing Spirit` skill. Losing pays a fraction of the stat and
nothing else, so **the odds are the whole decision**.

The game states those odds in a `Predictions` column: a glyph per row, at a
fixed x, reading (best to worst) a ringed dot, a hollow ring, a triangle and a
cross.

**Why this reads the left-hand option rows and not the Choices panel.** The
panel looks like the better source - it names the skill outright
(`Racing Spirit: Speed hint lvl +1`) rather than making us map a stat word. It
is not usable:

- `find_choice_headers` counts the trainee's stat strip at the top of the panel
  as an option, so the panel comes back with one entry more than there are
  options;
- the panel **scrolls**, and a three-option duel routinely shows only two of
  them (`tests/fixtures/duel/choice_4_dtc.png`). `docs/screen-map.md` already
  warns that the panel need not agree with the rows.

The option rows have neither problem: every option is on screen, and the label
and its glyph share a row, so they cannot drift out of step with each other.
"""
import os

import cv2
import numpy as np
from PIL import ImageGrab

import utils.constants as constants
from core.ocr import extract_text
from utils.log import debug, warning
from utils.screenshot import enhance_for_reading

# Match on the stat **word**, never on the sentence. master.mdb carries two
# banks of these (text_data category 267): "Contest of energy!" in one and
# "Let's see who has more energy!" in the other, sharing no phrasing. Note the
# game writes "wits" where every key in this repo is "wit".
CONTEST_WORDS = {
  "speed": "spd",
  "stamina": "sta",
  "power": "pwr",
  "guts": "guts",
  "wits": "wit",
  "energy": "energy",
}

# Best to worst. A win is a win whichever contest it was, so these only ever
# order the options against each other.
GLYPHS = ("d", "c", "t", "x")
GLYPH_RANK = {"d": 3, "c": 2, "t": 1, "x": 0}
GLYPH_NAMES = {"d": "@", "c": "O", "t": "/\\", "x": "X"}
# A win still needs to be likely. A triangle is the game saying "small chance",
# and a cross "very small" - neither buys a hint often enough to spend the one
# duel this facility offers.
GOOD_GLYPHS = ("d", "c")

PREDICTION_TEMPLATES = {g: f"assets/duel/pred_{g}.png" for g in GLYPHS}
# Every glyph is the same size and sits on a plain row, so this is a
# classification between four templates rather than a detection: what matters is
# the gap to the runner-up, measured at 0.241 at worst over the captured frames.
PREDICTION_CONFIDENCE = 0.55

_missing_assets = set()
_bank = None


def _load_bank():
  """{glyph: template}, loaded once. Empty when the assets are not cut."""
  global _bank
  if _bank is not None:
    return _bank
  _bank = {}
  for glyph, path in PREDICTION_TEMPLATES.items():
    if not os.path.exists(path):
      if path not in _missing_assets:
        _missing_assets.add(path)
        warning(f"{path} is not cut yet, so the duel Predictions cannot be read.")
      continue
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is not None:
      _bank[glyph] = template
  return _bank


def read_glyphs(img=None):
  """[(y, glyph)] for each option row carrying a Predictions glyph, top first.

  Rows are found from the glyphs themselves rather than from a fixed table, so
  an option count other than three needs no change here.
  """
  bank = _load_bank()
  if not bank:
    return []
  if img is None:
    img = ImageGrab.grab()
  try:
    bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    left, top, right, bottom = constants.DUEL_PREDICTION_BBOX
    roi = bgr[top:bottom, left:right]
    hits = []
    for glyph, template in bank.items():
      result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
      h, w = template.shape[:2]
      ys, xs = np.where(result >= PREDICTION_CONFIDENCE)
      for x, y in zip(xs, ys):
        hits.append((result[y][x], top + y + h // 2, glyph))
  except Exception as e:
    debug(f"read_glyphs: could not read the Predictions column ({e}).")
    return []
  # One row, one glyph: keep the best-scoring template per cluster of y.
  rows = []
  for score, cy, glyph in sorted(hits, reverse=True):
    if any(abs(cy - y) < 30 for y, _ in rows):
      continue
    rows.append((cy, glyph))
  return sorted(rows)


def read_label(img, y):
  """The contest category on the row centred at `y`, or None."""
  left, right = constants.DUEL_LABEL_X
  half = constants.DUEL_LABEL_HALF_HEIGHT
  text = (extract_text(enhance_for_reading(img.crop((left, y - half, right, y + half))))
          or "").lower()
  for word, key in CONTEST_WORDS.items():
    if word in text:
      return key
  return None


def read_board(img=None):
  """The duel as [{"y", "glyph", "category"}], top option first.

  Empty when this is not a duel screen: nothing else in the game puts that
  column of glyphs beside rows naming a contest.
  """
  if img is None:
    img = ImageGrab.grab()
  rows = []
  for y, glyph in read_glyphs(img):
    rows.append({"y": y, "glyph": glyph, "category": read_label(img, y)})
  return rows


def is_duel(rows):
  """Whether this really is Happy Meek's Challenge.

  Two rows naming a contest is the bar. One could be a stray read on some other
  scenario screen; two in the same column, each beside a Predictions glyph, is
  not something another screen produces.
  """
  return sum(1 for row in rows if row.get("category")) >= 2


def pick(rows, targets):
  """The 1-based option to take, or 0 for "no opinion".

  `targets` is the wanted contests in preference order, from config.

  The rules, in order:

  1. The first wanted contest whose odds are good takes it.
  2. Never a cross. A certain loss trades the hint for nothing, where a likely
     win on an unwanted stat still levels Happy Meek toward the stronger final
     race - so an unwanted contest at good odds beats a wanted one at a cross.
  3. Otherwise the best odds on the board.
  4. With no glyphs read at all, fall back to the wanted contest by label, then
     to the top option, and say so.
  """
  if not rows:
    return 0
  rated = [r for r in rows if r.get("glyph")]
  if not rated:
    for want in targets:
      for i, row in enumerate(rows, 1):
        if row.get("category") == want:
          debug(f"No Predictions read; taking {want} on its label alone.")
          return i
    return 0
  for want in targets:
    for i, row in enumerate(rows, 1):
      if row.get("category") == want and row.get("glyph") in GOOD_GLYPHS:
        return i
  best = max(range(len(rated)), key=lambda i: GLYPH_RANK.get(rated[i]["glyph"], -1))
  if GLYPH_RANK.get(rated[best]["glyph"], -1) <= 0:
    # Every option is a cross. Nothing to protect, so leave it to the caller's
    # own default rather than pretending this was a choice.
    return 0
  return rows.index(rated[best]) + 1


def describe(rows):
  """A one-line summary for the log."""
  return ", ".join(f"{(r.get('category') or '?').upper()}={GLYPH_NAMES.get(r.get('glyph'), '?')}"
                   for r in rows)
