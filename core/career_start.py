"""Starting the next career from the game's own home screen.

Everything a career needs is already chosen. The game reopens Scenario Select,
Trainee Select and Legacy Select on whatever was used last, and the support deck
is saved, so this walk presses Next three times and accepts what is there. The
one thing the game forgets is the **borrowed card** in the Friends slot: it is
spent with the career, and a deck with an empty Friends slot will not start -
`Start Career!` renders disabled until slot six is filled (measured 2026-09-18).
So the borrow is re-taken, and the card it looks for is whatever was borrowed
last time, remembered in `logs/career_start_progress.json` and seeded from
config `career_start.borrow_card` the first time.

This is what stood between the bot and an unattended night. `career_lobby()`
drives a career perfectly well and then stops dead at the home screen, because
`CAREER_BUTTON_MOUSE_POS` was pressed in exactly one place and only to resume
after a date change. On 2026-09-19 that ended three runs inside ten minutes.

**It is a reader loop, not a sequence of clicks.** Every pass grabs a frame,
identifies the screen from its own header, and presses one thing - the same
shape as `career_lobby()`, and for the same reason: a slow load, a popup or a
screen arriving out of order then costs a poll rather than a click landing on
whatever happens to be under the pointer. The measured positions are only ever
used *after* the screen they belong to has been recognised.

**Proven live 2026-09-22**, first try: Home to a started Grand Concert career
on Maruzensky in 57 seconds, every step landing on its first attempt, including
the borrow. The two brightness states of `Start Career!` were measured on that
run at 0.499 empty and 0.797 filled, against the 0.512/0.822 predicted from a
different career three days earlier. `docs/screen-map.md` has the full trace.
The one branch still unexercised is `restore_tp()`: that run had TP 100/100.
"""
import json
import os
import time
import uuid

from PIL import ImageGrab

import core.state as state
import utils.constants as constants
from core.ocr import extract_text, read_boxes
from core.recognizer import multi_match_templates
from utils.log import info, warning, error, debug
from utils.screenshot import enhance_for_reading
from utils.tools import sleep

# Each screen names itself in its own header, so that is what they are keyed on
# rather than on any button. The four setup screens share one grey pill at the
# top left and differ only in its wording, which is enough: cut to the same
# 240x32 crop they score 1.000 on themselves against a worst cross of 0.712
# (legacy against trainee), so 0.85 sits well inside the gap.
TEMPLATES = {
  "scenario_select": "assets/career/scenario_select.png",
  "trainee_select": "assets/career/trainee_select.png",
  "legacy_select": "assets/career/legacy_select.png",
  "support_formation": "assets/career/support_formation.png",
  "borrow_card": "assets/career/borrow_card.png",
  "final_confirmation": "assets/career/final_confirmation.png",
  # "Veteran Umamusume Max - You cannot add any more Veteran Umamusume.
  # 260/260. Please transfer a Veteran Umamusume before starting a Career
  # playthrough." A hard stop: the game will not start a career at all, and
  # clearing it means transferring a veteran out, which is the user's to
  # decide and not something to do unattended.
  "veteran_max": "assets/career/veteran_max.png",
  # The TP prompt's green button, shared with the spark reroll's own short-of-TP
  # dialog - the same asset core/sparks.py has been pressing since 2026-09-18.
  "restore_tp": "assets/buttons/restore_btn.png",
  # "Continue Career - Resume": pressing CAREER on a career that is still going
  # raises this instead of Scenario Select. Watched for, never pressed - see
  # RESUMED below.
  "continue_career": "assets/ui/continue_career.png",
}

# start()'s third outcome, beside True and False: there was already a career in
# progress, so there is nothing to start. Not a failure - `career_lobby` has a
# `continue_career` branch that presses Resume, and the walk leaves the dialog
# on screen for it rather than pressing Resume itself. One resume path, in the
# place that already owned it.
#
# Measured 2026-09-23 on a Post-Career state: without this the walk pressed
# CAREER, failed to recognise the dialog it had just raised, waited out all 40
# steps and stopped the bot on a career that only needed Resume.
RESUMED = "resumed"

# Polls before giving up on the walk. At roughly two seconds a pass plus the
# settles below, this is a couple of minutes - long enough for every screen to
# load twice over, short enough that a walk going nowhere hands back rather than
# pressing on. career_lobby stops the bot when this returns False, so it is the
# last thing that happens before a person is needed.
STEP_LIMIT = 40
# Times the Friends slot may be opened before the disabled Start Career! is
# taken to mean something else. Two, because the first borrow can fail on a
# list that has not loaded, and the second tells the two causes apart: an empty
# slot clears on the first successful take, a trainee conflict never clears.
BORROW_ATTEMPTS = 2
# Where the borrowed card is remembered between careers. Under logs/ beside
# grand_concert_progress.json, for the same reason: it is a running count of
# what a real run did, not repo data.
PROGRESS = os.path.join(os.environ.get("UMA_LOG_DIR", "logs"),
                        "career_start_progress.json")

def _click(pos, text):
  """core.execute's click at a point. Imported late: execute imports this
  module, so the other direction has to happen inside the call."""
  from core.execute import click
  return click(boxes=(pos[0], pos[1], 1, 1), text=text)

def remembered_card():
  """The card borrowed last career, or the configured one the first time.

  The file wins over the config because it is the record of what actually
  happened; the config is only ever the seed. A file naming a card that has
  since left the borrow list falls back to the config on the next failure, and
  that failure is logged rather than papered over with a different card."""
  try:
    with open(PROGRESS, encoding="utf-8") as f:
      name = (json.load(f) or {}).get("borrowed")
    if name:
      return name
  except (OSError, ValueError):
    pass
  return getattr(state, "CAREER_START_BORROW_CARD", "") or ""

def _progress():
  """The whole progress file, or an empty record."""
  try:
    with open(PROGRESS, encoding="utf-8") as f:
      return json.load(f) or {}
  except (OSError, ValueError):
    return {}

def _write(record):
  try:
    os.makedirs(os.path.dirname(PROGRESS) or ".", exist_ok=True)
    with open(PROGRESS, "w", encoding="utf-8") as f:
      json.dump(record, f, indent=2)
    return True
  except OSError as e:
    warning(f"Could not write {PROGRESS}: {e}")
    return False

def started_careers():
  """The careers begun since the count was last reset, newest last.

  Each is a row with its own uuid. The count is kept here rather than in a
  number in memory because the thing that most often ends a run is the client
  freezing, and the bot is restarted afterwards - an in-memory count would go
  back to zero every time and "three careers" would never mean three. The uuid
  is what makes a row identifiable rather than merely counted: two careers
  started in the same second are still two rows."""
  rows = _progress().get("careers")
  return rows if isinstance(rows, list) else []

def remember_card(name, career_uuid=None):
  """Record the borrowed card, and - when a career really began - the career.

  One file, written whole, because the two facts are written at the same moment
  and reading back a half-updated record would be worse than losing both."""
  record = _progress()
  record["borrowed"] = name
  record["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
  if career_uuid:
    rows = started_careers()
    rows.append({"uuid": career_uuid,
                 "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "borrowed": name})
    record["careers"] = rows
  _write(record)

def reset_count():
  """Forget the careers counted so far, keeping the borrowed card.

  What the config page's Reset button calls. The card is deliberately kept: it
  is the seed for the next borrow and has nothing to do with the count."""
  record = _progress()
  record["careers"] = []
  record["reset_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
  return _write(record)

def start_button_enabled(screen):
  """Is Support Formation's `Start Career!` live, or drawn disabled?

  Brightness, not saturation: measured 2026-09-19 on one frame, the disabled
  button read HSV value 0.512 against 0.822 for the enabled Auto-Fill right
  above it, while their saturations differed by 0.05. A saturation check misses
  the disabled state entirely, which is worth saying because "desaturated olive"
  invites exactly that check.

  Never trust this while a confirm modal is up: the overlay is a white wash that
  drops saturation and *raises* brightness, so under one both buttons look alike
  (Legacy Select's Auto-Select read 0.888 under a modal and 0.815 without)."""
  left, top, right, bottom = constants.START_CAREER_BUTTON_BBOX
  face = screen.crop((left, top, right, bottom)).convert("HSV")
  values = [v for _, _, v in face.getdata()]
  mean = sum(values) / float(len(values)) / 255.0
  debug(f"Start Career! face brightness {mean:.3f}"
        f" (disabled ~0.51, enabled ~0.82)")
  return mean >= constants.START_CAREER_ENABLED_VALUE

def read_borrow_rows(screen):
  """Every card name on the Borrow Card list, with where to tap for it.

  Read rather than counted off fixed row positions. The list is topped by a
  Remove button only while a card is already borrowed, so the rows below it sit
  ~147px lower in one case than the other, and a fixed row would take the wrong
  card in exactly the situation - a borrow already made - where taking the wrong
  one is worst. Each row prints the lender, the card title in brackets and the
  card name; it is the last of those that matters, so this returns every line
  with its own box and lets the caller match on it."""
  left, top, width, height = constants.BORROW_LIST_REGION
  crop = screen.crop((left, top, left + width, top + height))
  rows = []
  for text, conf, (x, y, w, h) in read_boxes(enhance_for_reading(crop)):
    text = (text or "").strip()
    if not text:
      continue
    # enhance_for_reading doubles the image, so halve back into screen pixels.
    # int() because read_boxes hands back numpy integers, which travel all the
    # way to control.moveTo before anything complains.
    rows.append((text, conf, (int(left + x // 2 + w // 4),
                              int(top + y // 2 + h // 4))))
  return rows

def take_borrow(screen, wanted):
  """Tap the row whose card name is `wanted`. True once one was pressed."""
  from rapidfuzz import fuzz
  rows = read_borrow_rows(screen)
  if not rows:
    warning("The Borrow Card list would not read; leaving it alone.")
    return False
  # Several lenders can offer the same card - three of the four rows on the
  # captured list are Light Hello - so ties go to the first, and read_boxes
  # returns reading order, which makes that the topmost row. With the list
  # sorted on Last Login that is also the most recently active lender.
  #
  # The length guard is not tidiness. partial_ratio scores the *best substring*
  # of the longer string, so a one-glyph box - and the list reads plenty of
  # them, an 'S' off a rarity badge, an 'I' off a card frame - scores 100
  # against any name containing that letter. Without this, asking for a card
  # the list does not hold picks the rarity badge of whatever row sorted first
  # and borrows it, which is the one outcome worth refusing outright. A row
  # that really carries the name cannot be shorter than the name.
  best, best_score = None, 0
  for text, conf, pos in rows:
    if len(text) + 2 < len(wanted):
      continue
    score = fuzz.partial_ratio(wanted.lower(), text.lower())
    if score > best_score:
      best, best_score = (text, pos), score
  if not best or best_score < constants.BORROW_NAME_MIN_RATIO:
    names = ", ".join(sorted({t for t, _, _ in rows}))
    warning(f"No row on the Borrow Card list reads as '{wanted}'"
            f" (best {best_score}). The list held: {names}."
            " Not taking a different card.")
    return False
  text, pos = best
  info(f"Borrowing '{wanted}' from the row reading '{text}'.")
  _click(pos, "Taking the borrowed card.")
  return True

def restore_tp():
  """Spend one TP bottle so the career can be paid for, if the stock allows.

  The same rule and the same two assets as core/sparks.py's reroll path, which
  has done this live since 2026-09-18: only the plain `Toughness 30` bottle is
  ever spent - Carats are money, and the handmade chocolates are one-offs - and
  only while more than `tp_bottle_floor` of them remain. Kept separate from
  sparks' copy rather than shared, because that one presses every button
  deliberately for a screen that swallows ordinary clicks, and these screens do
  not; the rule is what matters, and it is one config value in both.
  """
  from core.execute import click
  if not state.TP_BOTTLE_FLOOR >= 0:
    return False
  if not click(img=TEMPLATES["restore_tp"], minSearch=2,
               region=constants.GAME_SCREEN_REGION,
               text="Short of TP to start a career; opening Recover TP."):
    debug("No Restore button on the TP prompt.")
    return False
  sleep(1.5)
  row = _find(constants.TP_TOUGHNESS_ROW_ASSET)
  if not row:
    warning("No TP bottle on the restore list; not starting a career.")
    return False
  x, y, w, h = row
  held = _number(x + 90, y + 20, 100, 36)
  if held < 0:
    warning("Couldn't read how many TP bottles are left; not spending one.")
    return False
  if held <= state.TP_BOTTLE_FLOOR:
    info(f"{held} TP bottles left, at or under the floor of"
         f" {state.TP_BOTTLE_FLOOR}; not spending one to start a career.")
    return False
  info(f"Spending 1 of {held} TP bottles to start a career.")
  _click((constants.TP_RESTORE_USE_X, y + h // 2), "Using the bottle.")
  sleep(1.5)
  # The quantity dialog names the item and the holding before and after, so the
  # spend is visible in the log rather than confirmed blind.
  click(img="assets/buttons/ok_btn.png", minSearch=2,
        region=constants.GAME_SCREEN_REGION, text="Confirming the bottle.")
  sleep(2)
  click(img="assets/buttons/close_btn.png", minSearch=2,
        region=constants.GAME_SCREEN_REGION, text="Closing Recover TP.")
  sleep(1.5)
  return True

def _find(image, confidence=0.85):
  """Where `image` is on screen, or None. Its own grab: the callers that need
  this are acting on a dialog they have just opened."""
  import cv2
  import numpy as np
  screen = np.asarray(ImageGrab.grab().convert("RGB"))
  template = cv2.imread(image, cv2.IMREAD_COLOR)
  if template is None:
    return None
  result = cv2.matchTemplate(cv2.cvtColor(screen, cv2.COLOR_RGB2BGR),
                             template, cv2.TM_CCOEFF_NORMED)
  _, best, _, loc = cv2.minMaxLoc(result)
  if best < confidence:
    return None
  h, w = template.shape[:2]
  return (loc[0], loc[1], w, h)

def _number(left, top, width, height):
  from core.ocr import extract_number
  return extract_number(enhance_for_reading(
    ImageGrab.grab().crop((left, top, left + width, top + height))),
    value_range=(0, 9999))

def start():
  """Walk the setup screens and start a career.

  True once one has begun. RESUMED when there was already a career in progress,
  which is not a failure and not a new career. False means a person is needed,
  and the log says why: the walk ran out of polls, the Veteran roster is full,
  the card could not be borrowed, or `Start Career!` stayed disabled for a
  reason a borrow does not fix.
  """
  wanted = remembered_card()
  if not wanted:
    warning("No borrowed card is remembered and none is configured"
            " (career_start.borrow_card), so the Friends slot cannot be"
            " filled and a career cannot start.")
    return False
  info(f"Starting a career: last config, borrowing '{wanted}'.")
  borrows = 0
  takes = 0
  borrowed = False
  pressed_final = False
  for step in range(STEP_LIMIT):
    if state.stop_event.is_set() or not state.is_bot_running:
      return False
    screen = ImageGrab.grab()
    matches = multi_match_templates(TEMPLATES, screen=screen)

    if matches["continue_career"]:
      info("A career is already in progress; leaving it to the resume path"
           " rather than starting a new one.")
      return RESUMED

    if matches["veteran_max"]:
      error("The Veteran Umamusume roster is full (260/260), so the game will"
            " not start a career. Transfer a veteran and start the bot again;"
            " tools/veteran_scan.py reads the roster.")
      return False

    if matches["restore_tp"]:
      if not restore_tp():
        return False
      continue

    if matches["borrow_card"]:
      takes += 1
      if takes > BORROW_ATTEMPTS:
        # The row was tapped and the list is still up, so the tap is not
        # taking. Close it rather than tapping at the same row forever - an
        # unbounded press on one screen is this bot's oldest failure shape.
        warning("The Borrow Card list is still open after"
                f" {BORROW_ATTEMPTS} attempts; closing it and stopping.")
        _click(constants.BORROW_CLOSE_MOUSE_POS, "Closing the Borrow Card list.")
        return False
      if take_borrow(screen, wanted):
        borrowed = True
        sleep(2)
      else:
        _click(constants.BORROW_CLOSE_MOUSE_POS, "Closing the Borrow Card list.")
        return False
      continue

    if matches["final_confirmation"]:
      # The dialog states the price and what it leaves: "Spend 30 TP to begin
      # training?" over "TP 100 > 70". Logged rather than checked - the game
      # has already refused the press if the TP is not there, and that refusal
      # is the restore_tp branch above.
      info(f"Final Confirmation: {_confirmation_line(screen)}")
      _click(constants.FINAL_CONFIRM_START_MOUSE_POS,
             "Start Career! (Final Confirmation).")
      pressed_final = True
      sleep(6)
      continue

    if matches["support_formation"]:
      if start_button_enabled(screen):
        _click(constants.SUPPORT_FORMATION_START_MOUSE_POS,
               "Start Career! (Support Formation).")
        sleep(3)
        continue
      if borrows >= BORROW_ATTEMPTS:
        error("Start Career! is still disabled after filling the Friends slot."
              " The other cause is a support card of the same character as the"
              " trainee, which wears an orange Trainee banner with a red '!' -"
              " swap it out. Not starting a career.")
        return False
      borrows += 1
      _click(constants.SUPPORT_FRIENDS_SLOT_MOUSE_POS,
             "Opening the Friends slot to borrow.")
      sleep(2)
      continue

    # The three Next screens. Each accepts whatever the game reopened on, which
    # is what "the last config" means: the scenario, the trainee and the legacy
    # pair are all left exactly as the previous career had them.
    for key, pos, what in (
        ("scenario_select", constants.SCENARIO_SELECT_NEXT_MOUSE_POS, "scenario"),
        ("trainee_select", constants.TRAINEE_SELECT_NEXT_MOUSE_POS, "trainee"),
        ("legacy_select", constants.LEGACY_SELECT_NEXT_MOUSE_POS, "legacy")):
      if matches[key]:
        _click(pos, f"Keeping the {what} as it was; Next.")
        sleep(2.5)
        break
    else:
      # None of the setup screens. Either the home screen, where the walk
      # begins, or a frame on the way between two of them.
      #
      # Home is checked *before* the finished test, not after. A career that
      # failed to start drops back here, and "pressed_final, no setup screen,
      # so it must have worked" would then report success to career_lobby,
      # which would find the home screen and call this again - a loop between
      # two functions that each think the other is making progress. Pressing
      # CAREER instead just walks the screens again, and STEP_LIMIT bounds it.
      if _home(screen):
        _click(constants.CAREER_BUTTON_MOUSE_POS,
               "Opening Career from the home screen.")
        sleep(4)
      elif pressed_final:
        # Final Confirmation was accepted, the setup screens are gone and the
        # game is not back at Home, so the career is starting. The intro is
        # career_lobby's to drive, exactly as for one started by hand.
        career_uuid = uuid.uuid4().hex
        info(f"Career started (uuid {career_uuid}).")
        state.CAREER_UUID = career_uuid
        # Recorded whether or not this walk did the borrowing: the row is the
        # career, and the count has to include a career that started on a slot
        # somebody else had already filled.
        remember_card(wanted, career_uuid=career_uuid)
        state.CAREERS_STARTED = len(started_careers())
        return True
      else:
        debug(f"Career start: nothing recognised on step {step}; waiting.")
        sleep(1.5)

  error(f"Gave up starting a career after {STEP_LIMIT} steps. The game is"
        " parked on whatever the last step reached.")
  return False

def _home(screen):
  """The game's own home screen, where CAREER lives. The setup screens carry the
  same navigation bar, so this is only ever asked once they have been ruled
  out."""
  from core.execute import templates as lobby_templates
  found = multi_match_templates(
    {k: lobby_templates[k] for k in ("team_rank", "game_nav", "game_nav_alt")},
    screen=screen)
  return bool(found["team_rank"] or found["game_nav"] or found["game_nav_alt"])

def _confirmation_line(screen):
  left, top, width, height = constants.FINAL_CONFIRM_TP_REGION
  text = extract_text(enhance_for_reading(
    screen.crop((left, top, left + width, top + height)))).strip()
  return text or "TP line unread"
