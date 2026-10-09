"""Reading the Veteran Roster card by card, and tagging each one with an id.

The roster holds up to 260 finished careers and the game shows almost nothing
about them in the grid - a rating and a rank badge. Everything that decides
whether a veteran is worth keeping as a parent (its stats, the skills it
learned, the sparks it hands down) is only on the Umamusume Details dialog,
one card at a time.

So the walk is: open the first card, read the dialog, press the **next arrow**
beside the aptitude block, read the next one, and so on for the whole roster.
That arrow is what makes this cheap - the grid is never scrolled, never
re-found and never tapped again after the first card.

Two things about the arrow, both measured on 2026-10-09:

- It **wraps around**. Pressing the previous arrow on the first card landed on
  the last one, so nothing on the dialog says when a lap is finished. The
  roster's own "Registered 191/260" footer is the count the walk trusts, and
  coming back round to the first card is the cross-check.
- The selected **tab persists** across a step, so the walk leaves it on Skills
  and pays for the Inspiration switch once per card rather than twice.

The card itself carries no identifier a file could be keyed on - two careers of
the same trainee with the same rating are indistinguishable - which is what the
memo is for. `write_memo` stamps each card with the id its record was saved
under, so a row in the JSON can be found again in the game. The game caps a
memo at 9 characters, which is why the ids are V001-style and not a hash.

Nothing here taps Transfer, Change or any confirmation. The only thing it can
write is the memo, and only when the caller asks for it.
"""
import re
import time

import numpy as np
from PIL import Image, ImageDraw, ImageGrab
from scipy import ndimage

from rapidfuzz import fuzz, process

import core.masterdb as masterdb
import core.menu_scan as menu_scan
import core.trainee as trainee
import core.state as state
import utils.constants as constants
import utils.control as control
from core.ocr import read_boxes
from core.recognizer import match_template
from core.skill import base_name, canonical_skill, distinct_bases
from utils.log import debug, info, warning
from utils.tools import sleep

# The scrolling panel under the tabs. Both Skills and Inspiration live in it,
# so one calibration covers both. The numbers are menu_scan's defaults except
# where the dialog differs: it is a short list in a small panel, so eight
# passes is far more than the deepest card needs, and the rewind is quick.
PANEL = menu_scan.calibration(
  name="details panel",
  anchor=None,                       # rows are found by OCR, not a template
  list_bbox="VETERAN_PANEL_BBOX",
  scroll_up_from="VETERAN_PANEL_SCROLL_UP_FROM_MOUSE_POS",
  scroll_down_from="VETERAN_PANEL_SCROLL_DOWN_FROM_MOUSE_POS",
  default_step="VETERAN_PANEL_SCROLL_DISTANCE",
  hold_after=0.5,
  travel_ratio=0.9556,               # as measured for the skill list
  rewind_settle=1.0,
  rewind_limit=8,
  passes=8,
)

STATS = ("spd", "sta", "pwr", "guts", "wit")
# Each stat's number sits under its own header, in a fifth of the stats strip.
STAT_COLUMN_WIDTH = constants.VETERAN_STATS_REGION[2] / len(STATS)
# A grade badge (S+, D, Uᴳ) sits to the left of each number, and easyocr
# reads the two as one box when they touch: Symboli Rudolf's 1005 Speed came
# back as 81005 with the badge's glyph on the front. Painting the badge out
# before the read is cheaper and steadier than five crops, and it is why the
# whole strip is still one OCR call.
# 42, not more: the numbers start 44-50px into their cell and the badges end
# by 40, so a wider mask eats the first digit - at 46 the Wit column came back
# as 13 and 15 where the card said 213 and 415.
STAT_BADGE_WIDTH = 42
# Nothing the game shows is outside this, so a number that is says the read
# went wrong rather than that the career was remarkable.
STAT_RANGE = (1, 2000)

RANK_LETTERS = "SABCDEFG"
# The rank badge is one stylised glyph over the word RANK, optionally with a
# "+". easyocr reads the letter at 0.9+ but drops the plus about half the time,
# so the plus is taken from the width of the ink instead: measured on the same
# badge, "S+" came back 242px wide against "S" at 146 on a 4x crop of the same
# box. Anything between is reported as unsure rather than guessed.
# Measured on four live badges: plain letters came in at 0.91, 1.03 and 1.07,
# and the one "+" at 1.60. The plus is worth about 0.6 of ink width, so the
# undecided band sits where nothing has landed.
RANK_PLUS_RATIO = 1.35
RANK_NO_PLUS_RATIO = 1.20

# A spark pill's background says what kind of spark it is. Sampled clear of the
# text at the pill's right end; the three coloured ones are unmistakable and
# everything else is the white pill a skill or race spark gets.
SPARK_COLOURS = {
  "blue": lambda r, g, b: b > 200 and b - r > 60,          # a stat
  "pink": lambda r, g, b: r > 200 and r - g > 60,          # an aptitude
  "green": lambda r, g, b: g > 180 and g - b > 60 and r < 210,   # the unique
}
# A filled star, by the same rule tools/veteran_scan.py reads the grid with.
STAR_GOLD = lambda a: (a[:, :, 0] > 200) & (a[:, :, 1] > 150) & (a[:, :, 2] < 120)
# Stars are a fixed 14-16px glyph. The portrait's rank badge and a unique
# spark's own icon are gold too, so the filter is on size and on being right of
# the portrait, not on colour alone.
STAR_MIN_X = 150
STAR_SIZE = (11, 20)
STAR_AREA = (55, 150)
# How green a tab is when it is the selected one. See VETERAN_TAB_*_BBOX.
TAB_GREEN = 0.5
# Panel-local x that separates the left column of pills from the right one.
PANEL_COLUMN_SPLIT = 330
# A row cut off by the top or bottom of the panel reads as a different row:
# Mayano Top Gun's "Flashy☆Landing" came back as "Tasi} Landing" on the pass
# where it was half under the header, and was then kept as a skill of its own.
# Dropping those costs nothing, because every pass overlaps the one before it
# (menu_scan's advance_one_screen) so a clipped row is read whole on another.
PANEL_EDGE = 10
# The top edge needs a deeper margin than the bottom, because a name that
# wraps onto two lines can lose its first line entirely and leave the second
# looking like a row of its own - "Behold Thine Emperor's Divine Might" came
# back as "Divine Might". A whole row is 62px, so 30 clears the case.
#
# It is only applied from the SECOND pass on. On the first the panel is at the
# top of the list, nothing is clipped there, and ANY top margin throws the real
# first row away - it starts 8px in - which no later pass would bring back.
PANEL_TOP_EDGE = 30
# Where to sample a pill's colour, as panel-local x per column.
PILL_SAMPLE_X = (320, 555)
# The band a row's name is read from, as offsets from the top of its stars.
# It reaches a little BELOW them: a name too long for its pill wraps onto a
# second line that sits level with the stars, and a band that stopped above
# them lost the second half of every long unique
# ("Behold Thine Emperor's Divine" without the "Might"). Rows are 50px apart,
# so 42 above still cannot reach the row before.
NAME_BAND = (42, -4)

# "Lvl 4" rides on the right-hand end of a unique skill's pill. It is its own
# OCR box, level with the first line of a two-line name, so it has to go before
# the lines are joined or it lands in the middle of the name.
SKILL_LEVEL = re.compile(r"^(?:lvl|lvi|ivl|iv|lv)\s*\d*$|^\d+$", re.I)
# The ○ / ◎ rank master.mdb carries on a name. See read_skills for why it is
# removed rather than kept.
RANK_GLYPH = re.compile(r"\s+[○◎×]$")

# A blue spark names one of the five stats and a pink one of the ten
# aptitudes, so those two never need a database - they are snapped to the
# closest member of their own short list.
BLUE_NAMES = ("Speed", "Stamina", "Power", "Guts", "Wit")
PINK_NAMES = ("Turf", "Dirt", "Sprint", "Mile", "Medium", "Long",
              "Front Runner", "Pace Chaser", "Late Surger", "End Closer")
# Below this a read is reported as it came off the screen rather than snapped
# to something it only half resembles, and a runner-up within the margin is
# refused outright - for the reason core/skill.py refuses one: a read that is
# nearly as much like one name as another is not evidence for either.
# "Japanese Derby" came back as "Japan Dirt Derby" until the margin was added.
SPARK_MIN_SCORE = 70
SPARK_MIN_MARGIN = 8
# A very close match is evidence on its own, and the margin rule was throwing
# those away: the race list holds "NHK Mile C." and "NHK Mile Cup", so a read
# of "NHK Mile C" scored 95.2 and 90.9 and was refused six times over. Above
# this score a small margin is enough - but not no margin, so the three
# "TS Climax Race N" entries, which are one character apart, still refuse.
SPARK_STRONG_SCORE = 92
SPARK_STRONG_MARGIN = 3
# The race-name list carries the practice and hard-mode copies of every race
# under their own names, and a Spark never names one of those.
NOT_A_RACE = ("practice:", "(hard)")
# A career's last white spark is its scenario's final, which is neither a race
# nor a skill and is in no table this reads. Without them here "URA Finale"
# fell through to the skill list and came back as "Rational" at 67.
SCENARIO_SPARKS = ("URA Finale", "Unity Cup", "Grand Concert", "Trackblazer",
                   "TS Climax Scenario")

_race_names = None
_trainee_names = None


def race_names():
  """Every race name the game knows, for telling a race spark from a skill
  spark. Both wear the same white pill, and the name is the only difference."""
  global _race_names
  if _race_names is None:
    # The SHORT names: a Spark pill prints "Japanese Derby", while the full
    # name in the other table is "Tokyo Yushun (Japanese Derby)".
    found = masterdb.text_data(masterdb.RACE_SHORT_NAMES) or []
    _race_names = [name.strip() for name in found
                   if not any(part in name.lower() for part in NOT_A_RACE)]
    debug(f"Loaded {len(_race_names)} race names for spark classification.")
  return _race_names


def trainee_names():
  """Every trainee as the game writes it, "[Variant] Name". One uma has several
  variants and they are different parents, so the variant is part of the
  name."""
  global _trainee_names
  if _trainee_names is None:
    _trainee_names = [card["name"] for card in trainee.catalog() or []]
    debug(f"Loaded {len(_trainee_names)} trainee names.")
  return _trainee_names


def closest(text, names, minimum=SPARK_MIN_SCORE):
  """The closest real name to a read, or None on a weak or a close call.

  fuzz.ratio for the reason core/skill.py uses it: WRatio's partial matching
  happily turns a short read into a long name that merely contains it.
  """
  if not text.strip() or not names:
    return None
  hits = process.extract(text, names, scorer=fuzz.ratio, limit=2)
  if not hits or hits[0][1] < minimum:
    return None
  margin = SPARK_STRONG_MARGIN if hits[0][1] >= SPARK_STRONG_SCORE else SPARK_MIN_MARGIN
  if len(hits) > 1 and hits[0][1] - hits[1][1] < margin:
    debug(f"Spark {text!r} is {hits[0][1]:.0f} like {hits[0][0]!r} but"
          f" {hits[1][1]:.0f} like {hits[1][0]!r}; leaving it as read.")
    return None
  return hits[0][0]


def name_spark(spark):
  """Snap a spark's read name to a real one, and settle what kind it is.

  A white pill is a skill spark or a race spark and nothing on screen says
  which, so the name decides: it is matched against master.mdb's races first
  and its skills second. The three coloured pills already know their kind, and
  a blue or pink name comes from a list of five or ten, which is why they do
  not touch the database at all.
  """
  read = spark["name"]
  if spark["kind"] == "blue":
    name = closest(read, BLUE_NAMES)
  elif spark["kind"] == "pink":
    name = closest(read, PINK_NAMES)
  elif spark["kind"] == "green":
    name = skill_spark(read)
  else:
    # Races first, because a race name is the one kind that is certainly not a
    # skill; then the scenario finals; then the skills. The skill list is last
    # and strictest - it is 980 names long, so something is always 60-odd
    # percent like whatever was read.
    name = closest(read, race_names())
    if name:
      spark["kind"] = "race"
    elif closest(read, SCENARIO_SPARKS):
      spark["kind"], name = "scenario", closest(read, SCENARIO_SPARKS)
    else:
      spark["kind"], name = "skill", skill_spark(read)
  spark["matched"] = name is not None
  spark["name"] = name or read
  return spark


def skill_spark(read):
  """A spark's skill name, matched at this module's bar rather than
  core/skill.py's.

  canonical_skill accepts at 60, which is right when the row is certainly a
  skill - on the purchase screen it is - but a spark pill might be a scenario
  final or a race the database spells differently, and at 60 those get a skill
  name attached to them. The candidates are its base names all the same, so a
  skill's ○ and ◎ rank still fold into one.
  """
  bases = distinct_bases()
  if not bases:
    return None
  # base_name, not the raw read: distinct_bases is keyed on lower-cased names
  # and fuzz.ratio is case-sensitive, so "Red Shift/LP12II-M" scored 56 against
  # its own lower-cased entry and was thrown away at 88.9's worth of evidence.
  base = closest(base_name(read), list(bases))
  return RANK_GLYPH.sub("", bases[base]).strip() if base else None


# --------------------------------------------------------------------------
# Pure readers. Each takes a frame and returns what it can see, so they can be
# checked against the PNGs in tests/fixtures/veteran/ without a game running.
# --------------------------------------------------------------------------

def crop(screen, region):
  left, top, width, height = region
  return screen.crop((left, top, left + width, top + height))


def on_details():
  """True when the Umamusume Details dialog is up and nothing is over it.

  The memo dialog dims the title bar enough to score 0.663 against this
  template's 1.000, so "details" and "memo on top of details" are told apart by
  the same check rather than needing a second one.
  """
  return bool(match_template(constants.VETERAN_DETAILS_TEMPLATE, threshold=0.83))


def on_memo():
  return bool(match_template(constants.VETERAN_MEMO_TEMPLATE, threshold=0.82))


def on_error():
  """The game's own "Contains invalid characters." dialog. See the note in
  utils/constants.py - it sits OVER the memo dialog, so it has to be asked
  about before anything concludes that the memo closed cleanly."""
  return bool(match_template(constants.VETERAN_ERROR_TEMPLATE, threshold=0.79))


def dismiss_error():
  """Close the error dialog if it is up. Returns whether one was there."""
  if not on_error():
    return False
  tap(constants.VETERAN_ERROR_CLOSE_MOUSE_POS, settle=1.2)
  return True


def read_rank(screen):
  """The rank badge, as "S+" / "A" / None.

  See RANK_PLUS_RATIO: the letter is OCR'd and the plus is inferred from how
  wide the ink is, because easyocr drops the glyph itself too often to rely on.
  """
  patch = crop(screen, constants.VETERAN_RANK_REGION)
  # LANCZOS, not the default: on the same badge bicubic read "S+" at 0.41 while
  # LANCZOS read "S" at 0.998, and a confident letter plus the width test below
  # beats an unconfident one that happens to carry the plus.
  patch = patch.resize((patch.width * 4, patch.height * 4), Image.LANCZOS)
  boxes = [b for b in read_boxes(patch, allowlist=RANK_LETTERS + "+") if b[0].strip()]
  if not boxes:
    return None
  # The word RANK sits under the letter and reads as a letter of its own, so
  # the badge is the tallest box, not the first.
  text, confidence, (x, y, w, h) = max(boxes, key=lambda b: b[2][3])
  letter = next((c for c in text.upper() if c in RANK_LETTERS), None)
  if not letter or confidence < 0.5:
    return None
  if "+" in text:
    return letter + "+"
  ratio = w / float(h or 1)
  if ratio >= RANK_PLUS_RATIO:
    return letter + "+"
  if ratio <= RANK_NO_PLUS_RATIO:
    return letter
  return None                        # between the two: say nothing


def read_header(screen):
  """Name, variant, rating, rank, epithet and the memo already on the card.

  The name is snapped to master.mdb's own trainee list, variant and all. The
  variants are where the OCR hurts most - they are stylised
  ("[Rising☆Fortune]", "[El Número 1]") and came back as "[Rising ~Fortune]"
  and "[El~Numero 1]" - and the variant is not decoration: two variants of one
  uma carry different uniques and different aptitudes, so they are different
  parents.
  """
  lines = [t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_NAME_REGION)) if t.strip()]
  variant = next((l for l in lines if l.startswith("[")), "")
  name = " ".join(l for l in lines if not l.startswith("[")).strip()
  full = closest(f"{variant} {name}".strip(), trainee_names(), minimum=75)
  if full:
    variant, _, name = full.partition("] ")
    variant += "]"
  epithet = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_EPITHET_REGION)))
  memo = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_MEMO_REGION)))
  memo = memo.strip()
  return {
    "name": name,
    "variant": variant.strip(),
    "rank": read_rank(screen),
    "rating": read_rating(screen),
    "epithet": epithet.strip(),
    # An unset memo is drawn as a dash, which is not a memo.
    "memo": "" if memo in ("", "-", "_", "~") else memo,
  }


def read_rating(screen):
  """The number under the portrait. It carries a comma, so the digits are
  pulled out of the text rather than read as a number."""
  text = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_RATING_REGION)))
  digits = "".join(c for c in text if c.isdigit())
  return int(digits) if digits else -1


def read_stats(screen):
  """{spd, sta, pwr, guts, wit}, each -1 when it would not read.

  The five numbers share one strip, so they are read in one OCR call and
  assigned by which fifth of the strip each box's centre lands in. Reading them
  as five crops costs five calls per card, which over a 191-card roster is the
  difference between a long run and a very long one.
  """
  strip = crop(screen, constants.VETERAN_STATS_REGION).copy()
  height = constants.VETERAN_STATS_REGION[3]
  painter = ImageDraw.Draw(strip)
  for column in range(len(STATS)):
    left = column * STAT_COLUMN_WIDTH
    painter.rectangle([left, height / 2, left + STAT_BADGE_WIDTH, height], fill="white")

  found = {}
  for text, confidence, (x, y, w, h) in read_boxes(strip):
    digits = "".join(c for c in text if c.isdigit())
    # The headers (Speed, Stamina, ...) share the strip; only the numbers in
    # the lower half are wanted.
    if not digits or y + h / 2 < height / 2 or confidence < 0.4:
      continue
    value = int(digits)
    if not STAT_RANGE[0] <= value <= STAT_RANGE[1]:
      continue
    column = int((x + w / 2) // STAT_COLUMN_WIDTH)
    if 0 <= column < len(STATS):
      found.setdefault(STATS[column], value)

  # One stat in fifteen comes back empty from the shared strip - the numbers
  # sit close enough together that a weak box gets dropped - and re-reading
  # just that cell on its own almost always gets it. Only the missing ones, so
  # a clean card still costs one OCR call.
  for column, stat in enumerate(STATS):
    if stat not in found:
      found[stat] = read_one_stat(screen, column)
  return {stat: found.get(stat, -1) for stat in STATS}


def read_one_stat(screen, column):
  """One stat's number from its own cell, as the fallback for a dropped box."""
  left, top, _, height = constants.VETERAN_STATS_REGION
  cell = (int(left + column * STAT_COLUMN_WIDTH + STAT_BADGE_WIDTH), int(top + height / 2),
          int(STAT_COLUMN_WIDTH - STAT_BADGE_WIDTH), int(height / 2))
  text = " ".join(t for t, _, _ in read_boxes(crop(screen, cell), allowlist="0123456789"))
  digits = "".join(c for c in text if c.isdigit())
  value = int(digits) if digits else -1
  return value if STAT_RANGE[0] <= value <= STAT_RANGE[1] else -1


def star_rows(panel):
  """Filled stars on the panel, as {(column, row y): count}.

  Rows are found from the stars rather than from the pills: every spark row has
  between one and three of them at a fixed size, and they are the only thing on
  the panel whose geometry does not depend on how long the name is.
  """
  image = np.asarray(panel.convert("RGB")).astype(int)
  labels, count = ndimage.label(STAR_GOLD(image))
  rows = {}
  for index, slice_ in enumerate(ndimage.find_objects(labels), 1):
    ys, xs = slice_
    w, h = xs.stop - xs.start, ys.stop - ys.start
    area = int((labels[slice_] == index).sum())
    if xs.start < STAR_MIN_X:
      continue
    if not (STAR_SIZE[0] <= w <= STAR_SIZE[1] and STAR_SIZE[0] <= h <= STAR_SIZE[1]):
      continue
    if not (STAR_AREA[0] <= area <= STAR_AREA[1]):
      continue
    column = 0 if xs.start < PANEL_COLUMN_SPLIT else 1
    key = next((k for k in rows if k[0] == column and abs(k[1] - ys.start) <= 6), None)
    rows[key or (column, int(ys.start))] = rows.get(key or (column, int(ys.start)), 0) + 1
  return {key: min(value, 3) for key, value in rows.items()}


def pill_kind(panel, column, star_y):
  """The spark's kind from the colour of its pill: blue stat, pink aptitude,
  green unique, or white for a skill or race spark."""
  image = np.asarray(panel.convert("RGB")).astype(int)
  y = max(0, star_y - 15)
  x = PILL_SAMPLE_X[column]
  if y >= image.shape[0] or x >= image.shape[1]:
    return "white"
  r, g, b = (int(v) for v in image[y, x])
  for name, test in SPARK_COLOURS.items():
    if test(r, g, b):
      return name
  return "white"


def tab_selected(bbox, screen=None):
  """Whether the tab in `bbox` is the one currently showing."""
  image = np.asarray((screen or grab()).crop(bbox).convert("RGB")).astype(int)
  green = ((image[:, :, 1] > 150) & (image[:, :, 1] - image[:, :, 2] > 80)
           & (image[:, :, 1] - image[:, :, 0] > 40))
  return float(green.mean()) > TAB_GREEN


def select_tab(point, bbox, tries=4):
  """Tap a tab and make sure it actually came up.

  Nothing downstream can tell a tab that did not switch from a card with
  nothing on it: card 78 of the first full run was recorded with zero sparks
  because the Inspiration tap was swallowed while the game was stalled, and
  the Skills panel was read as if it were the sparks panel.
  """
  for attempt in range(tries):
    if tab_selected(bbox):
      return True
    tap(point, settle=0.8 + 0.6 * attempt)
  if tab_selected(bbox):
    return True
  warning(f"The tab at {point} would not come up after {tries} taps.")
  return False


def read_sparks_frame(screen, top_edge=PANEL_EDGE):
  """The spark rows visible on one frame, and whether the ancestors' block has
  come into view.

  Returns ([{name, kind, stars}], saw_legacy). Only the Uma's own sparks are
  returned: the "Legacy Origin" header is the boundary, and everything under it
  belongs to the career's parents, which the child already records itself.
  """
  panel = crop(screen, region_of(constants.VETERAN_PANEL_BBOX))
  boxes = read_boxes(panel)
  legacy_y = next((y for t, _, (x, y, w, h) in boxes if "legacy" in t.lower()), None)

  sparks = []
  for (column, star_y), stars in sorted(star_rows(panel).items(), key=lambda kv: (kv[0][1], kv[0][0])):
    if legacy_y is not None and star_y > legacy_y:
      continue
    # A row whose name is off the top of the panel, or whose stars are off the
    # bottom, is read partly - and a partly read star row is the wrong number
    # of stars, which is worse than not reading it. See PANEL_EDGE.
    if star_y - NAME_BAND[0] < top_edge or star_y + 16 > panel.height - PANEL_EDGE:
      continue
    low, high = star_y - NAME_BAND[0], star_y - NAME_BAND[1]
    # read_boxes hands them back in reading order, so the index keeps a wrapped
    # name's two lines - and the two halves of one line - the right way round.
    parts = [(i, t) for i, (t, _, (x, y, w, h)) in enumerate(boxes)
             if (0 if x < PANEL_COLUMN_SPLIT else 1) == column and low <= y + h / 2 <= high]
    name = " ".join(t for _, t in sorted(parts)).strip()
    if not name:
      continue
    sparks.append({"name": name, "kind": pill_kind(panel, column, star_y), "stars": stars})
  return sparks, legacy_y is not None


def read_skills_frame(screen, top_edge=PANEL_EDGE):
  """The skill names visible on one frame of the Skills tab.

  A name can wrap onto two lines inside its pill, so boxes are grouped by
  column and then by how close they are vertically - the row pitch is 62px and
  a wrapped line is 17px below its first, so 30px separates the two cases
  without having to know where the rows are.
  """
  panel = crop(screen, region_of(constants.VETERAN_PANEL_BBOX))
  bottom = panel.height - PANEL_EDGE
  columns = {0: [], 1: []}
  for index, (text, _, (x, y, w, h)) in enumerate(read_boxes(panel)):
    if not text.strip() or SKILL_LEVEL.match(text.strip()):
      continue
    columns[0 if x < PANEL_COLUMN_SPLIT else 1].append((y, y + h, index, text))

  names = []
  for column in (0, 1):
    group = []
    for part in sorted(columns[column]):
      if group and (part[0] + part[1]) / 2 - (group[-1][0] + group[-1][1]) / 2 > 30:
        names.append(group)
        group = []
      group.append(part)
    if group:
      names.append(group)

  # Clipping is judged on the whole row, not on each line. Filtering the boxes
  # first is what left "Divine Might" standing on its own: the first line of
  # "Behold Thine Emperor's Divine Might" sat just above the margin and was
  # thrown away, and the second line - which was not clipped - became a skill.
  names = [group for group in names
           if group[0][0] >= top_edge and group[-1][1] <= bottom]
  # Joined in reading order, not in y order: a wrapped name's two lines differ
  # by 17px and the boxes within one line by none at all, so sorting on y alone
  # returned "Corners Long" and "Late Savvy Surger".
  return [" ".join(part[3] for part in sorted(group, key=lambda part: part[2])).strip()
          for group in names]


def region_of(bbox):
  """A (left, top, right, bottom) bbox as the (left, top, w, h) `crop` wants.
  Both conventions are in use here - see the note in utils/constants.py."""
  left, top, right, bottom = bbox
  return (left, top, right - left, bottom - top)


# --------------------------------------------------------------------------
# Driving the dialog.
# --------------------------------------------------------------------------

def grab():
  return ImageGrab.grab()


def tap(point, settle=0.6):
  control.moveTo(point[0], point[1], duration=0.15)
  control.click()
  sleep(settle)


def scan_panel(read_frame, stop_when=None, keep=None):
  """Scroll the panel top to bottom, collecting what `read_frame` reads.

  The panel is rewound first for the reason core/menu_scan.py rewinds: the
  previous card's scan left it at the bottom, and the tab keeps its scroll
  position across the next-arrow step, so a scan that did not rewind would read
  the back half of every card after the first.

  `stop_when(result)` ends the scan early - the Inspiration tab uses it to stop
  as soon as the ancestors' block is in view, since nothing below it is wanted.

  `keep`, when given a list, collects the panel crop of every pass. That is
  what the saved contact sheet is made of: a long skill list is only ever
  fully on screen across several passes, so one screenshot could not show
  what the record was read from.
  """
  menu_scan.scroll_to_top(PANEL)
  collected = []
  for pass_no in range(PANEL["passes"]):
    if state.stop_event.is_set():
      return collected
    # See PANEL_TOP_EDGE: the first pass is at the top of the list, so nothing
    # is cut off there and ANY top margin costs a real row - the first row of
    # the right-hand column starts 8px into the panel.
    screen = grab()
    if keep is not None:
      keep.append(crop(screen, region_of(constants.VETERAN_PANEL_BBOX)))
    result = read_frame(screen, 0 if pass_no == 0 else PANEL_TOP_EDGE)
    collected.append(result)
    if stop_when and stop_when(result):
      return collected
    before = menu_scan.frame(PANEL)
    menu_scan.scroll(PANEL, up=False)
    menu_scan.wait_for_list(PANEL)
    if menu_scan.still(PANEL, before, menu_scan.frame(PANEL)):
      return collected
  warning(f"Details panel still scrolling after {PANEL['passes']} passes.")
  return collected


def read_skills(keep=None):
  """Every skill on the open card, in list order, duplicates folded.

  Names are canonicalised against master.mdb and then stripped of their ○ / ◎
  rank, so what is stored is the base name and nothing is claimed about the
  rank. The rank matters for a parent - only the top of a tier group pays a
  spark - but it cannot be read: OCR renders the glyph as @, U, o or 0 about as
  often as it gets it right (core/skill.py's RANK_SUFFIX), and template
  matching the two rings against each other was tried on 2026-10-09 and
  dropped, because ○ and ◎ differ only by a 4px inner ring and scored within
  0.06 of each other on real rows - close enough that the winner flipped with
  the pixel the match landed on. Recording the rank canonical_skill happens to
  return would be inventing it.

  A name that matches no real skill is kept as it was read and reported,
  because a dropped skill looks the same as a career that never learned it.
  """
  seen, skills, unmatched = set(), [], []
  for names in scan_panel(read_skills_frame, keep=keep):
    for name in names:
      if not name.strip():
        continue
      canonical = canonical_skill(name)
      if canonical is None:
        if name.lower() not in seen:
          unmatched.append(name)
        canonical = name
      canonical = RANK_GLYPH.sub("", canonical).strip()
      if not canonical or canonical.lower() in seen:
        continue
      seen.add(canonical.lower())
      skills.append(canonical)
  return skills, unmatched


def read_sparks(keep=None):
  """The Uma's own sparks, as [{name, kind, stars}].

  A white pill is a skill spark or a race spark; master.mdb's race names say
  which, so the kind is reported as "race" or "skill" rather than "white".
  """
  seen, sparks = set(), []
  frames = scan_panel(read_sparks_frame, stop_when=lambda result: result[1], keep=keep)
  for found, _ in frames:
    for spark in found:
      named = name_spark(spark)
      key = named["name"].lower()
      if key in seen:
        continue
      seen.add(key)
      sparks.append(named)
  return sparks


def read_card(keep=None):
  """Everything on the open Details dialog, with what would not read flagged.

  The Skills tab is left selected, because the next arrow keeps the tab and
  the next card is read Skills-first.

  `keep`, when given a dict, is filled with the crops the read was made from:
  "top" (the dialog above the panel) and the per-pass panel crops under
  "skills" and "sparks". The caller turns those into the card's contact sheet.
  """
  warnings = []
  if not select_tab(constants.VETERAN_TAB_SKILLS_MOUSE_POS, constants.VETERAN_TAB_SKILLS_BBOX):
    warnings.append("the Skills tab would not open; its skills are missing")
  screen = grab()
  if keep is not None:
    keep["top"] = screen.crop(constants.VETERAN_DIALOG_TOP_BBOX)
    keep["skills"], keep["sparks"] = [], []
  card = read_header(screen)
  card["stats"] = read_stats(screen)
  card["skills"], unmatched = read_skills(keep=None if keep is None else keep["skills"])

  if select_tab(constants.VETERAN_TAB_INSPIRATION_MOUSE_POS,
                constants.VETERAN_TAB_INSPIRATION_BBOX):
    card["sparks"] = read_sparks(keep=None if keep is None else keep["sparks"])
  else:
    warnings.append("the Inspiration tab would not open; its sparks are missing")
    card["sparks"] = []
  repair_unique(card)

  if not card["name"]:
    warnings.append("name did not read")
  if card["rating"] < 0:
    warnings.append("rating did not read")
  if card["rank"] is None:
    warnings.append("rank badge unclear")
  missing = [stat for stat, value in card["stats"].items() if value < 0]
  if missing:
    warnings.append(f"stats did not read: {', '.join(missing)}")
  if unmatched:
    warnings.append(f"skills matched no real name: {'; '.join(unmatched)}")
  # Every finished career hands over exactly one blue and one pink, so either
  # of those missing means the panel was read short rather than that the career
  # did not produce one. A green is only generated for a 3-star uma, so its
  # absence is reported without being called wrong.
  if card["sparks"]:
    for kind in ("blue", "pink"):
      if not any(spark["kind"] == kind for spark in card["sparks"]):
        warnings.append(f"no {kind} spark found; the sparks panel read short")
  if card["sparks"] and not any(spark["kind"] == "green" for spark in card["sparks"]):
    warnings.append("no green spark (expected for a 1- or 2-star uma)")
  unread = [spark["name"] for spark in card["sparks"] if not spark.get("matched")]
  if unread:
    warnings.append(f"sparks matched no real name: {'; '.join(unread)}")
  card["warnings"] = warnings
  return card


def repair_unique(card):
  """Fill in a green spark that would not read from the skills list, or back.

  They are the same name twice - the green spark a career hands over IS the
  trainee's unique skill - and the two are drawn differently enough that one
  often reads when the other does not: Agnes Tachyon's "U=ma2" came off the
  Skills tab clean and off the spark pill as "U-maz", which is 60 against the
  real name and below the bar.

  The unique is always the first row of the Skills tab - it is the one pill
  with the rainbow background and a level on it - so that is the row this
  trusts. Nothing is overwritten: a name is only copied onto a read that
  failed to match anything at all.
  """
  green = next((spark for spark in card["sparks"] if spark["kind"] == "green"), None)
  first = card["skills"][0] if card["skills"] else None
  if not green or not first:
    return
  if not green.get("matched") and skill_spark(first):
    green["name"], green["matched"] = skill_spark(first), True
  elif green.get("matched") and not skill_spark(first):
    card["skills"][0] = green["name"]


def fingerprint(screen=None):
  """The bytes of the strip that identifies the open card.

  Compared as pixels rather than read, because this is asked once per step and
  an OCR pass per step over 191 cards is minutes of nothing.
  """
  patch = (screen or grab()).crop(constants.VETERAN_CARD_FINGERPRINT_BBOX).convert("L")
  return np.asarray(patch, dtype=np.uint8).tobytes()


def next_card(previous=None, tries=2, settle=8.0):
  """Step to the next card, and confirm it really stepped.

  `previous` is the fingerprint of the card that was just read. Without it
  this can only check that a dialog is on screen, which is what it did on the
  first full run - and the one time the game stalled, the check ran during the
  stall, came back False and ended the run at card 78 of 191 with the dialog
  still perfectly open behind it.

  So the wait is a poll, not a sleep, and the tap is repeated only after the
  whole wait has gone by with the card unchanged. Tapping twice could skip a
  card, but only if the two cards either side are identical over the portrait,
  the name, the rating and all five stats.
  """
  for attempt in range(tries):
    tap(constants.VETERAN_NEXT_MOUSE_POS, settle=0.8)
    deadline = time.time() + settle
    while time.time() < deadline:
      if state.stop_event.is_set():
        return False
      screen = grab()
      if on_details() and (previous is None or fingerprint(screen) != previous):
        return True
      sleep(0.5)
    debug(f"The next arrow did not change the card within {settle}s"
          f" (try {attempt + 1} of {tries}); tapping again.")
  warning("The next arrow is not advancing the roster.")
  return False


def write_memo(text):
  """Put `text` in the open card's memo. True when the game took it.

  The field keeps whatever was there, so it is selected and cleared first. The
  read-back is not a formality: a memo that silently failed would leave a row
  in the file claiming an id the card does not carry, which is exactly the
  thing the id exists to prevent.
  """
  if len(text) > constants.VETERAN_MEMO_MAX_CHARS:
    raise ValueError(f"The game caps a memo at {constants.VETERAN_MEMO_MAX_CHARS} characters;"
                     f" {text!r} is {len(text)}.")
  tap(constants.VETERAN_MEMO_PENCIL_MOUSE_POS, settle=1.0)
  if not wait_for(on_memo):
    warning("The memo dialog did not open; leaving the card as it was.")
    return False

  # **OK is disabled while the text is unchanged.** It is drawn dark olive
  # with grey lettering rather than the usual bright green, it does nothing
  # when pressed, and the dialog simply stays up - which a rescan of a roster
  # that has already been stamped would hit on every single card. There is
  # nothing to save, so back out and call it done.
  if same_memo(read_memo_field(grab()), text):
    debug(f"The memo already reads {text}; leaving it alone.")
    tap(constants.VETERAN_MEMO_CANCEL_MOUSE_POS, settle=1.0)
    return True

  # Caret past the end of whatever is there, then clear it from the right.
  control.click(*constants.VETERAN_MEMO_FIELD_END_MOUSE_POS)
  sleep(0.4)
  control.press("end")
  control.press("backspace", presses=constants.VETERAN_MEMO_MAX_CHARS + 2, interval=0.03)
  control.write(text)
  sleep(0.5)

  # Checked on LENGTH, not on the characters. The field's font is not
  # separable by OCR at this size - "V070X" read back as "VOzOX" and "V068B"
  # as "VOG8B" - so comparing the text refused writes the game had in fact
  # accepted. What a length check still catches is the failure that matters:
  # a clear that did not clear, which leaves the new id appended to the old.
  typed = read_memo_field(grab())
  if len(typed.replace(" ", "")) != len(text.replace(" ", "")):
    warning(f"The memo field reads {typed!r}, which is not {len(text)}"
            f" characters like {text!r}; cancelling.")
    tap(constants.VETERAN_MEMO_CANCEL_MOUSE_POS, settle=1.0)
    return False

  tap(constants.VETERAN_MEMO_OK_MOUSE_POS, settle=1.0)
  # The rejection is checked for before the "did it close?" test, because it
  # covers the memo title and would otherwise read as a clean close.
  if wait_for(on_error, limit=2.5, poll=0.3):
    warning(f"The game refused the memo {text!r}: contains invalid characters.")
    dismiss_error()
    if on_memo():
      tap(constants.VETERAN_MEMO_CANCEL_MOUSE_POS, settle=1.2)
    return False
  # Polled, not read once. The dialog fades out, and a single look 1.2s after
  # the press caught it mid-fade and reported every write as a failure - which
  # then cancelled a memo that had in fact gone in.
  if not wait_for(lambda: not on_memo(), limit=5.0):
    warning(f"The memo dialog is still up after OK; cancelling out of {text!r}.")
    tap(constants.VETERAN_MEMO_CANCEL_MOUSE_POS, settle=1.0)
    return False
  # No text comparison here either, for the same reason. The authority on
  # whether the memo went in is the game: it raises its own error when it
  # refuses one, and that was checked above. All that is left is that the
  # card is back and carrying something.
  written = read_header(grab())["memo"]
  if not written:
    warning(f"The card shows no memo after writing {text!r}.")
    return False
  return True


def wait_for(condition, limit=5.0, poll=0.4):
  """Poll a screen condition until it holds, or give up. Returns whether it
  held. Used wherever the game animates: a dialog fading in or out is a second
  of frames that are neither one state nor the other."""
  deadline = time.time() + limit
  while True:
    if condition():
      return True
    if time.time() >= deadline or state.stop_event.is_set():
      return False
    sleep(poll)


def read_memo_field(screen):
  """What is in the memo dialog's input box."""
  return " ".join(t for t, _, _ in
                  read_boxes(crop(screen, constants.VETERAN_MEMO_FIELD_REGION))).strip()


def same_memo(shown, wanted):
  """Whether a read of a memo is the memo that was asked for.

  Case and spacing are ignored, and so are O against 0 and S against 5.
  """
  # O/0 and S/5 both: the ids are V001-style, easyocr reads a zero as either
  # and a five as either ("V050" came back as "VosO"), and failing a write
  # over the glyph the font chose would be absurd.
  def flatten(text):
    text = text.replace(" ", "").lower()
    return text.replace("o", "0").replace("s", "5")
  return flatten(shown) == flatten(wanted)


# --------------------------------------------------------------------------
# Getting to the roster.
# --------------------------------------------------------------------------

def read_registered(screen):
  """(registered, capacity) from the roster footer, or (-1, -1)."""
  text = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_ROSTER_REGISTERED_REGION)))
  found = re.search(r"(\d+)\s*/\s*(\d+)", text.replace(" ", ""))
  return (int(found.group(1)), int(found.group(2))) if found else (-1, -1)


def label_near(screen, point, half=(150, 26)):
  """The text around a point, for checking a menu came up before pressing on.

  The Enhance menu and the Veteran Umamusume menu have no template, and they
  do not need one: each is identified by the words on the button about to be
  pressed.
  """
  x, y = point
  region = (x - half[0], y - half[1], half[0] * 2, half[1] * 2)
  return " ".join(t for t, _, _ in read_boxes(crop(screen, region))).strip().lower()


def read_sort(screen):
  """(key, order) as the roster footer states them, e.g. ("Date Acquired", "Asc")."""
  key = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_ROSTER_SORT_KEY_REGION)))
  order = " ".join(t for t, _, _ in read_boxes(crop(screen, constants.VETERAN_ROSTER_SORT_ORDER_REGION)))
  return tidy_button(key), tidy_button(order)


def tidy_button(text):
  """A footer button's label without the icon beside it.

  Both buttons carry a small glyph that easyocr reads as one more capital on
  the end - "Date Acquired" came back as "Date AcquiredL" - so a trailing
  capital that is stuck to the end of a word, and anything that is not a
  letter or a space, is dropped.
  """
  text = re.sub(r"[^A-Za-z ]+", "", text).strip()
  return re.sub(r"(?<=[a-z])[A-Z]+$", "", text)


def ensure_ascending():
  """Put the roster in oldest-first order, and say whether it worked.

  This is not cosmetic. The ids are positional, so the order has to be one that
  **appends**: newest-first renumbers every card the next time a career
  finishes, and every memo already written would then name the wrong row.
  Oldest-first only ever adds to the end.
  """
  key, order = read_sort(grab())
  if order.lower().startswith("asc"):
    return True
  info(f"Roster is sorted {key} {order}; switching to ascending.")
  tap(constants.VETERAN_ROSTER_SORT_ORDER_MOUSE_POS, settle=1.5)
  key, order = read_sort(grab())
  if not order.lower().startswith("asc"):
    warning(f"Roster order still reads {order!r}; the ids would not be stable.")
    return False
  return True
