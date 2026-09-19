"""Read Trackblazer's Climax Store shelf, and buy from it.

`core/shop_choice.py` already decides *what* to buy from a list of rows; this
is the half that reads rows off the screen and clicks. The scrolling itself is
`core/menu_scan.py`'s SHOP_BUY profile, so only the shop-specific reading of a
row lives here.

Two things measured on 2026-09-19 shape this module:

**A row is anchored on its "Cost" label, not its checkbox.** Ticking a row
turns its checkbox green, so a checkbox template fails on exactly the row just
selected - the one a buying pass most needs to find again.

**A row whose name does not read is clipped, not unknown.** The row scrolled
under the panel header keeps its Cost label on screen while its name is cut
off, so it reads as an empty string. That is the failure menu_scan's
`advance_one_screen` exists to survive: the row is seen again, lower down, on
the next pass. It must be reported as clipped rather than as a catalogue miss,
or a perfectly good item looks like a gap in `data/trackblazer_shop.json`.

The purchase itself is four screens deep and three different green buttons
share one position, so every step is confirmed by reading the dialog's title
bar. See docs/screen-map.md.
"""
import re

from PIL import Image

import core.menu_scan as menu_scan
import core.shop_choice as shop_choice
import core.state as state
import core.trackblazer as trackblazer
import utils.constants as constants
import utils.control as control
from core.ocr import extract_text
from utils.log import debug, info, warning
from utils.screenshot import capture_region
from utils.tools import sleep

LIST = menu_scan.SHOP_BUY

# Titles of the three dialogs the purchase walks through, in order. Matched
# loosely because the title bar OCRs with the odd dropped letter.
CONFIRM_EXCHANGE = "confirm exchange"
EXCHANGE_COMPLETE = "exchange complete"
CONFIRM_USE = "confirm use"


def _region(region, screen=None):
  """One region as an image, off a pre-grabbed screen or the live display.

  Readers take an optional `screen` the way `multi_match_templates` does, so
  they can be pointed at a saved frame. Without it this reader could only ever
  be exercised against the live game and the frames in
  `tests/fixtures/trackblazer/shop/` would be untestable.
  """
  left, top, w, h = region
  if screen is None:
    return capture_region(region)
  return screen.crop((left, top, left + w, top + h))


def _read(offset, box, screen=None):
  """OCR one field of a row, given the row's anchor box."""
  ax, ay = box[0], box[1]
  dx, dy, w, h = offset
  crop = _region((ax + dx, ay + dy, w, h), screen)
  return extract_text(crop.resize((w * 3, h * 3), Image.LANCZOS)).strip()


def read_cost(text):
  """The coins a row will actually charge, or None.

  **The last number wins.** During a sale the row prints the old price struck
  through beside the new one - "Cost 55 > 44" - and the new one is what is
  deducted. Reading the first number would overpay the plan by the discount
  and, worse, make an affordable basket look unaffordable.
  """
  numbers = re.findall(r"\d+", text or "")
  if not numbers:
    return None
  value = int(numbers[-1])
  return value if 0 < value <= 999 else None


def read_row(box, screen=None):
  """One shelf row as {"name", "cost", "effect"}, or None if it will not read.

  Returns None for a clipped row rather than a half-filled dict, so a caller
  never plans against a name it could not see.
  """
  name = _read(constants.SHOP_NAME_OFFSET, box, screen)
  cost = read_cost(_read(constants.SHOP_COST_OFFSET, box, screen))
  if not name:
    debug(f"Shelf row at y={box[1]} has no readable name; it is clipped by the"
          " panel header and will be read again on a later pass.")
    return None
  if cost is None:
    debug(f"Shelf row {name!r} at y={box[1]} has no readable cost, skipped.")
    return None
  return {"name": name, "cost": cost,
          "effect": _read(constants.SHOP_EFFECT_OFFSET, box, screen)}


def read_coins(screen=None):
  """The Shop Coins balance, or None."""
  crop = _region(constants.SHOP_COINS_REGION, screen)
  text = extract_text(crop.resize((crop.width * 4, crop.height * 4),
                                  Image.LANCZOS))
  numbers = re.findall(r"\d+", text or "")
  return int(numbers[-1]) if numbers else None


def read_shelf():
  """Every distinct row on the shelf, in shelf order.

  Rows are yielded once per pass and the passes overlap deliberately, so the
  same row arrives several times at different heights. They are keyed by
  (name, cost): the shelf can legitimately hold two identical rows - two Guts
  Manuals were on it at once - so position cannot be the key, and neither can
  the name alone.
  """
  seen, rows = set(), []
  for box in menu_scan.rows(LIST):
    if state.stop_event.is_set():
      return rows
    row = read_row(box)
    if row is None:
      continue
    key = (row["name"], row["cost"])
    if key in seen:
      continue
    seen.add(key)
    rows.append(row)
  return rows


def dialog_title():
  """The title bar of whatever dialog is up, lowercased."""
  crop = capture_region(constants.SHOP_DIALOG_TITLE_REGION)
  return extract_text(crop.resize((crop.width * 2, crop.height * 2),
                                  Image.LANCZOS)).strip().lower()


def _expect(want, tries=6):
  """Wait for a dialog whose title contains `want`. False if it never comes."""
  for _ in range(tries):
    if state.stop_event.is_set():
      return False
    title = dialog_title()
    if want in title:
      return True
    debug(f"Waiting for the {want!r} dialog; the title bar reads {title!r}.")
    sleep(1)
  return False


def tick(box):
  """Tick one row's checkbox, given its anchor box."""
  dx, dy = constants.SHOP_CHECKBOX_OFFSET
  control.click(box[0] + dx, box[1] + dy)
  sleep(0.6)


def buy(wanted, use_now=()):
  """Tick `wanted` rows and exchange them. Returns the names actually ticked.

  `wanted` is a list of rows from `shop_choice.plan`, matched against a fresh
  scan by (name, cost) - never by a position from an earlier pass, because
  scrolling moves every box.

  `use_now` names the items to spend immediately; everything else is stored.
  The game agrees with storing by default - the quantity stepper starts at 0
  with Confirm Use dimmed - so only the flat stat items, which have no timing
  to get wrong, are worth using on purchase.
  """
  targets = {(r["name"], r["cost"]) for r in (wanted or [])}
  if not targets:
    return []

  ticked = []
  for box in menu_scan.rows(LIST):
    if state.stop_event.is_set():
      return ticked
    row = read_row(box)
    if row is None:
      continue
    key = (row["name"], row["cost"])
    if key in targets:
      before = read_coins()
      tick(box)
      after = read_coins()
      # Ticking deducts the cost immediately, before any commit, so the coin
      # counter is a free confirmation that the right row was hit.
      if before is not None and after is not None and before - after != row["cost"]:
        warning(f"TB-SHOP-TICK: {row['name']} costs {row['cost']} but the coin"
                f" counter went {before} -> {after}; leaving it and moving on.")
        continue
      targets.discard(key)
      ticked.append(row)
      info(f"Shop: ticked {row['name']} for {row['cost']} coins.")
    if not targets:
      break

  if not ticked:
    return []

  control.click(*constants.SHOP_CONFIRM_MOUSE_POS)
  sleep(1.5)
  if not _expect(CONFIRM_EXCHANGE):
    warning("TB-SHOP-BUY: Confirm did not raise Confirm Exchange, backing out.")
    return []
  control.click(*constants.SHOP_DIALOG_GREEN_MOUSE_POS)
  sleep(2)
  if not _expect(EXCHANGE_COMPLETE):
    warning("TB-SHOP-BUY: Exchange did not complete; the basket may be unspent.")
    return ticked

  names = {r["name"] for r in ticked}
  if any(n in names for n in (use_now or ())):
    control.click(*constants.SHOP_QTY_PLUS_MOUSE_POS)
    sleep(0.5)
    control.click(*constants.SHOP_DIALOG_GREEN_MOUSE_POS)
    sleep(1.5)
    if _expect(CONFIRM_USE):
      control.click(*constants.SHOP_DIALOG_GREEN_MOUSE_POS)
      sleep(2)
  else:
    # Quantity stays 0 and Close stores the lot for the turn that wants it.
    control.click(*constants.SHOP_DIALOG_CANCEL_MOUSE_POS)
    sleep(1.5)
  return ticked


# One shop visit per turn at most. The shelf scan is several passes of OCR, so
# re-reading it on a turn already walked would cost a lot for nothing: the
# lineup only changes on the game's own restock windows.
_visited = {"turn": None}


def reset():
  """Forget the visit ledger. Called when a new career starts."""
  _visited["turn"] = None


def should_visit(turn):
  """True if this turn has not already had its shelf read."""
  return turn is not None and _visited["turn"] != turn


def note_visit(turn):
  _visited["turn"] = turn


def open_shop(box=None):
  """Open the shop from the lobby. True if the shelf came up.

  Takes the matched button box rather than trusting the position: the shop
  button only exists after the debut race and a race day replaces the whole
  facility row, so a bare click at SHOP_BUTTON_MOUSE_POS could land on
  anything. The position is only the fallback for a matched-but-boxless call.
  """
  if box is not None and len(box) >= 2:
    control.click(int(box[0]), int(box[1]))
  else:
    control.click(*constants.SHOP_BUTTON_MOUSE_POS)
  sleep(2)
  for _ in range(4):
    if state.stop_event.is_set():
      return False
    if read_coins() is not None:
      return True
    sleep(1)
  warning("TB-SHOP-OPEN: the shop did not come up, leaving it for this turn.")
  return False


def leave():
  """Back out of the shop to the lobby."""
  control.click(*constants.SHOP_BACK_MOUSE_POS)
  sleep(1.5)


def cheapest_cost():
  """The cheapest thing the catalogue sells, or 0 if it will not load."""
  costs = [e.get("cost", 0) for e in trackblazer.catalogue() if e.get("cost")]
  return min(costs) if costs else 0


def visit(headroom=None):
  """Read the shelf, decide, buy. Assumes the shop screen is already open."""
  coins = read_coins()
  if coins is None:
    warning("TB-SHOP-COINS: the Shop Coins balance did not read, skipping.")
    return []
  # Bail before the scan, not after. Reading the shelf is several passes of
  # OCR and there is no point paying for it with nothing affordable on the
  # other side - early careers sit on single-digit coins for a long while.
  floor = cheapest_cost()
  if floor and coins < floor:
    debug(f"Shop: {coins} coins, under the cheapest item at {floor}, not reading"
          " the shelf.")
    return []
  rows = read_shelf()
  if not rows:
    debug("Shop: no rows read off the shelf.")
    return []
  for line in shop_choice.explain(rows, coins, headroom):
    debug(f"Shop: {line}")
  wanted = shop_choice.plan(rows, coins, headroom)
  if not wanted:
    info(f"Shop: {len(rows)} row(s), {coins} coins, nothing worth buying.")
    return []
  info(f"Shop: {coins} coins, buying "
       + ", ".join(f"{r['name']} ({r['cost']})" for r in wanted))
  use_now = tuple(r["name"] for r in wanted
                  if (trackblazer.item(r["name"]) or {}).get("category") == "stat")
  return buy(wanted, use_now=use_now)
