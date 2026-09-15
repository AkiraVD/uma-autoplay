"""Grand Concert Lessons: spend Performance points on Techniques and Songs.

Training in Grand Concert earns five kinds of Performance points (Da, Pa, Vo,
Vi, Co). The Lessons button in the lobby spends them, and costs no turn. The
screen always shows three cards:

- a Technique is a small immediate gain (a stat, skill points, energy, a hint);
- a Song gives an immediate bonus plus one that applies from the next concert
  on, and every Song learned before a concert fills its Hype gauge. Three Songs
  before a concert is a Great Success (+10 to every stat, and the stat caps go
  up); fewer is +3.

Buying any card replaces all three ("Your trainee won't be able to learn the
other 2 options"), and nothing else ever changes the board. New Songs only
appear after a set number of Techniques, so Techniques are the way to the Songs
and are bought whenever nothing better is on offer.

Whether a card can be bought is read off the card, never worked out from the
point totals: a buyable card has a gold "Learnable!" ribbon and a bright cost
row, a locked one has no ribbon and a dimmed cost row. Measured on six cards:
~800 gold pixels against 0, and a cost row mean of 226 against 136. Both have
to agree before anything is bought.

A locked Song can be Scheduled, which reserves it: the game marks the points
still missing on the lobby's Performance panel and says when it can be learned.
"""
import colorsys
import json
import os
import re

import cv2
import numpy as np
import pyautogui
import utils.control as control
from PIL import ImageGrab
from rapidfuzz import fuzz, process

import core.state as state
import utils.constants as constants
from core.ocr import extract_text, extract_number, read_boxes
from utils.log import debug, info, warning, log_dir
from utils.screenshot import enhance_for_reading
from utils.tools import sleep

LESSONS_BTN = "assets/grand_concert/lessons_btn.png"
LESSONS_READY = "assets/grand_concert/lessons_ready.png"
CONCERT_INFO_BTN = "assets/grand_concert/concert_info_btn.png"
SONGS_LEARNED_BTN = "assets/grand_concert/songs_learned_btn.png"
BACK_BTN = "assets/buttons/back_btn.png"

READY_CONFIDENCE = 0.8
# Separation measured on the captured screens: 1.000 on the Lessons screen,
# at most 0.675 under the dialogs and overlays that cover it.
SCREEN_CONFIDENCE = 0.84

# A buyable card, by the two signals that have to agree.
RIBBON_MIN_GOLD = 200
COST_ROW_MIN_BRIGHTNESS = 190
# The "Scheduled" pill is solid red over the bottom of the song's art, and some
# art is red too: Run n' Run!'s cover put 591 red pixels in the box, against
# 1717 for the pill. The pill is also nearly free of white (207 against ~1000
# for bare art), which is the second guard.
SCHEDULED_MIN_RED = 1200
SCHEDULED_MAX_WHITE = 600

# A card's header colour names its kind, and nothing else on the card does it
# as reliably: the kind tag is small white text on the same colour. Judged by
# hue, not by the exact colour: the career-end board is drawn dimmed, and its
# Technique green came out (91, 136, 46) against the usual (143, 218, 71).
TECHNIQUE_HUE = (60, 130)   # green, 92 degrees measured
SONG_HUE = (240, 290)       # purple, 263 degrees measured

STAT_WORDS = {"speed": "spd", "stamina": "sta", "power": "pwr", "guts": "guts", "wit": "wit"}

# A lesson visit buys at most this many cards. Every purchase re-reads the
# board, so this only bounds a run of misreads, never a real shopping trip -
# a full trip before a concert is three or four cards.
MAX_PURCHASES_PER_VISIT = 8
SONG_NAME_MATCH = 80
# An Energy technique at high energy scores amount * 0.05 (1.5 for +30); any
# other effect scores several points. Below this it waits a turn (see choose).
WASTED_TECHNIQUE_FLOOR = 3.0
# The turn value a visit from the concert screen passes, where every song
# learned still counts towards the concert about to start.
CONCERT_TURN = "concert"
# Within this of a type's cap, points are spent rather than held.
OVERFLOW_MARGIN = 40
# Buying cheapest-first, a better-ranked song this many points dearer still wins.
SONG_COST_SLACK = 6
# Songs behind the straight-line pace before buying cheapest-first. The pace
# starts climbing on a segment's first turn, but its first song page is two
# techniques away: at 0.5, career 4 was "behind" (4 of 4.67) in Classic Late Jan
# and dropped the reserved Full Speed Ahead!, 7 Da short, for a rank-11 song.
PACE_TOLERANCE = 1.0
# The points totals: grey digits darker than this on a light ground. A "1" is
# ~7x20 px, a "4" ~16x20.
POINTS_INK_BELOW = 180
POINTS_MIN_GLYPH_HEIGHT = 12
POINTS_ONE_MAX_ASPECT = 0.5

# Songs bought per concert segment, keyed by segment index (see segment_of).
# The game shows no running total, so this count is the only one there is, and
# it decides both the 18-song gold skill and each concert's Hype. It is written
# to disk on every purchase: a restart mid-career would otherwise zero it, and
# the next visit then bought the worst song on the board.
_songs = {}
# Highest concert segment seen, to notice a new career starting.
_latest_segment = -1
# (year, turn) of a lobby turn where a visit bought nothing, so the "!" badge
# on a board of Songs being saved for does not reopen Lessons every poll.
_declined = None
# (card name, (year, turn)) of an Energy technique being made to wait a turn.
_energy_wait = None
# Types the board is waiting on when every card on it is a locked technique.
_blocked = set()

# Songs learned this career, by their name in the song table, so the reserve is
# worked out from the songs still to come.
_learned = []
# Where this segment's technique pattern stands: song pages bought so far, and
# techniques bought since the last one. The pattern resets at every concert.
_pattern = {"pages": 0, "steps": 0, "purchases": 0}

PROGRESS_FILE = os.path.join(log_dir, "grand_concert_progress.json")

def _save_progress():
  try:
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
      json.dump({"songs": {str(k): v for k, v in _songs.items()}, "latest_segment": _latest_segment,
                 "learned": _learned, "pattern": _pattern, "blocked": sorted(_blocked)}, f)
  except OSError as e:
    warning(f"Couldn't save the Grand Concert song count ({e}); it will not survive a restart.")

def _load_progress():
  global _latest_segment
  try:
    with open(PROGRESS_FILE, encoding="utf-8") as f:
      saved = json.load(f)
  except (OSError, ValueError):
    return
  _songs.clear()
  _songs.update({int(k): int(v) for k, v in (saved.get("songs") or {}).items()})
  _latest_segment = int(saved.get("latest_segment", -1))
  _learned[:] = saved.get("learned") or []
  _pattern.update(saved.get("pattern") or {})
  # A locked board opens no visit to re-read it, so a restart must remember it.
  _blocked.clear()
  _blocked.update(k for k in saved.get("blocked") or () if k in POINT_KEYS)

def _reset_pattern():
  _pattern.update({"pages": 0, "steps": 0, "purchases": 0})

def reset():
  """Forget the career: called when one completes."""
  global _latest_segment
  _songs.clear()
  _learned.clear()
  _blocked.clear()
  _reset_pattern()
  _latest_segment = -1
  _save_progress()
  resume()

def resume():
  """Forget this sitting only; called whenever the bot is started.

  The song counts survive an F1 pause. They are what keeps one concert's
  points from being drained into the one before it, and a restart mid-career
  used to zero them - the next visit then bought the worst song on the board.
  """
  global _declined, _concert_shopped, _energy_wait
  _declined = None
  _concert_shopped = None
  _energy_wait = None

def _note_year(year):
  """Clear the song counts when the calendar goes backwards: a new career."""
  global _latest_segment
  if not re.search(r"Junior|Classic|Senior|Finale", year or ""):
    return
  segment = segment_of(year)
  if segment < _latest_segment:
    info("The calendar went backwards, so this is a new career; song counts cleared.")
    _songs.clear()
    _learned.clear()
  if segment != _latest_segment:
    # A concert has passed (or a career started): the technique pattern resets.
    _reset_pattern()
    _latest_segment = segment
    _save_progress()

# Techniques needed before each song page, per segment; the list repeats.
# Before the 1st concert, then the 2nd-4th, then the Grand Concert (uma.guide,
# GameTora, LiveRoute agree).
PATTERNS = {0: [1, 2, 3, 4, 4, 2, 3], 1: [2, 2, 2, 4, 5, 2, 2], 2: [2, 2, 2, 4, 5, 2, 2],
            3: [2, 2, 2, 4, 5, 2, 2], 4: [2, 2, 2, 4, 3, 2, 2]}

def techs_to_next_page(year):
  """Techniques still to buy before the next song page, by the tracked pattern."""
  pattern = PATTERNS[segment_of(year)]
  return max(0, pattern[_pattern["pages"] % len(pattern)] - _pattern["steps"])

def _record_purchase(card, year):
  """Advance the tracked pattern and the learned list for one purchase.

  A song bought as the segment's first purchase is a page carried over the
  concert, and counts as the new pattern's first step rather than as a page -
  so the next song comes one technique sooner (LiveRoute, parukt).
  """
  if card["kind"] == "song":
    info_ = song_info(card["name"])
    if info_ and info_["name"] not in _learned:
      _learned.append(info_["name"])
    if _pattern["purchases"] == 0:
      _pattern["steps"] = 1
    else:
      _pattern["pages"] += 1
      _pattern["steps"] = 0
  else:
    _pattern["steps"] += 1
  _pattern["purchases"] += 1
  _save_progress()

def total_songs(year):
  """Songs learned so far. "Make Debut!" is given free after the debut race and
  counts towards the 18; "Girls' Legend U" arrives too late to count."""
  return sum(_songs.values()) + (0 if "Pre-Debut" in (year or "") else 1)

def song_target(segment):
  """Songs learned in total (Make Debut included) the plan wants by the end of
  this segment: 4 / 8 / 12 / 16 / 18 by default. 16 by Senior Late Jun opens the
  "Closer Together" event; 18 before Senior Early Dec is the gold skill."""
  plan = state.SONG_PLAN or [4, 8, 12, 16, 18]
  return plan[min(segment, len(plan) - 1)]

def segment_progress(year):
  """How far through its concert segment this turn is, 0..1.

  Each segment is a half year of 12 turns (Early/Late per month); the Junior
  one only really starts after the debut, so Pre-Debut is 0.
  """
  text = year or ""
  if "Pre-Debut" in text:
    return 0.0
  if "Finale" in text:
    return 1.0
  found = re.search(r"\b(Early|Late)\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text)
  if not found:
    return 0.5
  index = constants.DATE_ARRAY.index(f"{found.group(1)} {found.group(2)}")
  return ((index % 12) + 1) / 12

def songs_expected(year):
  """Where the plan says the total should be by now: the last segment's target
  plus this segment's share, pro rata."""
  segment = segment_of(year)
  if segment == 0 and "Pre-Debut" in (year or ""):
    # Make Debut is only credited once it is run; before it nothing is behind.
    return 0.0
  start = song_target(segment - 1) if segment > 0 else 1
  progress = segment_progress(year)
  if segment == 4:
    # The 18-song check is taken at the end of the Senior Early Dec command, and
    # a song bought that turn is too late (career 2). Aim to be done by Late Oct.
    progress = min(1.0, progress * 12 / 8)
  return start + (song_target(segment) - start) * progress

def hype_songs_needed(segment):
  """Songs to buy this segment for a Great Success: three per concert, and the
  first concert counts Make Debut, the Grand Concert Girls' Legend U."""
  return 2 if segment in (0, 4) else 3

def segment_of(year):
  """Which concert the current turn is building towards, 0..4.

  Concerts close each half year: Junior Late Dec, Classic Late Jun, Classic
  Late Dec, Senior Late Jun, Senior Late Dec. A purchase made on a concert's own
  turn still counts towards that concert, which is what this gives.
  """
  # Searched for rather than split on: the year read sometimes picks up a stray
  # character from the box beside it ("0 Junior Year Pre-Debut" on race day).
  text = year or ""
  first_half = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun)\b", text) is not None
  if re.search(r"Classic", text):
    return 1 if first_half else 2
  if re.search(r"Senior", text):
    return 3 if first_half else 4
  if re.search(r"Finale", text):
    return 4
  return 0

def _game_bbox():
  left, top, width, height = constants.GAME_SCREEN_REGION
  return (left, top, left + width, top + height)

def lessons_available(screen):
  """True when the lobby has a Lessons button, i.e. this is Grand Concert."""
  return bool(_match_in(screen, LESSONS_BTN, _game_bbox(), 0.8))

def ready(screen):
  """Where to tap Lessons when its button carries the "!" for a learnable card,
  else None. Found by its label, since summer camp moves it: three careers
  never visited Lessons in July or August because the badge was looked for
  where the button sits the rest of the year."""
  label = _match_in(screen, LESSONS_BTN, constants.LESSONS_LABEL_SEARCH_BBOX, 0.8)
  if not label:
    return None
  x, y = label[0] + label[2] // 2, label[1] + label[3] // 2
  dx0, dy0, dx1, dy1 = constants.LESSONS_BADGE_FROM_LABEL
  if not _match_in(screen, LESSONS_READY, (x + dx0, y + dy0, x + dx1, y + dy1), READY_CONFIDENCE):
    return None
  tap_x, tap_y = constants.LESSONS_TAP_FROM_LABEL
  return (x + tap_x, y + tap_y)

def should_visit(year, turn):
  return _declined != (year, turn)

def _match_in(screen, template, bbox, confidence):
  """Best template hit inside bbox as (x, y, w, h), or None below confidence."""
  left, top, right, bottom = bbox
  tpl = cv2.imread(template, cv2.IMREAD_COLOR)
  if tpl is None:
    warning(f"{template} is missing.")
    return None
  crop = cv2.cvtColor(np.asarray(screen.crop((left, top, right, bottom)).convert("RGB")), cv2.COLOR_RGB2BGR)
  if crop.shape[0] < tpl.shape[0] or crop.shape[1] < tpl.shape[1]:
    return None
  result = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)
  _, best, _, loc = cv2.minMaxLoc(result)
  if best < confidence:
    return None
  h, w = tpl.shape[:2]
  return (left + loc[0], top + loc[1], w, h)

def on_lessons_screen(screen=None):
  """The Lessons board, told apart by its bottom-right button: "Concert Info"
  while concerts remain, "Songs Learned" once the Grand Concert is over. Only
  checking the first is how the career-end visit decided Lessons had not
  opened and left the points unspent."""
  if screen is None:
    screen = ImageGrab.grab()
  return bool(_match_in(screen, CONCERT_INFO_BTN, _game_bbox(), SCREEN_CONFIDENCE)
              or _match_in(screen, SONGS_LEARNED_BTN, _game_bbox(), SCREEN_CONFIDENCE))

def _card_bbox(box, i):
  dy = constants.LESSON_CARD_PITCH * i
  return (box[0], box[1] + dy, box[2], box[3] + dy)

def _card_region(region, i):
  dy = constants.LESSON_CARD_PITCH * i
  return (region[0], region[1] + dy, region[2], region[3])

def _read_text(screen, region):
  left, top, width, height = region
  return extract_text(enhance_for_reading(screen.crop((left, top, left + width, top + height)))).strip()

def header_kind(rgb):
  """"technique", "song" or None from a card header's mean colour."""
  r, g, b = (float(v) / 255 for v in rgb)
  h, s, v = colorsys.rgb_to_hsv(r, g, b)
  if s < 0.25 or v < 0.2:
    return None
  hue = h * 360
  if TECHNIQUE_HUE[0] <= hue <= TECHNIQUE_HUE[1]:
    return "technique"
  if SONG_HUE[0] <= hue <= SONG_HUE[1]:
    return "song"
  return None

def read_card(screen, i):
  """One card as {slot, kind, name, effects, learnable, scheduled}."""
  rgb = np.asarray(screen.convert("RGB")).astype(int)
  hsv = np.asarray(screen.convert("HSV")).astype(int)

  def sub(arr, box):
    left, top, right, bottom = _card_bbox(box, i)
    return arr[top:bottom, left:right]

  ribbon = sub(hsv, constants.LESSON_RIBBON_BBOX)
  gold = int(((ribbon[..., 0] > 25) & (ribbon[..., 0] < 45)
              & (ribbon[..., 1] > 120) & (ribbon[..., 2] > 180)).sum())
  cost_row = float(sub(rgb, constants.LESSON_COST_ROW_BBOX).mean())
  header = sub(rgb, constants.LESSON_HEADER_BBOX).reshape(-1, 3).mean(0)
  pill = sub(rgb, constants.LESSON_SCHEDULED_BBOX)
  red = int(((pill[..., 0] > 200) & (pill[..., 1] < 110) & (pill[..., 2] < 150)).sum())
  white = int(((pill[..., 0] > 235) & (pill[..., 1] > 235) & (pill[..., 2] > 235)).sum())

  kind = header_kind(header)

  ribbon_says = gold >= RIBBON_MIN_GOLD
  row_says = cost_row >= COST_ROW_MIN_BRIGHTNESS
  if ribbon_says != row_says:
    # Mid-animation, most likely. Refusing costs one poll; a wrong yes would
    # open a Schedule dialog where a Learn was expected.
    debug(f"Lesson card {i + 1}: ribbon ({gold}) and cost row ({cost_row:.0f}) disagree,"
          " treating it as locked.")

  name = _read_text(screen, _card_region(constants.LESSON_TITLE_REGION, i))
  effects = [_read_text(screen, _card_region(constants.LESSON_EFFECT_1_REGION, i)),
             _read_text(screen, _card_region(constants.LESSON_EFFECT_2_REGION, i))]
  return {
    "slot": i,
    "kind": kind,
    "name": name,
    "effects": [e for e in effects if e and e.lower() != "none"],
    "learnable": ribbon_says and row_says,
    "scheduled": kind == "song" and red >= SCHEDULED_MIN_RED and white <= SCHEDULED_MAX_WHITE,
  }

def read_points(screen):
  """The five point totals across the top of the Lessons screen, or None."""
  boxes = [getattr(constants, f"LESSON_POINTS_{k.upper()}_BBOX") for k in POINT_KEYS]
  values = [extract_number(enhance_for_reading(screen.crop(b)), value_range=(0, 999)) for b in boxes]
  values = [v if v >= 0 else _read_ones(screen.crop(b)) for v, b in zip(values, boxes)]
  if any(v < 0 for v in values):
    debug(f"Performance points would not read cleanly: {values}")
    return None
  return dict(zip(POINT_KEYS, values))

def _read_ones(crop):
  """A points total easyocr gives up on: a lone "1" (career 3: Vo 17 -> 1 after
  a Vocal technique, and every read failed until it grew). The digits are grey
  on a light ground; a number made only of narrow glyphs is all ones. -1 if not."""
  ink = np.asarray(crop.convert("L")) < POINTS_INK_BELOW
  columns = ink.any(axis=0)
  glyphs = []
  x = 0
  while x < len(columns):
    if not columns[x]:
      x += 1
      continue
    start = x
    while x < len(columns) and columns[x]:
      x += 1
    rows = np.flatnonzero(ink[:, start:x].any(axis=1))
    glyphs.append((x - start, rows[-1] - rows[0] + 1))
  if not glyphs or any(h < POINTS_MIN_GLYPH_HEIGHT or w / h > POINTS_ONE_MAX_ASPECT for w, h in glyphs):
    return -1
  return int("1" * len(glyphs))

def read_cost(screen, i):
  """One card's cost per type, read off its cost row; None if nothing reads."""
  left, top, width, height = _card_region(constants.LESSON_COST_TEXT_REGION, i)
  row = enhance_for_reading(screen.crop((left, top, left + width, top + height)))
  cost = {k: 0 for k in POINT_KEYS}
  found = False
  for text, conf, (x, y, w, h) in read_boxes(row):
    digits = re.sub(r"[^\d]", "", text)
    if not digits or len(digits) > 2:
      continue
    # enhance_for_reading doubles the image; slots are in screen pixels.
    offset = x / 2
    slot = sum(1 for edge in constants.LESSON_COST_SLOT_EDGES if offset >= edge)
    cost[POINT_KEYS[slot]] = int(digits)
    found = True
  return cost if found else None

def read_board(screen=None):
  if screen is None:
    screen = ImageGrab.grab()
  cards = [read_card(screen, i) for i in range(3)]
  for card in cards:
    if card["kind"] == "technique" or not song_info(card["name"]):
      card["cost"] = read_cost(screen, card["slot"])
  return cards

def board_settled(cards):
  """A board caught mid-refresh reads as garbage: seen live straight after a
  purchase, "I I n no n" / "2" / "" with no kinds and no effects - and the "2"
  card was then taken for a song to schedule."""
  return all(c["kind"] and len(c["name"]) >= 4 and c["effects"] for c in cards)

def read_settled_board(attempts=4):
  """(cards, points) from one settled frame; points may be None."""
  for _ in range(attempts):
    screen = ImageGrab.grab()
    cards = read_board(screen)
    if board_settled(cards):
      return cards, read_points(screen)
    sleep(0.8)
  return cards, None

def describe(card):
  flags = ("learnable" if card["learnable"] else "locked") + (", scheduled" if card["scheduled"] else "")
  cost = card_cost(card)
  price = " " + "/".join(str(cost[k]) for k in POINT_KEYS) if cost else ""
  return f"{card['kind'] or '?'} {card['name']!r} [{'; '.join(card['effects']) or 'no effects read'}] ({flags}){price}"

def parse_effects(lines):
  """{effect: amount} from a card's effect lines.

  "Training Wit Gain +1" is a Song's permanent training bonus and is kept apart
  from "Wit +5", which is paid once.
  """
  found = {}
  for line in lines:
    text = line.lower().replace(" ", "")
    amount = re.search(r"\+(\d+)", text)
    value = int(amount.group(1)) if amount else 0
    trained = re.search(r"training(speed|stamina|power|guts|wit)gain", text)
    stat = re.search(r"(speed|stamina|power|guts|wit)", text)
    if trained:
      found[f"train_{STAT_WORDS[trained.group(1)]}"] = value
    elif "skillpt" in text and "training" in text:
      found["train_skill_pts"] = value
    elif "friendship" in text:
      found["friendship"] = value
    elif "specialty" in text or "speciality" in text:
      found["specialty"] = value
    elif "chain" in text or "supportevent" in text:
      found["chain"] = value
    elif "hint" in text:
      found["hint"] = value
    elif "skillpt" in text:
      found["skill_pts"] = value
    elif "energy" in text:
      found["energy"] = value
    elif stat:
      found[STAT_WORDS[stat.group(1)]] = value
  return found

def song_rank(name):
  """Position of a Song in the configured priority list; unlisted ones last."""
  priority = state.SONG_PRIORITY or []
  if not name or not priority:
    return len(priority)
  best = process.extractOne(name, priority, scorer=fuzz.ratio)
  if best and best[1] >= SONG_NAME_MATCH:
    return best[2]
  return len(priority)

POINT_KEYS = ("da", "pa", "vo", "vi", "co")
SONGS_FILE = os.path.join("data", "grand_concert_songs.json")
_song_table = None

def song_table():
  """The 21 learnable songs: name, segment it unlocks in, cost per point type."""
  global _song_table
  if _song_table is None:
    try:
      with open(SONGS_FILE, encoding="utf-8") as f:
        _song_table = [s for s in json.load(f)["songs"] if sum(s["cost"].values()) > 0]
    except (OSError, ValueError, KeyError) as e:
      warning(f"{SONGS_FILE} would not load ({e}); songs are chosen by rank alone.")
      _song_table = []
  return _song_table

def song_info(name):
  """The song table's entry for an OCR'd card title, or None."""
  table = song_table()
  if not name or not table:
    return None
  best = process.extractOne(name, [s["name"] for s in table], scorer=fuzz.ratio)
  if best and best[1] >= SONG_NAME_MATCH:
    return table[best[2]]
  return None

def cost_total(cost):
  return sum(cost.values()) if cost else 0

def card_cost(card):
  """A card's cost per type: the song table's for a known song, else as read."""
  if card["kind"] == "song":
    info_ = song_info(card["name"])
    if info_:
      return info_["cost"]
  return card.get("cost")

def point_cap(segment):
  """Each type is capped at 200, +50 after every concert (400 by the finale)."""
  return 200 + 50 * segment

def reserve(year):
  """Points per type to keep back for the songs still to come.

  The cheapest remaining songs, as many as this segment still needs (at most
  two - further ones are not unlockable before income arrives anyway), plus,
  once this segment is done, the next segment's first. Career 2 lost the gold
  skill to exactly this: Senior songs are Da/Vi heavy, Speed techniques spent
  the Da, and the 18th song was 17 Da short with a turn to go.
  """
  segment = segment_of(year)
  need = max(0, song_target(segment) - total_songs(year))
  pool = sorted((s for s in song_table() if s["segment"] <= segment and s["name"] not in _learned),
                key=lambda s: cost_total(s["cost"]))
  chosen = pool[:min(need, 2)]
  if need == 0 and segment < 4:
    later = sorted((s for s in song_table() if s["segment"] <= segment + 1
                    and s["name"] not in _learned and s not in chosen),
                   key=lambda s: cost_total(s["cost"]))
    chosen += later[:1]
  return {k: sum(s["cost"][k] for s in chosen) for k in POINT_KEYS}

def extra_deficit(cost, points, held):
  """How much further below the reserve buying at this cost would put us."""
  worse = 0
  for k in POINT_KEYS:
    after = points[k] - cost.get(k, 0)
    worse += max(0, held[k] - after) - max(0, held[k] - points[k])
  return worse

def shortfall(cost, points):
  """Points still missing to afford a cost; the worst single type."""
  return max(max(0, cost.get(k, 0) - points[k]) for k in POINT_KEYS)

def stat_weight(stat):
  """The user's training weight for a stat, floored so no stat is worth nothing."""
  try:
    return max(0.1, float(state.PRIORITY_EFFECTS_LIST[state.PRIORITY_STAT.index(stat)]))
  except (ValueError, KeyError, TypeError, AttributeError):
    return 0.5

def technique_value(card, energy):
  """Rough worth of a Technique, in stat points."""
  value = 0.0
  for effect, amount in parse_effects(card["effects"]).items():
    if effect in ("spd", "sta", "pwr", "guts", "wit"):
      value += amount * stat_weight(effect)
    elif effect == "skill_pts":
      value += amount * 0.9
    elif effect == "energy":
      # Energy is only worth something when it would otherwise be a rest.
      low = energy is not None and 0 <= energy < state.ENERGY_TECHNIQUE_BELOW
      value += amount * (1.5 if low else 0.05)
    elif effect == "hint":
      value += 2.0 * max(1, amount)
  return value

def choose(cards, energy, year, spend_all=False, turn=None, points=None):
  """What to do with this board: ("learn" | "schedule" | "none", card, why).

  spend_all is for the Grand Concert, after which points cannot be spent.
  turn identifies the lobby turn (CONCERT_TURN on the concert screen), for the
  carry-over and for waiting a turn on an Energy technique. points is the five
  totals read off the screen, or None, in which case nothing type-aware runs.

  The rules, from the second research pass (LiveRoute, uma-sim, GameTora,
  kamigame) and two live careers:
  - Songs follow the running plan (SONG_PLAN, 4/8/12/16/18 in total). Once a
    segment's target is met, points are HELD - no songs and no filler
    techniques - except to stop a type overflowing its cap, for energy when it
    is low, and for the carry-over on the concert screen.
  - Short of the target, techniques are the way to the next song page, and
    the one bought is the one that eats least into the reserve kept for the
    songs still to come (see reserve).
  - Behind pace, or in Senior H2 where a song only counts towards the 18, the
    cheapest learnable song is bought; on pace, the best-ranked. Within
    SONG_COST_SLACK of the cheapest, rank still decides.
  - With all 18 in Senior H2 there is nothing left to hold for: techniques are
    bought by value, so their stats arrive before the Japan Cup and Arima.
  - On the concert screen, with the Hype gauge secured, a song page is left on
    the board to carry over the concert (it then counts as the next pattern's
    first step), unless it is a Friendship song worth having now; a page one or
    two techniques away is bought into first.
  """
  global _energy_wait
  segment = segment_of(year)
  songs = sorted((c for c in cards if c["kind"] == "song"), key=lambda c: song_rank(c["name"]))
  techniques = [c for c in cards if c["kind"] == "technique"]
  learnable_songs = [c for c in songs if c["learnable"]]
  learnable_techs = [c for c in techniques if c["learnable"]]

  if spend_all:
    if learnable_songs:
      return "learn", learnable_songs[0], "spending everything: songs first"
    if learnable_techs:
      best = max(learnable_techs, key=lambda c: technique_value(c, energy))
      return "learn", best, f"spending everything: technique worth ~{technique_value(best, energy):.1f}"
    return "none", None, "nothing learnable"

  total = total_songs(year)
  need = max(0, song_target(segment) - total)
  on_concert = turn == CONCERT_TURN
  short_of_hype = on_concert and _songs.get(segment, 0) < hype_songs_needed(segment)
  patient = total >= songs_expected(year) - PACE_TOLERANCE
  cheapest_first = not patient or segment == 4

  # Carry-over, on the concert screen once the gauge is full.
  if on_concert and not short_of_hype and segment < 4:
    if songs:
      friendly = [c for c in learnable_songs
                  if "Friendship" in ((song_info(c["name"]) or {}).get("concert_bonus") or "")]
      if friendly and need > 0:
        return "learn", friendly[0], "Friendship song, worth having from this concert on"
      return "none", None, "leaving the song page to carry over the concert"
    to_page = techs_to_next_page(year)
    if learnable_techs and 0 < to_page <= 2:
      cheapest = min(learnable_techs, key=lambda c: cost_total(card_cost(c)) or 99)
      return "learn", cheapest, f"{to_page} technique(s) from a song page to carry over the concert"
    return "none", None, "holding the points over the concert"

  if songs:
    if need == 0 and not short_of_hype:
      return "none", None, (f"{total} songs learned, on plan for this concert ({song_target(segment)});"
                            " saving the points for the next one")
    if learnable_songs:
      if cheapest_first:
        # Cheapest, give or take a few points: career 3 bought Ring Ring Diary
        # (42, ranked 19) over the scheduled Run n' Run! (44, ranked 5).
        cheapest = min(cost_total(card_cost(c)) or 99 for c in learnable_songs)
        best = next(c for c in learnable_songs if (cost_total(card_cost(c)) or 99) <= cheapest + SONG_COST_SLACK)
        return "learn", best, (f"cheapest learnable song ({total} learned, pace {songs_expected(year):.1f}"
                               f"{', Senior H2 counts only' if segment == 4 else ''})")
      best = learnable_songs[0]
      top = songs[0]
      # A Song buried under a purchase comes back later, but not soon. Only the
      # very best are worth leaving the board alone for.
      if (top is not best and not top["learnable"]
          and song_rank(top["name"]) < state.HOLD_FOR_TOP_SONGS
          and song_rank(top["name"]) < song_rank(best["name"])):
        if not top["scheduled"]:
          return "schedule", top, f"holding for {top['name']!r}"
        return "none", None, f"holding for {top['name']!r}, already scheduled"
      # On pace, a scheduled better song is waited for rather than dropped.
      reserved = next((c for c in songs if c["scheduled"] and not c["learnable"]), None)
      if reserved and not on_concert and song_rank(reserved["name"]) < song_rank(best["name"]):
        return "none", None, f"waiting for the scheduled {reserved['name']!r} rather than {best['name']!r}"
      return "learn", best, f"song ranked {song_rank(best['name']) + 1}"
    if any(c["scheduled"] for c in songs):
      return "none", None, "nothing learnable; waiting for the scheduled song"
    # Reserve the song closest to affordable, unless one of the very best is on
    # the board and there is time to wait for it.
    pick = songs[0]
    if not (patient and segment < 4 and song_rank(pick["name"]) < state.HOLD_FOR_TOP_SONGS) and points:
      priced = [c for c in songs if card_cost(c)]
      if priced:
        # Closest, give or take a few points, then by rank (songs is rank-sorted).
        # Career 3 reserved Getaway! Fallin' Love (6 short, ranked 21) over Go
        # This Way (11 short, ranked 12). In Senior H2 there is no give: a
        # song's bonuses never take effect, only the count towards 18 does, and
        # career 4 reserved rank 3 at 17 points short over rank 20 at 12.
        slack = 0 if segment == 4 else SONG_COST_SLACK
        closest = min(shortfall(card_cost(c), points) for c in priced)
        pick = next(c for c in priced if shortfall(card_cost(c), points) <= closest + slack)
    return "schedule", pick, "nothing learnable; reserving the song closest to affordable"

  if not learnable_techs:
    return "none", None, "nothing learnable"

  energy_low = energy is not None and 0 <= energy < state.ENERGY_TECHNIQUE_BELOW
  # All 18 in Senior H2: nothing is left to save for, and the Grand Concert
  # would spend it on these same techniques - after the Japan Cup and Arima
  # rather than before. Career 3 reached 18 in Senior Early Sep.
  songs_done = segment == 4 and need == 0 and not short_of_hype
  # A concert still short of its songs keeps buying towards the next page.
  if need == 0 and not short_of_hype and not songs_done:
    # On plan: hold, bar overflow and energy.
    if points:
      cap = point_cap(segment)
      full = [k for k in POINT_KEYS if points[k] >= cap - OVERFLOW_MARGIN]
      spill = [c for c in learnable_techs if card_cost(c) and any(card_cost(c).get(k, 0) for k in full)]
      if spill:
        best = max(spill, key=lambda c: technique_value(c, energy))
        return "learn", best, f"{', '.join(full)} near the {cap} cap; spending before it overflows"
    if energy_low:
      topped = [c for c in learnable_techs if "energy" in parse_effects(c["effects"])]
      if topped:
        return "learn", max(topped, key=lambda c: technique_value(c, energy)), "on plan, but energy is low"
    return "none", None, f"{total} songs, on plan ({song_target(segment)}); holding points for the next songs"

  # Short of the target: buy towards the next song page, keeping the reserve.
  note = ""
  if songs_done:
    best = max(learnable_techs, key=lambda c: technique_value(c, energy))
    note = f", {total} songs done, spending ahead of the Grand Concert"
  elif points and all(card_cost(c) for c in learnable_techs):
    held = reserve(year)
    best = min(learnable_techs, key=lambda c: (extra_deficit(card_cost(c), points, held),
                                                -technique_value(c, energy)))
    dent = extra_deficit(card_cost(best), points, held)
    note = f", {dent} into the song reserve" if dent else ", song reserve kept"
  else:
    best = max(learnable_techs, key=lambda c: technique_value(c, energy))
  # An Energy technique costs 20-35 points, and with energy already high the
  # energy is simply lost. Seen live: Energy +30 bought at high energy while
  # a Wit +8 and a Skill Pts +8 sat locked on the same board, a turn or two
  # of points away. So it waits one turn: by then those may be affordable, or
  # energy may have dropped. If it is still the best card next turn it is
  # bought, so the board keeps moving towards the next song.
  wasted = technique_value(best, energy) < WASTED_TECHNIQUE_FLOOR and "energy" in parse_effects(best["effects"])
  if wasted:
    key = (year, turn)
    if _energy_wait is None or _energy_wait[0] != best["name"]:
      _energy_wait = (best["name"], key)
      return "none", None, f"{best['name']!r} is only energy and energy is high; waiting a turn"
    if _energy_wait[1] == key:
      return "none", None, f"{best['name']!r} is only energy; still waiting for next turn"
  _energy_wait = None
  return "learn", best, f"technique worth ~{technique_value(best, energy):.1f}{note}"

def _tap(pos, text=""):
  if state.stop_event.is_set() or not state.is_bot_running:
    return False
  if text:
    debug(text)
  control.moveTo(pos[0], pos[1], duration=0.2)
  control.click()
  return True

def _dialog_title():
  return _read_text(ImageGrab.grab(), constants.LESSON_DIALOG_TITLE_REGION).lower()

def _back_to_board(attempts=8):
  """Tap through whatever followed a purchase until the board is showing again.

  "TECHNIQUE LEARNED!" (and a Song's equivalent) wants a tap. A Schedule dialog
  can open behind it when that tap lands on a card, so any dialog still up is
  cancelled rather than accepted.
  """
  for _ in range(attempts):
    if state.stop_event.is_set():
      return False
    sleep(0.8)
    screen = ImageGrab.grab()
    if on_lessons_screen(screen):
      return True
    # The second "Confirm" sits over the first dialog, whose title still reads
    # behind it, so it is checked first. It only follows a Learn or Schedule
    # that has already been decided on.
    if "confirm" in _read_text(screen, constants.LESSON_CONFIRM_TITLE_REGION).lower():
      _tap(constants.LESSON_CONFIRM_OK_MOUSE_POS, "Dropping the scheduled song for this one.")
      continue
    if "scheduling" in _read_text(screen, constants.LESSON_SCHEDULING_TITLE_REGION).lower():
      _tap(constants.LESSON_SCHEDULING_CLOSE_MOUSE_POS, "Closing Scheduling Complete.")
      continue
    title = _read_text(screen, constants.LESSON_DIALOG_TITLE_REGION).lower()
    if "schedule" in title or "confirm" in title:
      _tap(constants.LESSON_DIALOG_CANCEL_MOUSE_POS, f"Cancelling an unexpected {title!r} dialog.")
    else:
      _tap(constants.LESSON_DISMISS_MOUSE_POS)
  return on_lessons_screen()

def _open_card(card, expected):
  """Open a card's dialog and check it is the one expected.

  Learn and Schedule sit on the same spot, so pressing it without reading the
  title first could reserve a card that was meant to be bought, or the reverse.
  """
  x, y = constants.LESSON_CARD_MOUSE_POS
  _tap((x, y + constants.LESSON_CARD_PITCH * card["slot"]), f"Opening lesson {card['name']!r}.")
  sleep(1.0)
  title = _dialog_title()
  if expected not in title:
    warning(f"Expected a {expected!r} dialog for {card['name']!r}, got {title!r}; cancelling.")
    _tap(constants.LESSON_DIALOG_CANCEL_MOUSE_POS)
    _back_to_board()
    return False
  return True

def learn(card):
  # The purchase dialog is titled "Confirmation".
  if not _open_card(card, "confirm"):
    return False
  _tap(constants.LESSON_DIALOG_ACCEPT_MOUSE_POS, f"Learning {card['name']!r}.")
  sleep(1.2)
  # Buying one song over a scheduled one drops the reservation, and the game
  # asks first. choose() has already decided this card is the better buy.
  if "confirm" in _read_text(ImageGrab.grab(), constants.LESSON_CONFIRM_TITLE_REGION).lower():
    _tap(constants.LESSON_CONFIRM_OK_MOUSE_POS, "Dropping the scheduled song for this one.")
    sleep(1.2)
  return _back_to_board()

def schedule(card):
  if not _open_card(card, "schedule"):
    return False
  _tap(constants.LESSON_DIALOG_ACCEPT_MOUSE_POS, f"Scheduling {card['name']!r}.")
  sleep(1.5)
  return _back_to_board()

def _leave():
  """Back out of Lessons to wherever it was opened from.

  That is the lobby on a normal turn and the concert screen on a concert turn,
  which has no Tazuna hint, so leaving is judged by the Lessons screen going
  away rather than by the lobby coming back.
  """
  for _ in range(4):
    if state.stop_event.is_set():
      return False
    if not on_lessons_screen():
      return True
    pos = pyautogui.locateCenterOnScreen(BACK_BTN, confidence=0.8, region=constants.SCREEN_BOTTOM_REGION)
    if pos:
      _tap(pos, "Leaving Lessons.")
    sleep(1.0)
  return not on_lessons_screen()

def _wait_for_lessons():
  for _ in range(6):
    sleep(0.6)
    if on_lessons_screen():
      return True
  return False

def visit(energy=None, year="", turn=None, button=None, spend_all=False):
  """Open Lessons, buy what is worth buying, and come back.

  Returns True when anything was bought, so the caller re-reads the lobby
  (stats and energy may have moved). The turn is then done with: points only
  come from training, so reopening would find the board the visit ended on.
  Career 3 reopened it after every buy-then-wait, a wasted visit a turn. Only
  a visit cut short by the purchase cap is left open for another.
  """
  global _declined
  # Points still come in during the URA Finale and the board still sells: a
  # song's concert bonus "won't take effect", but its on-learn stats do (career
  # 3: Dream Sky, Wit +22, learnable on the Finals turn). Only the board after
  # the last race is dead, so the Finale spends everything too.
  spend_all = spend_all or "Finale" in (year or "")
  if not _tap(button or constants.LESSONS_BUTTON_MOUSE_POS, "Opening Lessons."):
    return False
  if not _wait_for_lessons():
    warning("Lessons did not open; carrying on with the turn.")
    _leave()
    _declined = (year, turn)
    return False
  bought = shop(energy, year, spend_all, turn)
  _leave()
  if bought < purchase_limit(spend_all):
    _declined = (year, turn)
  return bought > 0

def purchase_limit(spend_all=False):
  return MAX_PURCHASES_PER_VISIT * (3 if spend_all else 1)

def blocked_types():
  """What a fully locked technique board needs, for training to favour.

  With nothing learnable the Lessons button carries no "!", so the board sits
  frozen - career 4 spent Classic Early Oct to Late Dec on three locked
  techniques (Vi 0 of 25, Co 10 of 15) with no song page coming. The red
  "N more" badges that steer training only exist for a scheduled song, so this
  is the same nudge for a technique board. Set by the visit that finds the
  board locked, cleared by the next one that finds anything learnable.
  """
  return sorted(_blocked)

def pushing_for_gold(year):
  """True while Senior H2 is still short of the 18 songs the gold skill wants.

  The check is taken at the end of the Senior Early December command, so from
  Senior July on, a turn that pays a type no scheduled song needs is a turn
  spent. Career 4 finished on 17 with a song page sat locked since Late Sep.
  """
  return segment_of(year) == 4 and total_songs(year) < song_target(4)

def _note_blocked(cards, points):
  was = set(_blocked)
  _blocked.clear()
  if points and cards and not any(c["learnable"] for c in cards) \
      and all(c["kind"] == "technique" for c in cards):
    priced = [card_cost(c) for c in cards if card_cost(c)]
    if priced:
      nearest = min(priced, key=lambda cost: shortfall(cost, points))
      _blocked.update(k for k in POINT_KEYS if nearest.get(k, 0) > points[k])
  if _blocked != was:
    _save_progress()
    if _blocked:
      info(f"Lessons board locked; training will favour {', '.join(sorted(_blocked))} to free it.")

def shop(energy=None, year="", spend_all=False, turn=None):
  """Buy from the board on screen until nothing is worth buying. Returns the count."""
  _note_year(year)
  bought = 0
  for _ in range(purchase_limit(spend_all)):
    if state.stop_event.is_set():
      break
    cards, points = read_settled_board()
    for card in cards:
      debug(f"Lesson card {card['slot'] + 1}: {describe(card)}")
    if not board_settled(cards):
      warning("The Lessons board would not read cleanly; leaving it for this visit.")
      break
    debug(f"Performance points {points}, reserve {reserve(year)}, "
          f"{techs_to_next_page(year)} technique(s) to the next song page.")
    _note_blocked(cards, points)
    action, card, why = choose(cards, energy, year, spend_all, turn, points)
    if action == "learn":
      info(f"Learning {card['kind']} {card['name']!r}: {why}.")
      if not learn(card):
        break
      bought += 1
      _record_purchase(card, year)
      if card["kind"] == "song":
        segment = segment_of(year)
        _songs[segment] = _songs.get(segment, 0) + 1
        _save_progress()
        info(f"Songs learned: {total_songs(year)} (plan {song_target(segment)} by this concert,"
             f" {song_target(4)} before Senior Early Dec).")
      gained = parse_effects(card["effects"]).get("energy")
      if gained and energy is not None and energy >= 0:
        energy = min(100, energy + gained)
      continue
    if action == "schedule":
      info(f"Scheduling {card['name']!r}: {why}.")
      schedule(card)
    else:
      debug(f"Lessons: {why}.")
    break
  return bought

# --- Concert turns -----------------------------------------------------------
#
# A concert is not a turn of its own. The box under the turn counter reads
# "Concert begins after this turn" on the half-year's last turn, which is
# trained as usual, and then the lobby is replaced by a concert screen: the
# header says "Concert", there is no Tazuna hint and no Back, just a big
# Lessons button and a Concert button. A "Schedule Notification" ("The song you
# scheduled can now be learned", Close / To Lessons) may sit on top of it, and
# so may appear over the ordinary lobby after any turn.
#
# Concert -> "Ready to start the concert?" (Start) -> GREAT SUCCESS (Next) ->
# the concert schedule (Next) -> a story event -> the next half-year's lobby.
# Only the first two need handling here; the rest are the generic Next and the
# dialogue taps.
#
# Songs learned right before a concert still count towards it, and the concert
# screen's Lessons button is how the Hype gauge gets topped up, so the board is
# shopped once per concert before Concert is pressed.

CONCERT_BTN = "assets/grand_concert/concert_btn.png"
SKIP_UNTICKED = "assets/grand_concert/skip_cutscene_unticked.png"
_concert_shopped = None

def cutscene_unticked(screen):
  """True when the Grand Concert's "Skip the Grand Concert cutscene" box is
  showing and not ticked.

  The grey box matches its template at 1.000, but the ticked one still scores
  0.777, so the green tick is counted as well: 146 green pixels ticked, 0
  unticked and 0 on an ordinary concert's confirmation.
  """
  if not _match_in(screen, SKIP_UNTICKED, constants.SKIP_CUTSCENE_BBOX, 0.9):
    return False
  left, top, right, bottom = constants.SKIP_CUTSCENE_BBOX
  box = np.asarray(screen.crop((left + 10, top + 10, right - 10, bottom - 10)).convert("RGB")).astype(int)
  green = int(((box[..., 1] > 150) & (box[..., 0] < 170) & (box[..., 2] < 110)).sum())
  return green < 20

def on_concert_screen(screen):
  return bool(_match_in(screen, CONCERT_BTN, _game_bbox(), 0.85))

def concert(box, year="", grand=False):
  """Handle the concert screen. box is the Concert (or Grand Concert) button.

  Performance points cannot be spent after the Grand Concert - the career-end
  Lessons board is drawn dimmed and nothing on it can be bought - so its visit
  spends everything: no per-concert cap, no saving up, no scheduling.
  """
  global _concert_shopped
  if _concert_shopped != year:
    _concert_shopped = year
    if grand:
      info("Grand Concert: the last chance to use Performance points, spending all of them.")
    else:
      info("Concert turn: one last look at Lessons for the Hype gauge.")
    visit(None, year, CONCERT_TURN, button=constants.CONCERT_LESSONS_MOUSE_POS, spend_all=grand)
    return
  x, y, w, h = box
  _tap((x + w // 2, y + h // 2), "Starting the concert.")

def to_lessons(box, energy=None, year="", turn=None):
  """A Schedule Notification's "To Lessons": the reserved song can be bought.

  The turn is remembered as visited, so the lobby that follows does not open
  the board again to reach the same decision (about 6 seconds a time).
  """
  global _declined
  x, y, w, h = box
  _tap((x + w // 2, y + h // 2), "A scheduled song can be learned now, going to Lessons.")
  if not _wait_for_lessons():
    warning("To Lessons did not open the Lessons screen.")
    return False
  bought = shop(energy, year)
  _leave()
  if turn is not None and bought < purchase_limit():
    _declined = (year, turn)
  return bought > 0

# The count lives on disk between runs; see _songs.
_load_progress()
