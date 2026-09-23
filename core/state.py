import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageGrab
import re
import json
import os
import threading
import time
import Levenshtein
from math import floor

from utils.log import info, warning, error, debug

from utils.screenshot import capture_region, enhanced_screenshot, enhance_for_reading
from core.ocr import extract_text, extract_number, extract_text_improved, read_boxes, in_range, NUMBER_MIN_CONFIDENCE
from core.recognizer import match_template, count_pixels_of_color, find_color_of_pixel, closest_color, multi_match_templates

import utils.constants as constants

STAT_VALUE_RANGE = (1, 1600)
STAT_CAP_RANGE = (800, 2200)
FAILURE_RANGE = (0, 99)
SKILL_PTS_RANGE = (0, 9999)
TURNS_LEFT_RANGE = (0, 99)

stop_event = threading.Event()
is_bot_running = False
bot_thread = None
bot_lock = threading.Lock()

MINIMUM_MOOD = None
PRIORITIZE_G1_RACE = None
IS_AUTO_BUY_SKILL = None
SKILL_PTS_CHECK = None
SKILL_DISTANCE = None
SKILL_RUN_STYLE = None
# Full "[Title] Name" of the trainee, for core/trainee.py's pre-career check.
TRAINEE = ""
PRIORITY_STAT = None
MAX_FAILURE = None
STAT_CAPS = None
CURRENT_YEAR = ""
# The last turn read in the lobby, for paths that act between two lobby reads.
CURRENT_TURN = None
SPIRIT_GAUGE_POINTS = 1.0
SPIRIT_BURST_POINTS = 2.0
SPIRIT_BURST_EX_POINTS = 3.0
BURST_ENABLED_STATS = []
CANCEL_CONSECUTIVE_RACE = None
SLEEP_TIME_MULTIPLIER = 1
# Grand Concert lessons. See core/lessons.py.
SONG_PRIORITY = []
SONG_PLAN = [4, 8, 12, 16, 18]
LYRICS_OPTION = 5
HOLD_FOR_TOP_SONGS = 2
ENERGY_TECHNIQUE_BELOW = 50
PERFORMANCE_SHORT_POINTS = 0.75
PERFORMANCE_URGENT_POINTS = 4.0
ALWAYS_BUY_GOLD_SKILL = False
# The game mode from config: "auto", "ura", "unity" or "grand_concert". A fixed
# mode sets the SEEN flags outright (apply_scenario); "auto" learns them by
# sighting the mode's own screens (saw_scenario).
#
# Trackblazer was removed from this list on 2026-09-21 - its Climax Store was
# more screen-driving than the run was worth. The scoring tables it left behind
# are still live (core/trackblazer.py, core/epithets.py) because the Race Plan
# tab is built on them; only the mode is gone. docs/TODO.md has the write-up
# and core/parked/ has the screen code.
SCENARIO = "auto"
SCENARIOS = ("auto", "ura", "unity", "grand_concert")
SCENARIO_NAMES = {"ura": "URA Finale", "unity": "Unity Cup",
                  "grand_concert": "Grand Concert"}
# Accepted by resolve_scenario with a warning rather than the generic "unknown
# mode" one, so a config saved before the removal says why it stopped working.
PARKED_SCENARIOS = {"trackblazer": "Trackblazer"}
# True when this career is Grand Concert: set by the config, or in "auto" once
# the lobby has shown a Lessons button, which only Grand Concert has.
GRAND_CONCERT_SEEN = False
# Career end. See core/sparks.py.
MAX_RACE_RETRIES = 1
REROLL_SPARKS = True
TP_BOTTLE_FLOOR = 50
CAREER_START_ENABLED = False
CAREER_START_BORROW_CARD = ""
CAREER_START_MAX = 0
RESTART_ON_FREEZE = False
# Careers career_start has begun since the bot was last started. Live state,
# not config: career_lobby() resets it and the config page reads it back.
CAREERS_STARTED = 0

def load_config():
  with open("config.json", "r", encoding="utf-8") as file:
    return json.load(file)

def reload_config():
  global PRIORITY_STAT, PRIORITY_WEIGHT, MINIMUM_MOOD, MINIMUM_MOOD_JUNIOR_YEAR, MAX_FAILURE
  global PRIORITIZE_G1_RACE, CANCEL_CONSECUTIVE_RACE, STAT_CAPS, IS_AUTO_BUY_SKILL, SKILL_PTS_CHECK, SKILL_DISTANCE, SKILL_RUN_STYLE
  global PRIORITY_EFFECTS_LIST, SKIP_TRAINING_ENERGY, NEVER_REST_ENERGY, SKIP_INFIRMARY_UNLESS_MISSING_ENERGY, PREFERRED_POSITION
  global ENABLE_POSITIONS_BY_RACE, POSITIONS_BY_RACE, POSITION_SELECTION_ENABLED, SLEEP_TIME_MULTIPLIER
  global TRAINEE
  global RACE_SCHEDULE, CONFIG_NAME, USE_OPTIMAL_EVENT_CHOICE, EVENT_CHOICES, USE_CLAW_MACHINE, CLAW_1_TIMER, CLAW_2_TIMER, CLAW_3_TIMER

  config = load_config()

  PRIORITY_STAT = config["priority_stat"]
  PRIORITY_WEIGHT = config["priority_weight"]
  MINIMUM_MOOD = config["minimum_mood"]
  MINIMUM_MOOD_JUNIOR_YEAR = config["minimum_mood_junior_year"]
  MAX_FAILURE = config["maximum_failure"]
  PRIORITIZE_G1_RACE = config["prioritize_g1_race"]
  CANCEL_CONSECUTIVE_RACE = config["cancel_consecutive_race"]
  # Alarm Clocks the bot may spend retrying a lost race, per career. 0 never
  # retries; a lost goal race otherwise ends the career on the spot.
  global MAX_RACE_RETRIES, REROLL_SPARKS
  MAX_RACE_RETRIES = config.get("max_race_retries", 1)
  # Spend 30 TP at career end when the stat spark is not 3-star. Off keeps
  # whatever the career rolled, which is what the bot did before.
  REROLL_SPARKS = config.get("reroll_sparks", True)
  # TP bottles the bot will not spend below when a spark reroll needs TP.
  global TP_BOTTLE_FLOOR
  TP_BOTTLE_FLOOR = config.get("tp_bottle_floor", 50)
  # Starting the next career by itself, from the game's own home screen. Off by
  # default: it spends 30 TP, and the borrowed card it needs has to be named
  # once before it can fill the Friends slot. The same tp_bottle_floor above
  # governs whether a bottle may be spent to afford the career.
  global CAREER_START_ENABLED, CAREER_START_BORROW_CARD
  career_start = config.get("career_start", {}) or {}
  CAREER_START_ENABLED = career_start.get("enabled", False)
  CAREER_START_BORROW_CARD = career_start.get("borrow_card", "")
  # How many careers one run may start before it stops on purpose. 0 is no
  # limit, which is what an overnight run wants; a number is for leaving it
  # going a fixed distance and finding the game where it stopped.
  global CAREER_START_MAX
  CAREER_START_MAX = career_start.get("max_consecutive", 0)
  # Close and relaunch the game when the client stops drawing, then resume the
  # career. Off by default: it ends the game process, and doing that to a
  # client that is only slow would cost whatever was on screen.
  global RESTART_ON_FREEZE
  RESTART_ON_FREEZE = config.get("restart_on_freeze", False)
  STAT_CAPS = config["stat_caps"]
  IS_AUTO_BUY_SKILL = config["skill"]["is_auto_buy_skill"]
  SKILL_PTS_CHECK = config["skill"]["skill_pts_check"]
  # What this Uma will run in Team Trials. A skill gated on a running
  # style or distance it does not have can never fire, so these decide
  # which skills are worth any skill points at all.
  SKILL_DISTANCE = config["skill"].get("skill_distance") or []
  SKILL_RUN_STYLE = config["skill"].get("skill_run_style") or None
  PRIORITY_EFFECTS_LIST = {i: v for i, v in enumerate(config["priority_weights"])}
  SKIP_TRAINING_ENERGY = config["skip_training_energy"]
  unity_config = config.get("unity", {})
  global SPIRIT_GAUGE_POINTS, SPIRIT_BURST_POINTS, SPIRIT_BURST_EX_POINTS, BURST_ENABLED_STATS
  SPIRIT_GAUGE_POINTS = unity_config.get("spirit_gauge_points", 1.0)
  SPIRIT_BURST_POINTS = unity_config.get("spirit_burst_points", 2.0)
  SPIRIT_BURST_EX_POINTS = unity_config.get("spirit_burst_ex_points", 3.0)
  BURST_ENABLED_STATS = unity_config.get("burst_enabled_stats", [])
  gc_config = config.get("grand_concert", {})
  global SONG_PRIORITY, SONG_PLAN, LYRICS_OPTION, HOLD_FOR_TOP_SONGS, ENERGY_TECHNIQUE_BELOW, PERFORMANCE_SHORT_POINTS
  global PERFORMANCE_URGENT_POINTS, ALWAYS_BUY_GOLD_SKILL
  PERFORMANCE_SHORT_POINTS = gc_config.get("performance_short_points", 0.75)
  # What a needed point type is worth when the board is stuck or the 18th song
  # is running out of turns: 0.75 never changed a training choice (careers 4-5).
  PERFORMANCE_URGENT_POINTS = gc_config.get("performance_urgent_points", 4.0)
  ALWAYS_BUY_GOLD_SKILL = gc_config.get("always_buy_gold_skill", False)
  SONG_PRIORITY = gc_config.get("song_priority", [])
  SONG_PLAN = gc_config.get("song_plan") or [4, 8, 12, 16, 18]
  LYRICS_OPTION = gc_config.get("lyrics_option", 5)
  HOLD_FOR_TOP_SONGS = gc_config.get("hold_for_top_songs", 2)
  ENERGY_TECHNIQUE_BELOW = gc_config.get("energy_technique_below", 50)
  NEVER_REST_ENERGY = config["never_rest_energy"]
  SKIP_INFIRMARY_UNLESS_MISSING_ENERGY = config["skip_infirmary_unless_missing_energy"]
  PREFERRED_POSITION = config["preferred_position"]
  TRAINEE = config.get("trainee") or ""
  global SCENARIO
  SCENARIO = resolve_scenario(config.get("scenario"))
  apply_scenario()
  ENABLE_POSITIONS_BY_RACE = config["enable_positions_by_race"]
  POSITIONS_BY_RACE = config["positions_by_race"]
  POSITION_SELECTION_ENABLED = config["position_selection_enabled"]
  SLEEP_TIME_MULTIPLIER = config["sleep_time_multiplier"]
  RACE_SCHEDULE = sort_race_schedule(config["race_schedule"])
  CONFIG_NAME = config["config_name"]
  USE_OPTIMAL_EVENT_CHOICE = config["event"]["use_optimal_event_choice"]
  EVENT_CHOICES = config["event"]["event_choices"]
  # `or <default>` pinned use_claw_machine to True no matter what the config
  # said, and made a configured 0 timer fall back to the default.
  claw_config = config.get("claw_machine", {})
  USE_CLAW_MACHINE = claw_config.get("use_claw_machine", True)
  CLAW_1_TIMER = claw_config.get("claw_1_timer", 1599)
  CLAW_2_TIMER = claw_config.get("claw_2_timer", 900)
  CLAW_3_TIMER = claw_config.get("claw_3_timer", 599)



# Get Stat
def stat_state():
  stat_regions = {
    "spd": constants.SPD_STAT_REGION,
    "sta": constants.STA_STAT_REGION,
    "pwr": constants.PWR_STAT_REGION,
    "guts": constants.GUTS_STAT_REGION,
    "wit": constants.WIT_STAT_REGION
  }

  result = {}
  for stat, region in stat_regions.items():
    img = enhanced_screenshot(region)
    val = extract_number(img, value_range=STAT_VALUE_RANGE)
    result[stat] = val
  return result

def parse_stat_cap(text):
  """'/1400' -> 1400.

  The leading '/' is sometimes recognised as a 7. The field is only ever a slash
  plus three or four digits, so a five-digit value starting with 7 is
  unambiguous - but the fixup is only accepted when dropping that digit lands
  back inside the plausible range."""
  digits = re.sub(r"[^\d]", "", text)
  if not digits:
    return -1

  value = int(digits)
  if not in_range(value, STAT_CAP_RANGE) and len(digits) == 5 and digits[0] == "7":
    value = int(digits[1:])

  return value if in_range(value, STAT_CAP_RANGE) else -1

def stat_caps_state():
  """Read the "/NNNN" cap printed under each stat.

  Caps are not safe to hardcode: they rise between game versions, and they also
  differ per stat inside a single run because inherited sparks raise individual
  caps. A cap that will not read comes back as -1 so the caller keeps using the
  configured value - a truncated read must never be able to stop training."""
  cap_regions = {
    "spd": constants.SPD_STAT_CAP_REGION,
    "sta": constants.STA_STAT_CAP_REGION,
    "pwr": constants.PWR_STAT_CAP_REGION,
    "guts": constants.GUTS_STAT_CAP_REGION,
    "wit": constants.WIT_STAT_CAP_REGION
  }

  result = {}
  for stat, region in cap_regions.items():
    # Read with the full alphabet on purpose: with a digits-only allowlist the
    # leading "/" is forced into a 7, turning 1464 into 71464. No confidence
    # floor either - the field is just a slash and digits, so the range check in
    # parse_stat_cap is the real guard, and a correct but hesitant read is worth
    # more than falling back to a possibly stale configured cap.
    boxes = read_boxes(enhanced_screenshot(region))
    result[stat] = parse_stat_cap("".join(text for text, confidence, rect in boxes))
  return result

# Check support card in each training
def check_support_card(threshold=0.8, target="none"):
  SUPPORT_ICONS = {
    "spd": "assets/icons/support_card_type_spd.png",
    "sta": "assets/icons/support_card_type_sta.png",
    "pwr": "assets/icons/support_card_type_pwr.png",
    "guts": "assets/icons/support_card_type_guts.png",
    "wit": "assets/icons/support_card_type_wit.png",
    "friend": "assets/icons/support_card_type_friend.png"
  }

  count_result = {}

  SUPPORT_FRIEND_LEVELS = {
    "gray": [110,108,120],
    "blue": [42,192,255],
    "green": [162,230,30],
    "yellow": [255,173,30],
    "max": [255,235,120],
  }

  count_result["total_supports"] = 0
  count_result["total_hints"] = 0
  count_result["total_friendship_levels"] = {}
  count_result["hints_per_friend_level"] = {}

  for friend_level, color in SUPPORT_FRIEND_LEVELS.items():
    count_result["total_friendship_levels"][friend_level] = 0
    count_result["hints_per_friend_level"][friend_level] = 0

  hint_matches = match_template("assets/icons/support_hint.png", constants.SUPPORT_CARD_ICON_BBOX, threshold)
  for key, icon_path in SUPPORT_ICONS.items():
    count_result[key] = {}
    count_result[key]["supports"] = 0
    count_result[key]["hints"] = 0
    count_result[key]["friendship_levels"]={}

    for friend_level, color in SUPPORT_FRIEND_LEVELS.items():
      count_result[key]["friendship_levels"][friend_level] = 0

    matches = match_template(icon_path, constants.SUPPORT_CARD_ICON_BBOX, threshold)
    for match in matches:
      # add the support as a specific key
      count_result[key]["supports"] += 1
      # also add it to the grand total
      count_result["total_supports"] += 1

      #find friend colors and add them to their specific colors
      x, y, w, h = match
      match_horizontal_middle = floor((2*x+w)/2)
      match_vertical_middle = floor((2*y+h)/2)
      icon_to_friend_bar_distance = 66
      bbox_left = match_horizontal_middle + constants.SUPPORT_CARD_ICON_BBOX[0]
      bbox_top = match_vertical_middle + constants.SUPPORT_CARD_ICON_BBOX[1] + icon_to_friend_bar_distance
      wanted_pixel = (bbox_left, bbox_top, bbox_left+1, bbox_top+1)
      friendship_level_color = find_color_of_pixel(wanted_pixel)
      friend_level = closest_color(SUPPORT_FRIEND_LEVELS, friendship_level_color)
      count_result[key]["friendship_levels"][friend_level] += 1
      count_result["total_friendship_levels"][friend_level] += 1

      if hint_matches:
        for hint_match in hint_matches:
          distance = abs(hint_match[1] - match[1])
          if distance < 45:
            count_result["total_hints"] += 1
            count_result[key]["hints"] += 1
            count_result["hints_per_friend_level"][friend_level] +=1

  return count_result

FAILURE_LABEL = "failure"

def parse_failure_value(text):
  """Returns (value, saw_percent); value is -1 when the text is unusable.

  '6%' -> (6, True) is the trustworthy case. Without a '%' the trailing digit
  is almost always the '%' glyph read as a 9: measured against the live bubble,
  it comes back as '7%' most frames and '79' roughly one frame in eight, and a
  '%' dropped outright was never seen. So a trailing 9 is dropped - '79' -> 7,
  '399' -> 39. That is still a guess, which is why check_failure re-reads and
  only falls back on a guessed value when no attempt produced a '%'."""
  cleaned = re.sub(r"[^\d%]", "", text)
  if not cleaned:
    return -1, False

  saw_percent = "%" in cleaned
  if saw_percent:
    digits = cleaned.split("%")[0]
  else:
    digits = cleaned
    if len(digits) > 1 and digits.endswith("9"):
      digits = digits[:-1]

  if not digits.isdigit():
    return -1, False

  value = int(digits)
  if not in_range(value, FAILURE_RANGE):
    return -1, False
  return value, saw_percent

# Get failure chance (idk how to get energy value)
def check_failure():
  """Read the failure % from the bubble above the training button being held.

  The region has to be wide because the bubble follows whichever training is
  hovered, so most of it is character art. Anchoring on the "Failure" label and
  taking the nearest number to it is far steadier than scraping every digit out
  of the strip and trusting they belong to the same number.

  A reading that contains an explicit '%' is trustworthy; one without it has to
  guess whether a trailing 9 is the percent glyph. The bubble misreads that way
  intermittently, so re-read and prefer any attempt that produced a '%' before
  settling for a guessed value. The last attempt uses the raw colour crop: the
  grayscale pass suits the dark-on-light stat numbers but flattens the
  white-on-blue bubble text."""
  guessed = -1
  for attempt in range(3):
    if attempt < 2:
      img = enhanced_screenshot(constants.FAILURE_REGION)
    else:
      raw = capture_region(constants.FAILURE_REGION)
      img = raw.resize((raw.width * 2, raw.height * 2), Image.BICUBIC)

    value, saw_percent = read_failure_from(img)
    if value >= 0:
      if saw_percent:
        return value
      if guessed < 0:
        guessed = value

  if guessed < 0:
    debug("Failure chance unreadable after 3 attempts.")
  return guessed

def read_failure_from(img):
  boxes = read_boxes(img)
  if not boxes:
    return -1, False

  label = next(
    (b for b in boxes if Levenshtein.ratio(re.sub(r"[^a-z]", "", b[0].lower()), FAILURE_LABEL) >= 0.7),
    None
  )
  if label is None:
    # The label is only there to locate the number. OCR mangles it often enough
    # ("Tamute", "Tdmuie" for "Failure") that throwing away a perfectly readable
    # value is worse than using it: if exactly one box in the bubble carries an
    # explicit percentage, that is the failure chance. Requiring the % keeps
    # stray digits from the surrounding UI out.
    percents = []
    for text, confidence, rect in boxes:
      if "%" not in text:
        continue
      value, saw_percent = parse_failure_value(text)
      if value >= 0 and saw_percent:
        percents.append((value, saw_percent))
    if len(percents) == 1:
      debug(f"Failure label unreadable, using the only percentage in the bubble: {percents[0][0]}%")
      return percents[0]
    debug(f"Failure label not found. Read: {[b[0] for b in boxes]}")
    return -1, False

  lx, ly, lw, lh = label[2]

  # easyocr sometimes returns the label and the number as one box.
  inline, saw_percent = parse_failure_value(label[0])
  if inline >= 0:
    return inline, saw_percent

  best = None
  for text, confidence, rect in boxes:
    if rect == label[2] or confidence < NUMBER_MIN_CONFIDENCE:
      continue
    x, y, w, h = rect
    # Stay inside the bubble: the % sits just under the label, roughly centred.
    if not (-lh <= y - ly <= 4 * lh):
      continue
    if abs((x + w / 2) - (lx + lw / 2)) > 2 * lw:
      continue
    value, saw_percent = parse_failure_value(text)
    if value < 0:
      continue
    distance = abs((x + w / 2) - (lx + lw / 2)) + abs(y - ly)
    if best is None or distance < best[0]:
      best = (distance, value, saw_percent)

  if best is None:
    debug(f"No usable failure number near the label. Read: {[b[0] for b in boxes]}")
    return -1, False

  return best[1], best[2]

# Check mood
def check_mood():
  mood = capture_region(constants.MOOD_REGION)
  mood_text = extract_text(mood).upper()

  for known_mood in constants.MOOD_LIST:
    if known_mood in mood_text:
      return known_mood

  warning(f"Mood not recognized: {mood_text}")
  return "UNKNOWN"

# Maps the facility name printed in the training banner to the training key used
# everywhere else.
TRAINING_BANNER_NAMES = {
  "speed": "spd",
  "stamina": "sta",
  "power": "pwr",
  "guts": "guts",
  "wit": "wit"
}

# Unity Cup only. The spirit gauge is a flame that fills from the bottom, so the
# template covers just its constant upper part and matches a little loosely; the
# burst badge is a fixed graphic and can be matched tightly.
SPIRIT_GAUGE_CONFIDENCE = 0.60
BURST_READY_CONFIDENCE = 0.80
BURST_EXTREME_CONFIDENCE = 0.80
# Warn once per missing icon rather than on every facility of every turn.
_missing_unity_assets = set()
# True once any spirit gauge or burst badge has been seen this career, which is
# how the rest of the bot tells Unity Cup from every other scenario without a
# config switch. Gauges show up on the very first training scan of a Unity
# career, so anything that waits for a debuff or a race can trust it.
UNITY_SEEN = False
_scenario_warned = set()

def resolve_scenario(name):
  """The effective game mode for a config's `scenario` value.

  Anything this does not recognise becomes "auto", which plays rather than
  stalls. Parked modes get their own message: a config written before the mode
  was removed is not a typo, and saying "unknown game mode" about it sends the
  reader looking for one.
  """
  name = name or "auto"
  if name in PARKED_SCENARIOS:
    warning(f"{PARKED_SCENARIOS[name]} is parked and the bot no longer drives it"
            " (see core/parked/README.md); detecting the mode from the screen instead.")
    return "auto"
  if name not in SCENARIOS:
    warning(f"Unknown game mode {name!r} in config; detecting it from the screen instead.")
    return "auto"
  return name

def apply_scenario(new_career=False):
  """Set the mode flags from the configured game mode.

  A fixed mode sets them outright, at every start and every new career. "auto"
  clears them only for a new career: stopping and starting the bot mid-career
  keeps what it has already seen."""
  global UNITY_SEEN, GRAND_CONCERT_SEEN
  if SCENARIO == "auto":
    if new_career:
      UNITY_SEEN = False
      GRAND_CONCERT_SEEN = False
    return
  UNITY_SEEN = SCENARIO == "unity"
  GRAND_CONCERT_SEEN = SCENARIO == "grand_concert"

def saw_scenario(name, how):
  """The screen showed something only game mode `name` has.

  In "auto" that decides the mode. A fixed mode is kept as configured, with one
  warning per mode when the screen disagrees, since it usually means the Game
  mode setting is wrong for this career."""
  global UNITY_SEEN, GRAND_CONCERT_SEEN
  # A parked mode is reported once and then ignored. It cannot set a flag -
  # there is none - and it must not fall through to the mismatch warning
  # below, which would name a mode that is no longer selectable.
  if name in PARKED_SCENARIOS:
    if name not in _scenario_warned:
      _scenario_warned.add(name)
      warning(f"{how}, which only {PARKED_SCENARIOS[name]} has. That mode is parked"
              " and the bot does not drive it; this career will be played as if it"
              " were URA and its own screens will be left alone.")
    return
  if SCENARIO == "auto":
    if name == "unity" and not UNITY_SEEN:
      UNITY_SEEN = True
      info(f"{how}: this is Unity Cup.")
    elif name == "grand_concert" and not GRAND_CONCERT_SEEN:
      GRAND_CONCERT_SEEN = True
      info(f"{how}: this is Grand Concert.")
    return
  if name != SCENARIO and name not in _scenario_warned:
    _scenario_warned.add(name)
    warning(f"{how}, which only {SCENARIO_NAMES[name]} has, but the game mode is set to "
            f"{SCENARIO_NAMES[SCENARIO]}. Check the Game mode setting.")

def check_unity_icons():
  """Count Unity Cup spirit gauges and burst badges for the selected facility.

  Returns {"spirit": n, "burst": n, "burst_ex": n}; zeros outside Unity Cup.
  burst_ex needs assets/icons/unity_burst_extreme.png, which can only be cut
  from a live Extreme Spirit Burst; until then it stays 0 and only a warning
  is logged, once."""
  counts = {"spirit": 0, "burst": 0, "burst_ex": 0}
  # A fixed game mode other than Unity Cup has no icons to look for.
  if SCENARIO not in ("auto", "unity"):
    return counts
  for key, path, region, confidence in (
    ("spirit", "assets/icons/unity_spirit_gauge.png", constants.SPIRIT_GAUGE_BBOX, SPIRIT_GAUGE_CONFIDENCE),
    # The burst flame sits in the same rail column as the charging gauges, left
    # of SUPPORT_CARD_ICON_BBOX. Scanning the old bbox matched the orange
    # "stat up" chevron badge instead, which is why Burst was always 0.
    ("burst", "assets/icons/unity_burst_ready.png", constants.SPIRIT_GAUGE_BBOX, BURST_READY_CONFIDENCE),
    ("burst_ex", "assets/icons/unity_burst_extreme.png", constants.UNITY_RAIL_BBOX, BURST_EXTREME_CONFIDENCE),
  ):
    if not os.path.exists(path):
      if path not in _missing_unity_assets:
        _missing_unity_assets.add(path)
        warning(f"{path} is missing, so Unity {key} icons will never be detected.")
      continue
    try:
      matches = match_template(path, region, confidence)
    except Exception as e:
      debug(f"Unity {key} icon check failed: {e}")
      continue
    if not matches:
      continue
    # Template matching returns a cluster of hits per icon; collapse them.
    kept = []
    for x, y, w, h in matches:
      if not any(abs(x - kx) < 25 and abs(y - ky) < 25 for kx, ky in kept):
        kept.append((x, y))
    counts[key] = len(kept)
  if any(counts.values()):
    saw_scenario("unity", "Spirit gauge on the training screen")
  return counts

PERFORMANCE_TYPES = ("da", "pa", "vo", "vi", "co")
# The chip crops come from upstream's unity_cup_beta branch, where they were
# cut at this same 1920x1080 layout: Da/Vo/Vi/Co score 1.000 on this repo's own
# captures, and nothing on a lobby reaches 0.58. The second chip of a rainbow
# facility is the weakest real hit seen (0.805), hence the threshold.
PERFORMANCE_CHIP_CONFIDENCE = 0.78
PERFORMANCE_BADGE_MIN_RED = 250

def check_performance(screen=None):
  """Grand Concert Performance points, as the training screen shows them.

  Returns {"chips": {facility: [types]}, "short": [types]}:
  - chips: the type(s) each facility pays this turn, from the chip over its
    button. Two on a friendship training.
  - short: the types a scheduled song still needs more of - the rows of the
    Performance panel carrying a red "N more" badge. Empty when nothing is
    scheduled, which is when there is no particular type to chase.
  """
  if screen is None:
    screen = ImageGrab.grab()
  rgb = np.asarray(screen.convert("RGB"))
  bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

  left, top, right, bottom = constants.PERFORMANCE_CHIP_BBOX
  roi = bgr[top:bottom, left:right]
  facility_x = {key: getattr(constants, f"{key.upper()}_TRAIN_MOUSE_POS")[0] + constants.PERFORMANCE_CHIP_OFFSET_X
                for key in ("spd", "sta", "pwr", "guts", "wit")}
  chips = {key: [] for key in facility_x}
  for kind in PERFORMANCE_TYPES:
    template = cv2.imread(f"assets/grand_concert/chip_{kind}.png", cv2.IMREAD_COLOR)
    if template is None:
      continue
    result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= PERFORMANCE_CHIP_CONFIDENCE)
    h, w = template.shape[:2]
    seen = []
    for x, y in zip(xs, ys):
      cx, cy = left + x + w // 2, top + y + h // 2
      if any(abs(cx - sx) < 12 and abs(cy - sy) < 12 for sx, sy in seen):
        continue
      seen.append((cx, cy))
      key = min(facility_x, key=lambda k: abs(facility_x[k] - cx))
      if abs(facility_x[key] - cx) <= 30:
        chips[key].append(kind)

  left, top, right, bottom = constants.PERFORMANCE_BADGE_BBOX
  short = []
  for i, kind in enumerate(PERFORMANCE_TYPES):
    y = constants.PERFORMANCE_BADGE_FIRST_Y + i * constants.PERFORMANCE_ROW_PITCH
    band = rgb[max(top, y - 9):min(bottom, y + 9), left:right].astype(int)
    red = int(((band[..., 0] > 215) & (band[..., 1] < 120)
               & (band[..., 2] > 70) & (band[..., 2] < 170)).sum())
    if red >= PERFORMANCE_BADGE_MIN_RED:
      short.append(kind)
  return {"chips": chips, "short": short}

OUTING_BADGE_CONFIDENCE = 0.80

def check_outing_available():
  """True when the Recreation button shows the friend-outing badge.

  Friend-type supports (Tazuna and the like) do not hand out stats on the
  training facilities; their bond and their event chain come from outings, and
  the outing reliably restores energy and clears negative conditions. The badge
  is how the lobby says one is on offer.
  """
  # Grand Concert's extra Lessons button pushes Recreation left, out of the
  # usual box. Scoped per scenario rather than widened, because the widened box
  # would take in the Lessons button's own pink badge.
  box = constants.GC_RECREATION_BADGE_BBOX if GRAND_CONCERT_SEEN else constants.RECREATION_BADGE_BBOX
  try:
    found = match_template("assets/icons/recreation_badge.png", box, OUTING_BADGE_CONFIDENCE)
  except Exception as e:
    debug(f"Outing badge check failed: {e}")
    return False
  return bool(found)

# The filled chevrons are a flat cyan-blue; the empty ones are a light grey
# outline on white. Hue alone separates them, and it survives the fill
# animation, so there is no template to match and nothing to keep in step with
# however many chevrons the chain has.
CHEVRON_HUE = (180, 220)
CHEVRON_MIN_AREA = 300
CHEVRON_SIZE = (22, 48)

def count_filled_chevrons(img):
  """Filled Event Progress chevrons in a full-screen image."""
  bbox = constants.RECREATION_CHEVRON_BBOX
  strip = np.array(img.crop(bbox).convert("RGB"))
  hsv = cv2.cvtColor(cv2.cvtColor(strip, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
  hue = hsv[:, :, 0].astype(int) * 2
  mask = ((hue >= CHEVRON_HUE[0]) & (hue <= CHEVRON_HUE[1])
          & (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 80)).astype(np.uint8)
  count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

  filled = 0
  for i in range(1, count):
    w = stats[i, cv2.CC_STAT_WIDTH]
    h = stats[i, cv2.CC_STAT_HEIGHT]
    if stats[i, cv2.CC_STAT_AREA] < CHEVRON_MIN_AREA:
      continue
    if not (CHEVRON_SIZE[0] <= w <= CHEVRON_SIZE[1]):
      continue
    if not (CHEVRON_SIZE[0] <= h <= CHEVRON_SIZE[1]):
      continue
    filled += 1
  return filled

def check_recreation_panel(img=None):
  """Read the friend card and its chain position off the Recreation panel.

  Returns {"card": name, "filled": n}, or None when nothing could be read. The
  panel states outright what the bot otherwise has to infer - which friend card
  is in the deck, and how many chain steps are already done - so this beats
  counting outings, which cannot tell an outing that was taken from one that
  was opened and abandoned.

  Fails closed: a bad read returns None and leaves the counted position alone
  rather than overwriting it with a guess.
  """
  try:
    if img is None:
      img = ImageGrab.grab()
    filled = count_filled_chevrons(img)
  except Exception as e:
    debug(f"Could not read the Recreation chevron row: {e}")
    return None

  # Same frame as the chevrons, so the name and the position cannot disagree.
  region = constants.RECREATION_NAME_REGION
  name = extract_text(enhance_for_reading(
    img.crop((region[0], region[1], region[0] + region[2], region[1] + region[3]))))
  debug(f"Recreation panel: {name!r}, {filled} chevrons filled.")
  return {"card": name, "filled": filled}

def read_log_lines():
  """Lines of the game's Log panel, newest last.

  The Log is the only place that says what an action actually did rather than
  what it was going to do, so it is how a predicted outing gets checked
  against the real one. Reads unenhanced: the text is a light salmon on white
  and the contrast pass loses more to the resize than it gains.
  """
  try:
    boxes = read_boxes(capture_region(constants.LOG_PANEL_REGION))
  except Exception as e:
    debug(f"Could not read the Log panel: {e}")
    return []
  # read_boxes returns (text, confidence, rect); rect is (x, y, w, h).
  ordered = sorted(boxes, key=lambda b: (b[2][1], b[2][0]))
  return [text for text, confidence, rect in ordered if text.strip()]

# Each option on the Choices panel is introduced by a flat green header bar,
# and its effects sit underneath in plain text. Counting the bars is what gives
# the option order, so nothing depends on reading the option text - which OCRs
# poorly, and does not need to be read at all.
CHOICE_HEADER_HUE = (80, 110)
CHOICE_HEADER_MIN_SAT = 120
CHOICE_HEADER_MIN_VAL = 140
# A header spans most of the panel; a green word inside the effects text does
# not. Height rejects the thin divider lines.
CHOICE_HEADER_MIN_WIDTH = 200
CHOICE_HEADER_MIN_HEIGHT = 8

def find_choice_headers(img):
  """Top and bottom y of each option header on the Choices panel, in order."""
  left, top, right, bottom = constants.CHOICES_PANEL_BBOX
  arr = np.array(img.convert('RGB'))[top:bottom, left:right]
  hsv = cv2.cvtColor(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
  hue = hsv[:, :, 0].astype(int) * 2
  green = ((hue >= CHOICE_HEADER_HUE[0]) & (hue <= CHOICE_HEADER_HUE[1])
           & (hsv[:, :, 1] >= CHOICE_HEADER_MIN_SAT)
           & (hsv[:, :, 2] >= CHOICE_HEADER_MIN_VAL))

  rows = green.sum(axis=1)
  bands, start = [], None
  for y, count in enumerate(rows):
    if count > CHOICE_HEADER_MIN_WIDTH and start is None:
      start = y
    elif count <= CHOICE_HEADER_MIN_WIDTH and start is not None:
      if y - start >= CHOICE_HEADER_MIN_HEIGHT:
        bands.append((top + start, top + y - 1))
      start = None
  if start is not None and len(rows) - start >= CHOICE_HEADER_MIN_HEIGHT:
    bands.append((top + start, bottom - 1))
  return bands

# Any right-hand panel with green section bars looks like a list of choices to
# find_choice_headers: the Career Profile has four (Trainee, Legacy Umamusume,
# Support Cards, Event Bonus Umamusume) and the Log has one per scenario
# section. Measured over 33 captured frames, those produced confident readings
# of things like "legacy 1 legacy 2" and "event bonus total ep 103%".
#
# So the panel title gates the read. It separates 1.000 against a best negative
# of 0.453, and it is the only thing on screen that means this really is the
# Choices panel rather than a green heading that happens to be the right shape.
CHOICES_TITLE_THRESHOLD = 0.8

def choices_panel_open(img):
  """True when the Choices panel title is on screen."""
  return bool(multi_match_templates({"choices": "assets/ui/choices_panel.png"},
                                    screen=img,
                                    threshold=CHOICES_TITLE_THRESHOLD)["choices"])

def read_choice_effects(img=None):
  """Effect lines for each option of the event on screen, top option first.

  Returns [] when the Choices panel is not up, so an absent panel can never be
  mistaken for an event whose options all do nothing.
  """
  try:
    if img is None:
      img = ImageGrab.grab()
    if not choices_panel_open(img):
      return []
    headers = find_choice_headers(img)
  except Exception as e:
    debug(f"Could not read the Choices panel: {e}")
    return []

  if not headers:
    return []

  left, _, right, bottom = constants.CHOICES_PANEL_BBOX
  choices = []
  for i, (_, header_bottom) in enumerate(headers):
    # An option's effects run from under its own header to the next one, which
    # is what makes this work for a two-line result and a five-line one alike.
    end = headers[i + 1][0] if i + 1 < len(headers) else bottom
    if end - header_bottom < 12:
      choices.append([])
      continue
    crop = img.crop((left, header_bottom + 4, right, end - 4))
    # Worth the contrast pass here, unlike the Log: raw reads drop the
    # minus off "Mood -3" and mangle "attribute(s)", and a dropped sign
    # silently turns a penalty into nothing.
    choices.append(group_lines(read_boxes(enhance_for_reading(crop))))

  debug(f"Choices panel: {len(choices)} options, {choices}")
  return choices

def group_lines(boxes, gap=14):
  """Join OCR boxes that share a line, so "Energy" and "+5" read as one."""
  # read_boxes returns (text, confidence, rect) with rect (x, y, w, h).
  items = sorted(((rect[1], rect[0], text) for text, _, rect in boxes if text.strip()))
  lines, current, last_y = [], [], None
  for y, x, text in items:
    if last_y is not None and y - last_y > gap:
      lines.append(current)
      current = []
    current.append((x, text))
    last_y = y
  if current:
    lines.append(current)
  return [" ".join(text for _, text in sorted(line)) for line in lines]

def check_selected_training():
  """Read the green banner naming the currently selected training facility.

  Returns (key, level), e.g. ("spd", 1). key is None when the banner cannot be
  read, which is the caller's signal that we are not on the training screen or
  the click did not land.
  """
  banner = capture_region(constants.TRAINING_BANNER_REGION)
  boxes = read_boxes(banner)
  text = " ".join(t for t, conf, rect in boxes).lower()

  best_key, best_score = None, 0.0
  for token in re.findall(r"[a-z]+", text):
    for name, key in TRAINING_BANNER_NAMES.items():
      score = Levenshtein.ratio(token, name)
      if score > best_score:
        best_key, best_score = key, score

  if best_score < 0.6:
    debug(f"Training banner not recognized: {text!r}")
    return None, 0

  # "Lvl 1" - the digit is small and is the first thing OCR drops, so treat a
  # missing level as unknown rather than failing the whole read.
  level_match = re.search(r"lvl\s*(\d)", text)
  level = int(level_match.group(1)) if level_match else 0

  return best_key, level

# The calendar box's digits, one glyph at a time. The font's "1" carries a flag,
# and read as a whole number easyocr turned "11" into "17" (0.32 confidence) -
# with no way to tell it was wrong. Split into glyphs, a "1" is plain to see: it
# is 13-14px wide (width/height 0.34-0.39) where every other digit is 25-30px
# (0.68-0.75). Only the wide ones go to OCR, one at a time. Measured on 12
# lobbies across both box colours (purple Grand Concert, blue URA/Unity).
# Deliberately still (25, 50), which means this reader DECLINES on every live
# lobby frame and the OCR fallback does all the real work. That is not an
# oversight - widening it was tried on 2026-09-19 and made things worse.
#
# The live lobby renders this box at a different scale from the 17 saved
# fixtures: fixture digits stand 36-40px, live digits 22-23px. Lowering the
# floor to 20 does admit them, and the components are found in the right places
# - on a frame whose box read "11 turn(s) left", both glyphs were located at
# x=26 and x=64, w=16-17, h=22. But at that scale the per-glyph OCR returns
# nothing at all for them, so the function still bails; and where two digits
# touch they merge into one 31-34px blob at aspect ~1.4, which easyocr reads as
# a single wrong character - '0' for a 9, '2' for a 6.
#
# So the widened band turns silent Nones into confidently wrong numbers, which
# is the worse failure: a None falls through to the fallback, a wrong digit does
# not. Reading this box at the live scale needs a digit-template bank cut from
# live crops, the way core/gains.py works - not a threshold change. The 27 live
# captures in tests/fixtures/turn/live/ are the material for it.
TURN_GLYPH_HEIGHT = (25, 50)
TURN_GLYPH_MAX_WIDTH = 40
TURN_ONE_MAX_ASPECT = 0.5
TURN_MIN_WHITE = 0.35

def read_turn_digits(screen=None, crop=None):
  """The turns-left number read glyph by glyph, or None if it does not read.

  Pass a full screenshot as screen, or an already-cut digits crop as crop.
  """
  if crop is None:
    # Imported here rather than at module scope: core/scenarios.py imports this
    # module, so a top-level import would be circular.
    import core.scenarios as scenarios
    region = scenarios.get("turn_digits_region")
    if screen is None:
      crop = capture_region(region)
    else:
      left, top, width, height = region
      crop = screen.crop((left, top, left + width, top + height))
  result = _read_turn_digits(crop)
  if TURN_DEBUG_DIR:
    _save_turn_frame(crop, result)
  return result


# Set UMA_TURN_DEBUG to a directory to keep every crop this reader is handed,
# named after what it returned. Off by default: it writes a file per turn.
#
# It exists because capturing the frame any other way does not work. A tool that
# watched the log for a year string and then grabbed the screen caught the race
# screen three steps later - the bot reads the box, decides, and moves on inside
# a second. The only place the reader's actual input exists is here.
TURN_DEBUG_DIR = os.environ.get("UMA_TURN_DEBUG") or ""


def _save_turn_frame(crop, result):
  """Keep the crop next to the number it produced, for offline replay."""
  try:
    os.makedirs(TURN_DEBUG_DIR, exist_ok=True)
    stamp = time.strftime("%H%M%S")
    crop.save(os.path.join(TURN_DEBUG_DIR, f"turn_{stamp}_read{result}.png"))
  except Exception as e:                       # never let debugging break a turn
    debug(f"turn-frame capture failed, ignored ({e}).")


def _read_turn_digits(crop):
  """The glyph-by-glyph read itself. Split out so the capture above can wrap it
  without duplicating any of the logic."""
  rgb = np.asarray(crop.convert("RGB"))
  # The digits sit on the calendar's white card (~60% of the region). With no
  # card there is no counter to read, only whatever else is on that screen.
  if (rgb > 225).all(-1).mean() < TURN_MIN_WHITE:
    return None
  hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(int)
  mask = ((hsv[..., 1] > 50) & (hsv[..., 2] > 90)).astype(np.uint8)
  n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
  glyphs = []
  for k in range(1, n):
    x, y, w, h, _ = stats[k]
    # The box's own coloured frame is one big component; skip it.
    if not (TURN_GLYPH_HEIGHT[0] <= h <= TURN_GLYPH_HEIGHT[1]) or w > TURN_GLYPH_MAX_WIDTH:
      continue
    glyphs.append((x, w, h, (labels[y:y + h, x:x + w] == k).astype(np.uint8)))
  if not glyphs or len(glyphs) > 2:
    return None
  text = ""
  for x, w, h, glyph in sorted(glyphs, key=lambda g: g[0]):
    if w / h < TURN_ONE_MAX_ASPECT:
      text += "1"
      continue
    padded = np.full((h + 24, w + 24), 255, np.uint8)
    padded[12:12 + h, 12:12 + w] = 255 - glyph * 255
    padded = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    digits = [b for b in read_boxes(Image.fromarray(padded), allowlist="0123456789") if b[0]]
    if not digits:
      return None
    text += max(digits, key=lambda b: b[1])[0][:1]
  return int(text) if text.isdigit() else None

# Check turn
def check_turn():
    turn = capture_region(constants.TURN_REGION)
    turn_text = extract_text_improved(turn)

    # Unity Cup renders the goal counter much smaller than URA does (it has to
    # fit a second "Until the Unity Cup" box underneath), small enough that OCR
    # reads 9 as 0 or misses 11 entirely at native size. Upscaling hard first
    # reads both layouts reliably.
    enlarged = ImageEnhance.Contrast(turn.convert("L")).enhance(1.8)
    enlarged = enlarged.resize((enlarged.width * 5, enlarged.height * 5), Image.LANCZOS)

    # URA writes "Race Day" in this box; Unity Cup writes "GOAL" instead. Both
    # mean the same thing, and without the second case the turn falls through to
    # the number rule and picks up the "Until the Unity Cup" countdown, so the
    # race-day branch never fires and the bot hunts for a Training button that
    # the race-day lobby does not have.
    lowered = turn_text.lower()
    if "race" in lowered or "goal" in lowered:
        return "Race Day"

    glyph_read = read_turn_digits()
    if glyph_read is not None and in_range(glyph_read, TURNS_LEFT_RANGE):
      return glyph_read

    # Which path produced the number matters, and used to be invisible: the
    # glyph bank and the easyocr fallback both return a bare int, so a wrong
    # reading looked exactly like a right one. Two careers ran with Late Jul
    # reading 1 where the truth was 11 - six times over - and nothing in either
    # log said the fallback had been used at all. easyocr drops narrow digits
    # (the failure core/gains.py's template bank exists to avoid), so a fallback
    # reading is the first suspect whenever a turn count looks wrong.
    why = "declined" if glyph_read is None else f"out of range ({glyph_read})"
    debug(f"Turn glyph read {why}; falling back to OCR on the turn box.")

    # The region covers the goal counter and, in Unity Cup, the "Until the Unity
    # Cup" counter below it, so position still decides between two *real*
    # counters - but only after confidence has thrown out what is not a counter
    # at all.
    #
    # Ranking on position alone read the wrong number for two entire careers.
    # The region's top edge catches the year label, easyocr mangles "Classic"
    # into things like '(5obbic', and re.findall pulls a 5 out of it. Measured
    # live 2026-09-19:
    #
    #   box y= 18.0  conf=0.03  '(5obbic'  -> digit 5   <- garbage, and topmost
    #   box y=321.0  conf=0.99  '7'        -> digit 7   <- the actual counter
    #
    # Every "Classic Year stuck at 5" turn was that. Filtering at
    # NUMBER_MIN_CONFIDENCE is core/ocr.py's own rule for exactly this - see
    # extract_number, which refuses rather than return a plausible-but-wrong
    # number - so confidence leads and position is only the tie-break.
    numbers = []
    for text, conf, (bx, by, bw, bh) in read_boxes(enlarged):
      if conf < NUMBER_MIN_CONFIDENCE:
        debug(f"Ignoring {text!r} in the turn box: confidence {conf:.2f}"
              f" is under {NUMBER_MIN_CONFIDENCE}.")
        continue
      for found in re.findall(r"\d+", text):
        numbers.append((conf, by + bh / 2, int(found)))
    if not numbers:
      debug(f"OCR found no number in the turn box either ({turn_text!r}); returning -1.")
      return -1
    numbers.sort(key=lambda n: (-n[0], n[1]))
    turns_left = numbers[0][2]
    if not in_range(turns_left, TURNS_LEFT_RANGE):
      warning(f"Turn count out of range, ignoring: {turn_text}")
      return -1

    info(f"Turn {turns_left} came from the OCR fallback, not the glyph bank"
         f" (raw {turn_text!r}) - treat it as suspect.")
    return turns_left

# Check year
def check_current_year():
  year = enhanced_screenshot(constants.YEAR_REGION)
  text = extract_text(year)
  # On race days the turn box says "GOAL" in lettering tall enough to reach
  # this region, and it comes back as a stray "0" in front ("0 Junior Year
  # Early Dec"), which breaks every year_parts[0] == "Junior" check that turn.
  found = re.search(r"(Junior|Classic|Senior|Finale).*", text)
  return found.group(0) if found else text

# Check criteria
def check_criteria():
  img = enhanced_screenshot(constants.CRITERIA_REGION)
  text = extract_text(img)
  return text

def check_criteria_detail():
  img = enhanced_screenshot(constants.CRITERIA_DETAIL_REGION)
  text = extract_text(img)
  return text

# Get credit from claw event
def check_credit():
  img = enhanced_screenshot(constants.CLAW_EVENT_REGION)
  text = extract_text(img)
  return text

def check_skill_pts():
  img = enhanced_screenshot(constants.SKILL_PTS_REGION)
  return extract_number(img, value_range=SKILL_PTS_RANGE)

# Get credit from claw event
def check_credit():
  img = enhanced_screenshot(constants.CLAW_EVENT_REGION)
  text = extract_text(img)
  return text

previous_right_bar_match=""

# The training screen dims the slice of the energy bar that the selected
# training will spend. That dim tail is the only place the **real** cost is
# stated: it already has the deck's Energy Cost Reduction in it, and there is
# no other way to get that - support cards are recognised by type icon, never
# by name, so no effect can be looked up for them.
#
# Measured across one turn's five facilities (tests/fixtures/gains/024146_*):
# spd 20.8, sta 19.9, pwr 19.9, guts 15.7, wit 0.0, against database bases of
# 21/19/20/22 and wit's +5. Guts was six cheaper than its base that turn, which
# is a reduction that nothing else in the bot can see.
#
# The tail is dark and strongly coloured; the bright gradient is not (its every
# stop has a channel at 240+), and the grey of missing energy is not coloured at
# all, so brightness plus saturation separates all three.
RESERVED_MAX_BRIGHTNESS = 200
RESERVED_MIN_SATURATION = 40

# Counted pixels from one end of the bar to the other. Fine at 1080p, which is
# the only resolution any of these coordinates work at. Module level so the
# reserved-tail reader and check_energy_level share one number.
hundred_energy_pixel_constant = 236

def check_energy_reserved(threshold=0.85):
  """Energy the selected training will spend, read off the bar's dim tail.

  Returns None when the bar cannot be found and 0.0 when nothing is reserved -
  wit reserves nothing, because it hands energy back. Callers fall back to
  core.training_cost's database figure when this is None.
  """
  bar = match_template("assets/ui/energy_bar_right_end_part.png", constants.ENERGY_BBOX, threshold)
  if not bar:
    bar = match_template("assets/ui/energy_bar_right_end_part_2.png", constants.ENERGY_BBOX, threshold)
  if not bar:
    return None

  bar_end = bar[0][0]
  left, top, right, bottom = constants.ENERGY_BBOX
  middle = int(round((top + bottom) / 2))
  try:
    strip = ImageGrab.grab(bbox=(left, middle, left + bar_end, middle + 1)).convert("RGB")
  except Exception as e:
    debug(f"Could not read the energy bar for a cost preview: {e}")
    return None

  reserved = 0
  for x in range(strip.width):
    r, g, b = strip.getpixel((x, 0))
    if max(r, g, b) < RESERVED_MAX_BRIGHTNESS and (max(r, g, b) - min(r, g, b)) > RESERVED_MIN_SATURATION:
      reserved += 1
  return reserved / hundred_energy_pixel_constant * 100

def check_energy_level(threshold=0.85):
  # find where the right side of the bar is on screen
  global previous_right_bar_match
  right_bar_match = match_template("assets/ui/energy_bar_right_end_part.png", constants.ENERGY_BBOX, threshold)
  # longer energy bars get more round at the end
  if not right_bar_match:
    right_bar_match = match_template("assets/ui/energy_bar_right_end_part_2.png", constants.ENERGY_BBOX, threshold)

  if right_bar_match:
    x, y, w, h = right_bar_match[0]
    energy_bar_length = x

    x, y, w, h = constants.ENERGY_BBOX
    top_bottom_middle_pixel = round((y + h) / 2, 0)

    MAX_ENERGY_BBOX = (x, top_bottom_middle_pixel, x + energy_bar_length, top_bottom_middle_pixel+1)


    #[117,117,117] is gray for missing energy, region templating for this one is a problem, so we do this
    empty_energy_pixel_count = count_pixels_of_color([117,117,117], MAX_ENERGY_BBOX)

    #use the energy_bar_length (a few extra pixels from the outside are remaining so we subtract that)
    total_energy_length = energy_bar_length - 1
    # hundred_energy_pixel_constant is module level now; see the note by
    # check_energy_reserved, which measures against the same scale.

    previous_right_bar_match = right_bar_match

    energy_level = ((total_energy_length - empty_energy_pixel_count) / hundred_energy_pixel_constant) * 100
    info(f"Total energy bar length = {total_energy_length}, Empty energy pixel count = {empty_energy_pixel_count}, Diff = {(total_energy_length - empty_energy_pixel_count)}")
    info(f"Remaining energy guestimate = {energy_level:.2f}")
    max_energy = total_energy_length / hundred_energy_pixel_constant * 100
    return energy_level, max_energy
  else:
    warning(f"Couldn't find energy bar, returning -1")
    return -1, -1

def get_race_type():
  race_info_screen = enhanced_screenshot(constants.RACE_INFO_TEXT_REGION)
  race_info_text = extract_text(race_info_screen)
  debug(f"Race info text: {race_info_text}")
  return race_info_text

# Severity -> 0 is doesn't matter / incurable, 1 is "can be ignored for a few turns", 2 is "must be cured immediately"
BAD_STATUS_EFFECTS={
  "Migraine":{
    "Severity":2,
    "Effect":"Mood cannot be increased",
  },
  "Night Owl":{
    "Severity":1,
    "Effect":"Character may lose energy, and possibly mood",
  },
  "Practice Poor":{
    "Severity":1,
    "Effect":"Increases chance of training failure by 2%",
  },
  "Skin Outbreak":{
    "Severity":1,
    "Effect":"Character's mood may decrease by one stage.",
  },
  "Slacker":{
    "Severity":2,
    "Effect":"Character may not show up for training.",
  },
  "Slow Metabolism":{
    "Severity":2,
    "Effect":"Character cannot gain Speed from speed training.",
  },
  "Under the Weather":{
    "Severity":0,
    "Effect":"Increases chance of training failure by 5%"
  },
}

GOOD_STATUS_EFFECTS={
  "Charming":"Raises Friendship Bond gain by 2",
  "Fast Learner":"Reduces the cost of skills by 10%",
  "Hot Topic":"Raises Friendship Bond gain for NPCs by 2",
  "Practice Perfect":"Lowers chance of training failure by 2%",
  "Shining Brightly":"Lowers chance of training failure by 5%"
}

def check_status_effects():
  status_effects_screen = enhanced_screenshot(constants.FULL_STATS_STATUS_REGION)

  screen = np.array(status_effects_screen)  # currently grayscale
  screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)  # convert to 3-channel BGR for display

  #debug_window(screen)

  status_effects_text = extract_text(status_effects_screen)
  debug(f"Status effects text: {status_effects_text}")

  normalized_text = status_effects_text.lower().replace(" ", "")

  matches = [
      k for k in BAD_STATUS_EFFECTS
      if k.lower().replace(" ", "") in normalized_text
  ]

  total_severity = sum(BAD_STATUS_EFFECTS[k]["Severity"] for k in matches)

  debug(f"Matches: {matches}, severity: {total_severity}")
  return matches, total_severity

APTITUDES = {}

def check_aptitudes():
  global APTITUDES

  image = capture_region(constants.FULL_STATS_APTITUDE_REGION)
  image = np.array(image)
  h, w = image.shape[:2]

  # Ratios for each aptitude box (x, y, width, height) in percentages
  boxes = {
    "surface_turf":   (0.0, 0.00, 0.25, 0.33),
    "surface_dirt":   (0.25, 0.00, 0.25, 0.33),

    "distance_sprint": (0.0, 0.33, 0.25, 0.33),
    "distance_mile":   (0.25, 0.33, 0.25, 0.33),
    "distance_medium": (0.50, 0.33, 0.25, 0.33),
    "distance_long":   (0.75, 0.33, 0.25, 0.33),

    "style_front":  (0.0, 0.66, 0.25, 0.33),
    "style_pace":   (0.25, 0.66, 0.25, 0.33),
    "style_late":   (0.50, 0.66, 0.25, 0.33),
    "style_end":    (0.75, 0.66, 0.25, 0.33),
  }

  aptitude_images = {
    "a" : "assets/ui/aptitude_a.png",
    "b" : "assets/ui/aptitude_b.png",
    "c" : "assets/ui/aptitude_c.png",
    "d" : "assets/ui/aptitude_d.png",
    "e" : "assets/ui/aptitude_e.png",
    "f" : "assets/ui/aptitude_f.png",
    "g" : "assets/ui/aptitude_g.png"
  }

  crops = {}
  for key, (xr, yr, wr, hr) in boxes.items():
    x, y, ww, hh = int(xr*w), int(yr*h), int(wr*w), int(hr*h)
    cropped_image = np.array(image[y:y+hh, x:x+ww])
    matches = multi_match_templates(aptitude_images, cropped_image)
    for name, match in matches.items():
      if match:
        APTITUDES[key] = name
        #debug_window(cropped_image)

  info(f"Parsed aptitude values: {APTITUDES}. If these values are wrong, please stop and start the bot again with the hotkey.")

def debug_window(screen, x=-1400, y=-100):
  cv2.namedWindow("image")
  cv2.moveWindow("image", x, y)
  cv2.imshow("image", screen)
  cv2.waitKey(0)

def sort_race_schedule(race_schedule):
    year_order = {
        "Junior Year": 0,
        "Classic Year": 1,
        "Senior Year": 2
    }

    return sorted(
        race_schedule,
        key=lambda race: (
            year_order.get(race["year"], 999),
            constants.DATE_ARRAY.index(race["date"]) if race["date"] in constants.DATE_ARRAY else 999
        )
    )