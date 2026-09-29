"""Pick a race off the Race List by what its row says, not by its picture.

`race_select` used to find a race by `assets/races/<name>.png`, a cut of the
row's banner art. That bank has 30 files, so 30 of the 402 schedulable races
could ever be clicked; every OP and Pre-OP race was unreachable, which is why
the Race Plan tab marks them "agenda only" and expects them typed into the
game's own agenda by hand.

Every row already prints what identifies it. Measured against master.mdb over
all 59 turn-slots of a career, **track + surface + metres + fans gained is
unique for every race but one pair**:

    Junior Late Nov - Akamatsu Sho and Begonia Sho
    both Pre-OP, both Tokyo Turf 1600m Left, both +1,000 fans

The date costs nothing: the list only shows the current turn's races, so the
turn is already the filter. Nothing else on the row is read. The direction
("Left", "Right / Outer", the two straight courses) and the grade badge each
separate *nothing* that the fans number has not separated already - checked
both ways round - so reading them would buy a second parser and a second way
to be wrong for no races gained. `tests/test_race_row.py` re-runs that
uniqueness proof against the installed master.mdb, so a patch that introduces
a second clashing pair fails a test rather than a career.

Two rules follow from that one pair, and both matter more than they look:

- the whole list is read before anything is clicked, across every scroll
  position. Clicking the first row that matches would mean a duplicate below
  the fold is never seen, and the ambiguity guard silently stops working;
- when two rows match, nothing is clicked. Skipping a race costs a turn;
  entering the wrong one costs the race.
"""
import json
import os
import re
import sqlite3

import cv2
import numpy as np
from PIL import Image
from rapidfuzz import fuzz, process

from utils.log import debug, info, warning
import core.masterdb as masterdb
import core.recognizer as recognizer
import utils.constants as constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RACES_JSON = os.path.join(ROOT, "data", "races.json")

# text_data categories, as core/masterdb.py names them.
RACE_NAMES = 28
TRACK_NAMES = 35

# Grades the career race list can offer. Maiden (800) and Debut (900) are left
# out for the same reason server/master_data.py leaves them out of the picker:
# they are not races anything schedules.
GRADES = {100: "G1", 200: "G2", 300: "G3", 400: "OP", 700: "Pre-OP"}

# A name has to be recognised off an OCR'd line, so the match is fuzzy. 80 is
# what core/events.py uses for the same job on longer strings; the track line
# is short, and every alternative is a different word, so it can be stricter.
NAME_MATCH = 88
TRACK_MATCH = 80

# The row anchor matched 1.000 on the row it was cut from and 0.975-0.984 on
# five other rows across four frames, with nothing else on the screen above
# 0.80. 0.90 sits in that gap.
ANCHOR_MATCH = 0.90
# Drags before giving up on reaching the bottom. Two rows a drag, and the
# busiest turn in the game offers 12 races, so six is enough and ten is slack.
SCAN_STEPS = 10

_keys = None


def _ocr():
  """core.ocr, imported on use.

  Importing it builds the easyocr Reader, which takes seconds and is pure waste
  for the half of this module that only reads master.mdb - including its test.
  """
  import core.ocr as ocr
  return ocr


def _fallback_keys():
  """{race name: key} from data/races.json - the 43 G1s.

  Only reached when master.mdb cannot be read. The key is exactly as unique
  here as it is with master.mdb: the one colliding pair is Pre-OP, so it is
  not in this file at all.
  """
  try:
    with open(RACES_JSON, encoding="utf-8") as f:
      races = json.load(f)
  except (OSError, ValueError) as e:
    warning(f"RACE-ROW-R01: no race list to match rows against ({e}).")
    return {}

  keys = {}
  for year in races.values():
    for name, detail in year.items():
      meters = detail.get("distance", {}).get("meters")
      fans = detail.get("fans", {}).get("gained")
      if not meters or not fans:
        continue
      keys.setdefault(name, {
        "track": detail.get("racetrack", ""),
        "surface": detail.get("terrain", ""),
        "meters": meters,
        "fans": fans,
      })
  return keys


def _mdb_keys():
  """{race name: key} for every schedulable race, from master.mdb.

  `single_mode_program` is the career's race calendar; the course lives two
  joins away, because a program names a race *instance* rather than a race.
  Scenario and character variants repeat a race under the same name and the
  same course, so the first one is enough - `setdefault` keeps it.
  """
  path = masterdb.local_copy()
  if not path:
    return {}

  try:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
      names = dict(con.execute(
        'select "index", text from text_data where category = ?', (RACE_NAMES,)))
      tracks = dict(con.execute(
        'select "index", text from text_data where category = ?', (TRACK_NAMES,)))
      fans = dict(con.execute(
        'select fan_set_id, fan_count from single_mode_fan_count where "order" = 1'))
      rows = con.execute("""
        select p.race_instance_id, r.grade, p.fan_set_id,
               c.race_track_id, c.distance, c.ground
        from single_mode_program p
        join race_instance ri on ri.id = p.race_instance_id
        join race r on r.id = ri.race_id
        join race_course_set c on c.id = r.course_set
      """).fetchall()
  except sqlite3.Error as e:
    warning(f"RACE-ROW-R02: couldn't read races from master.mdb ({e}).")
    return {}

  keys = {}
  for instance_id, grade, fan_set, track_id, meters, ground in rows:
    name = names.get(instance_id)
    if not name or grade not in GRADES:
      continue
    keys.setdefault(name, {
      "track": tracks.get(track_id, ""),
      "surface": "Dirt" if ground == 2 else "Turf",
      "meters": meters,
      "fans": fans.get(fan_set, 0),
    })
  return keys


def race_keys():
  """{race name: key}, master.mdb first, data/races.json when it is missing."""
  global _keys
  if _keys is None:
    _keys = _mdb_keys()
    if _keys:
      debug(f"Race rows: {len(_keys)} races keyed from master.mdb.")
    else:
      _keys = _fallback_keys()
      info(f"Race rows: master.mdb unreadable, keyed {len(_keys)} races from"
           " data/races.json.")
  return _keys


def _plain(name):
  """A name with its punctuation dropped, for comparing spellings.

  The config spells races the way `assets/races/*.png` does - `Tokyo Yushun
  Japanese Derby` - and master.mdb writes `Tokyo Yushun (Japanese Derby)`.
  Fuzzy matching alone does not close that: `token_set_ratio` scores the pair
  **75**, because `(Japanese` and `Japanese` are different tokens, so the
  right race loses to a cutoff that has to stay high. Stripping first makes it
  an exact match and leaves the fuzz for OCR's kind of miss.
  """
  return re.sub(r"[^a-z0-9]+", " ", name.lower().replace("’", "'")).strip()


def key_for(name):
  """The row key for a configured race name, or None."""
  keys = race_keys()
  if not keys:
    return None
  if name in keys:
    return keys[name]

  plain = {_plain(k): k for k in keys}
  if _plain(name) in plain:
    return keys[plain[_plain(name)]]

  hit = process.extractOne(_plain(name), plain.keys(), scorer=fuzz.ratio,
                           score_cutoff=NAME_MATCH)
  if hit:
    hit = (plain[hit[0]], hit[1])
  if not hit:
    warning(f"RACE-ROW-W01: '{name}' matches no race in the game's data, so its"
            " row cannot be recognised. Check the spelling in the config.")
    return None
  if hit[0] != name:
    debug(f"Race '{name}' read as '{hit[0]}' ({hit[1]:.0f}).")
  return keys[hit[0]]


def track_names():
  return sorted({k["track"] for k in race_keys().values() if k["track"]})


# Everything after the metres - "(Mile) Left / Outer" - is deliberately not
# captured. See the module docstring: it identifies nothing.
#
# The metres are matched as letters-or-digits and repaired afterwards, because
# easyocr reads the trailing zero of a round distance as a capital O: the live
# frames came back `Niigata Turf 160Om` and `Sapporo Turf 150Om`. Repairing is
# safe here in a way it would not be in free text - the field can only be a
# number - and it is cheaper than the digit-template bank core/gains.py needed,
# because a wrong repair cannot select the wrong race, only fail to match.
DIGIT_LOOKALIKE = str.maketrans({
  "O": "0", "o": "0", "D": "0", "Q": "0",
  "I": "1", "l": "1", "i": "1", "|": "1",
  "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2", "G": "6",
})
TRACK_LINE = re.compile(
  r"^(?P<track>.+?)\s+(?P<surface>turf|dirt)\s*(?P<meters>[0-9OoDQIlis|SBZzG]{3,4})\s*m\b",
  re.IGNORECASE)
FANS = re.compile(r"([\d,OoDQIlis|SBZzG]+)fans", re.IGNORECASE)


def _digits(text):
  """A number read off the screen, with easyocr's letter-for-digit slips
  undone. None when nothing is left to read."""
  cleaned = text.translate(DIGIT_LOOKALIKE).replace(",", "")
  return int(cleaned) if cleaned.isdigit() else None


def parse_track_line(text):
  """'Niigata Turf 1600m (Mile) Left / Outer' -> {track, surface, meters}, or
  None when the line is not a track line at all.

  The track name is fuzzy-matched against the game's own list, because this
  comes off OCR: 'Niiqata' and 'Tokvo' are the usual shapes of a miss, and
  every alternative is a different word, so a near miss is safe to resolve.
  """
  if not text:
    return None
  line = re.sub(r"\s+", " ", text).strip()
  found = TRACK_LINE.match(line)
  if not found:
    return None

  names = track_names()
  raw = found.group("track").strip()
  track = raw
  if names:
    hit = process.extractOne(raw, names, scorer=fuzz.ratio,
                             score_cutoff=TRACK_MATCH)
    if not hit:
      debug(f"Track line '{line}': '{raw}' is no racetrack.")
      return None
    track = hit[0]

  meters = _digits(found.group("meters"))
  if not meters:
    return None
  return {
    "track": track,
    "surface": found.group("surface").capitalize(),
    "meters": meters,
  }


def parse_fans(text):
  """'+3,100 fans' -> 3100, or None. The comma is the game's, not OCR's."""
  if not text:
    return None
  found = FANS.search(text.replace(" ", ""))
  return _digits(found.group(1)) if found else None


def row_matches(row, key):
  """Does one read row identify this race?

  Every field is compared exactly. There is no tolerance to spend: the metres
  and the fans are the two numbers that do the separating, and a reader that
  accepted a near miss on either would enter a different race rather than fail.
  """
  if not row or not key:
    return False
  return (row.get("track") == key["track"]
          and row.get("surface") == key["surface"]
          and row.get("meters") == key["meters"]
          and row.get("fans") == key["fans"])


def find_row(rows, key, name=""):
  """The one row matching this race, or None when none or several do.

  `rows` is the whole list, every scroll position included - see the module
  docstring for why the caller must not hand over one screen at a time.
  """
  hits = [row for row in rows if row_matches(row, key)]
  if not hits:
    return None
  if len(hits) > 1:
    warning(f"RACE-ROW-W02: {len(hits)} rows on the race list read the same as"
            f" {name or 'this race'} ({key['track']} {key['surface']}"
            f" {key['meters']}m, +{key['fans']} fans). Not entering one at"
            " random - skipping the race.")
    return None
  return hits[0]


# ---------------------------------------------------------------- the screen

def _strip(screen, anchor, offsets):
  """One anchor-relative strip of a row, upscaled for OCR.

  x3 is not decoration: at native size the live frames read `I60Om` where x3
  read `160Om`, and the leading digit matters more than the trailing one -
  a repaired `160Om` is right, a dropped digit is not.
  """
  x, y = anchor
  left, top, right, bottom = offsets
  crop = screen.crop((x + left, y + top, x + right, y + bottom))
  return crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)


def row_anchors(screen):
  """Every fully visible row's anchor on this frame, top to bottom.

  A row scrolled half out of the viewport has no whole anchor to match, so it
  is not returned - it will be read whole at another scroll position, which is
  why the scan walks to the end of the list rather than stopping early.
  """
  boxes = recognizer.multi_match_templates(
    {"row": constants.RACE_ROW_ANCHOR}, screen=screen, threshold=ANCHOR_MATCH)["row"]
  left, top, right, bottom = constants.RACE_ROW_LIST_BBOX
  inside = [b for b in boxes
            if left <= b[0] and b[0] + b[2] <= right
            and top <= b[1] and b[1] + b[3] <= bottom]
  # min_dist has to clear the icon itself; rows are a pitch apart.
  anchors = recognizer.deduplicate_boxes(inside, min_dist=constants.RACE_ROW_PITCH // 2)
  return sorted((b[0], b[1]) for b in anchors)


def read_rows(screen):
  """Read every whole row on one frame: {track, surface, meters, fans, anchor}.

  A row that will not read is dropped rather than half-filled, so it can never
  match a race by accident.
  """
  rows = []
  for anchor in row_anchors(screen):
    read = _ocr().extract_text
    line = parse_track_line(read(
      _strip(screen, anchor, constants.RACE_ROW_TRACK_FROM_ANCHOR_BBOX)))
    fans = parse_fans(read(
      _strip(screen, anchor, constants.RACE_ROW_FANS_FROM_ANCHOR_BBOX)))
    if not line or not fans:
      debug(f"Race row at {anchor} did not read ({line}, {fans}).")
      continue
    rows.append({**line, "fans": fans, "anchor": anchor})
  return rows

def _overlap(seen, fresh):
  """How many of `fresh`'s leading rows are the tail of `seen`.

  One drag is meant to move the list two whole rows, so normally nothing
  overlaps. The last drag of a list is the exception: it stops where the
  content ends, having moved one row or none, and then the top of the new
  screen is a row already read. Comparing what the rows *say* needs no pixel
  arithmetic and survives the list coming to rest a pixel or two off.
  """
  for size in range(min(len(seen), len(fresh)), 0, -1):
    if all(row_matches(a, b) for a, b in zip(seen[-size:], fresh[:size])):
      return size
  return 0


def scan_list(screen_grab, scroll, stopped=None):
  """Every row of the race list, in order, scrolling to the bottom.

  `screen_grab()` returns the current frame and `scroll()` drags the list down
  one step; both are passed in so this can be tested without a game. `stopped()`
  says whether the bot has been told to stop.

  The whole list is read before the caller picks anything - see the module
  docstring. That costs an OCR pair per row, which is why nothing else on the
  row is read.
  """
  rows = []
  for step in range(SCAN_STEPS):
    if stopped and stopped():
      return rows
    fresh = read_rows(screen_grab())
    if not fresh:
      break
    new = fresh[_overlap(rows, fresh):]
    if not new:
      # The list did not move, so this is the bottom.
      return rows
    rows += [{**row, "step": step} for row in new]
    scroll()
  else:
    warning(f"RACE-ROW-W03: the race list was still moving after {SCAN_STEPS}"
            f" drags ({len(rows)} rows read). Reading no further.")
  return rows


def row_on_screen(screen, key, name=""):
  """The one row on *this* frame matching a race, or None.

  A scan ends at the bottom of the list, so the row it chose is no longer where
  it was seen. The caller scrolls back to it and calls this: what gets clicked
  is a row read on the frame it is clicked from, never a remembered position.
  """
  return find_row(read_rows(screen), key, name)


def click_point(row):
  """Where to tap to select a row: the middle of its banner picture."""
  dx, dy = constants.RACE_ROW_CLICK_FROM_ANCHOR
  return (int(row["anchor"][0]) + dx, int(row["anchor"][1]) + dy)
