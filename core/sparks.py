"""The Spark Selection screen that follows a completed career.

The screen lists the sparks the career produced: one stat spark (a blue pill),
one aptitude (pink), one unique (green), and a run of skill sparks (grey), each
with one to three gold stars. Confirm keeps them; Reroll Sparks spends 30 TP to
roll a second set, after which a two-page selection screen offers either, and
the better one is kept.

The user's rule, refined over several careers:

1. A 3-star blue spark is the highest priority - blue is the stat spark.
2. With no 3-star blue, reroll. Always, however good the rest looks.
3. When neither set has a 3-star blue, take the one with the most white
   (skill) sparks.

Rerolling has no downside beyond the 30 TP: the original stays on offer.

The reader finds rows by their gold stars rather than by fixed offsets, because
the list screen and the selection screen put them 28px apart (y=169 against
y=198). A row is then named by the colour of its pill.
"""
import numpy as np
from PIL import ImageGrab

import core.state as state
import utils.constants as constants
from core.ocr import extract_text, extract_number
from utils.log import info, warning, debug
from utils.screenshot import enhanced_screenshot, enhance_for_reading
from utils.tools import sleep

# Pill colours, sampled right of the text and left of the stars.
KINDS = {
  "stat": (98, 200, 248),
  "aptitude": (255, 144, 191),
  "unique": (153, 215, 55),
  "skill": (225, 224, 225),
}
COLOUR_TOLERANCE = 40
# A filled star is gold; three of them span the band, one covers its left third.
STAR_BAND = (715, 795)
STAR_SPANS = ((0, 25, 1), (25, 55, 2))
# The rows live between the header and the buttons; the title art is gold too.
LIST_TOP, LIST_BOTTOM = 140, 780

def _rows(screen):
  """Row centres, by the gold stars every spark row carries."""
  pixels = np.asarray(screen.convert("RGB")).astype(int)
  left, right = STAR_BAND
  band = pixels[:, left:right]
  gold = (band[:, :, 0] > 200) & (band[:, :, 1] > 150) & (band[:, :, 2] < 120)
  found, start, previous = [], None, None
  for y in np.flatnonzero(gold.sum(axis=1) > 3):
    if y < LIST_TOP or y > LIST_BOTTOM:
      continue
    if start is None:
      start = y
    elif y - previous > 5:
      found.append(((start + previous) // 2, gold))
      start = y
    previous = y
  if start is not None:
    found.append(((start + previous) // 2, gold))
  return [(y, pixels, gold) for y, gold in found]

def _kind(pixels, y):
  patch = pixels[y - 8:y + 8, 640:700].reshape(-1, 3).mean(axis=0)
  for name, colour in KINDS.items():
    if all(abs(int(patch[i]) - colour[i]) <= COLOUR_TOLERANCE for i in range(3)):
      return name
  return None

def _stars(gold, y):
  columns = np.flatnonzero(gold[y - 10:y + 10].sum(axis=0) > 2)
  if not columns.size:
    return 0
  widest = int(columns.max())
  for low, high, count in STAR_SPANS:
    if low <= widest < high:
      return count
  return 3

def read(screen=None):
  """The set on screen as [{"kind", "stars"}], top row first."""
  if screen is None:
    screen = ImageGrab.grab()
  out = []
  for y, pixels, gold in _rows(screen):
    kind = _kind(pixels, y)
    if not kind:
      continue
    out.append({"kind": kind, "stars": _stars(gold, y)})
  return out

def rank(rows):
  """(stars on the stat spark, number of skill sparks) - the user's order."""
  blue = max((r["stars"] for r in rows if r["kind"] == "stat"), default=0)
  whites = sum(1 for r in rows if r["kind"] == "skill")
  return (blue, whites)

def describe(rows):
  blue, whites = rank(rows)
  return f"blue {blue}*, {whites} white spark(s), {len(rows)} rows"

def worth_rerolling(rows):
  """Rule 2: anything short of a 3-star blue is worth the 30 TP."""
  blue, _ = rank(rows)
  return blue < 3

def page_label(screen=None):
  """"Rerolled Sparks" or "Original Sparks" on the two-page selection screen."""
  text = extract_text(enhanced_screenshot(constants.SPARK_PAGE_LABEL_REGION))
  return (text or "").strip()

def valid(rows):
  """A real set: a stat spark and a handful of others. The career-rank screen
  behind this one has gold artwork that reads as a single row."""
  return len(rows) >= 3 and any(r["kind"] == "stat" for r in rows)

REROLL_BTN = "assets/ui/reroll_sparks_btn.png"
REROLL_CONFIRM_BTN = "assets/ui/reroll_confirm_btn.png"
CONFIRM_BTN = "assets/buttons/confirm_btn.png"
NEXT_BTN = "assets/buttons/next_btn.png"

def _press(img, region=None, minSearch=3, text="", confidence=0.8):
  """The spark screens swallow ordinary clicks; see execute.deliberate_click.
  Imported late because execute imports this module."""
  from core.execute import deliberate_click
  return deliberate_click(img=img, region=region, minSearch=minSearch, text=text,
                          confidence=confidence)

def handle():
  """Drive the whole spark flow, from the list screen to the kept set.

  Returns True once something was confirmed. The caller re-observes either way,
  so a step that cannot be found leaves the screen alone rather than clicking
  near Reroll, which spends TP.
  """
  rows = read()
  if not valid(rows):
    warning("On the spark screen but the sparks would not read; leaving them alone.")
    return False
  info(f"Sparks rolled: {describe(rows)}.")
  if not worth_rerolling(rows) or not state.REROLL_SPARKS:
    return _keep("as rolled")

  if not _press(REROLL_BTN, region=constants.SCREEN_BOTTOM_REGION,
                text=f"No 3-star blue spark; rerolling for 30 TP."):
    warning("Couldn't find Reroll Sparks; keeping this set.")
    return _keep("as rolled")
  if not _press(REROLL_CONFIRM_BTN, region=constants.GAME_SCREEN_REGION,
                text="Confirming the reroll."):
    # Short of TP the game asks "You need N more TP to reroll Sparks. Restore
    # TP?" instead. Career 6 sat on that dialog re-pressing Reroll every poll.
    #
    # Restoring puts the TP back and nothing else: the press that opened the
    # prompt was spent on it, so once the dialogs are closed the plain spark
    # screen is back with no reroll in flight and no confirm to find. Career 4
    # paid a bottle, read "Spending 1 of 169", and still kept a 1-star blue
    # because it looked for the confirm without asking for the reroll again.
    if not (_restore_tp()
            and _press(REROLL_BTN, region=constants.SCREEN_BOTTOM_REGION,
                       text="TP restored; asking for the reroll again.")
            and _press(REROLL_CONFIRM_BTN, region=constants.GAME_SCREEN_REGION,
                       text="Confirming the reroll.")):
      warning("The reroll confirmation never appeared; keeping this set.")
      _dismiss()
      return _keep("as rolled")
  sleep(8)
  # "Sparks Rerolled", then the notice that both sets are on offer.
  for _ in range(2):
    _press(NEXT_BTN, region=constants.GAME_SCREEN_REGION, text="Next.")
    sleep(2)
  return _choose(rows)

TOUGHNESS_ROW = "assets/ui/toughness_row.png"
# "You need N more TP to reroll Sparks. Restore TP?" - the green button on it.
# Cut tight to the label because the button body is the same green as Confirm,
# OK and Start Career!; measured worst positive 1.000 against best negative
# 0.711 over six other green-button screens, so 0.85 sits inside the gap.
RESTORE_BTN = "assets/buttons/restore_btn.png"
RESTORE_CONFIDENCE = 0.85

def _dismiss():
  """Close whatever dialog is over the spark screen, so the next poll does not
  come back to the same place and press Reroll again."""
  from core.execute import click
  for image, label in (("assets/buttons/cancel_btn.png", "Cancel"),
                       ("assets/buttons/close_btn.png", "Close")):
    if click(img=image, minSearch=1, region=constants.GAME_SCREEN_REGION,
             text=f"Closing the dialog over the sparks ({label})."):
      sleep(1)
      return True
  return False

def _restore_tp():
  """Spend one TP bottle on the "Restore TP?" dialog, if the stock allows.

  Carats are money and are never spent; the handmade chocolates are one-offs
  and are left alone. Only the plain bottle counts, and only while more than
  TP_BOTTLE_FLOOR of them remain.
  """
  if not state.TP_BOTTLE_FLOOR >= 0:
    return False
  # The prompt's buttons are "No" and "Restore" - there is no OK on it, so
  # looking for ok_btn matched nothing (0.53 against the live dialog) and this
  # returned before its first log line. That is why the whole bottle rule had
  # never once fired: three careers reached a reroll short of TP and every one
  # of them silently kept the set it had. And it has to be a deliberate press,
  # like every other button on this screen - an ordinary click is swallowed.
  if not _press(RESTORE_BTN, minSearch=2, confidence=RESTORE_CONFIDENCE,
                region=constants.GAME_SCREEN_REGION,
                text="Restoring TP so the reroll can go ahead."):
    debug("No Restore button on the TP prompt; keeping the sparks as rolled.")
    return False
  sleep(1.5)
  row = _match(TOUGHNESS_ROW)
  if not row:
    warning("No TP bottle on the restore list; keeping the sparks as rolled.")
    _dismiss()
    return False
  x, y, w, h = row
  held = extract_number(enhance_for_reading(ImageGrab.grab().crop(
    (x + 90, y + 20, x + 190, y + 56))), value_range=(0, 9999))
  if held < 0:
    warning("Couldn't read how many TP bottles are left; not spending one.")
    _dismiss()
    return False
  if held <= state.TP_BOTTLE_FLOOR:
    info(f"{held} TP bottles left, at or under the floor of {state.TP_BOTTLE_FLOOR}; not spending one.")
    _dismiss()
    return False
  info(f"Spending 1 of {held} TP bottles to afford the reroll.")
  _tap((constants.TP_RESTORE_USE_X, y + h // 2))
  sleep(1.5)
  # This one really is an OK button (the quantity dialog), but it is layered
  # over the spark screen like everything else here, so press it deliberately.
  _press("assets/buttons/ok_btn.png", minSearch=2, region=constants.GAME_SCREEN_REGION,
         text="Confirming the bottle.")
  sleep(2)
  _dismiss()
  sleep(1)
  return True

def _match(image, confidence=0.85):
  import cv2
  import numpy as np
  screen = np.asarray(ImageGrab.grab().convert("RGB"))
  template = cv2.imread(image, cv2.IMREAD_COLOR)
  if template is None:
    return None
  result = cv2.matchTemplate(cv2.cvtColor(screen, cv2.COLOR_RGB2BGR), template, cv2.TM_CCOEFF_NORMED)
  _, best, _, loc = cv2.minMaxLoc(result)
  if best < confidence:
    return None
  h, w = template.shape[:2]
  return (loc[0], loc[1], w, h)

def _choose(original):
  """Two pages, one set each: keep whichever ranks higher."""
  pages = {}
  for _ in range(2):
    label = page_label()
    rows = read()
    if valid(rows):
      pages[label] = rows
      info(f"{label or 'page'}: {describe(rows)}.")
    _tap(constants.SPARK_PAGE_NEXT_MOUSE_POS)
    sleep(1.5)
  if not pages:
    warning("Neither spark page read; confirming whatever is on screen.")
    return _keep("unread")
  best = max(pages.items(), key=lambda item: rank(item[1]))
  # The pages alternate, so step until the label matches the one wanted.
  for _ in range(3):
    if page_label() == best[0]:
      break
    _tap(constants.SPARK_PAGE_NEXT_MOUSE_POS)
    sleep(1.5)
  blue, whites = rank(best[1])
  return _keep(f"{best[0] or 'the better set'}: blue {blue}*, {whites} white spark(s)")

def _keep(why):
  if not _press(CONFIRM_BTN, region=constants.SCREEN_BOTTOM_REGION,
                text=f"Keeping the sparks ({why})."):
    warning("On the spark screen but could not find Confirm; leaving it alone"
            " rather than clicking near Reroll.")
    return False
  sleep(2)
  # "Keep this set of Sparks?" - the same Confirm, in a dialog this time.
  _press(CONFIRM_BTN, region=constants.GAME_SCREEN_REGION, text="Confirming the kept set.")
  sleep(3)
  return True

def _tap(pos):
  import utils.control as control
  if state.stop_event.is_set() or not state.is_bot_running:
    return False
  control.moveTo(pos, duration=0.2)
  sleep(0.2)
  control.click()
  return True
