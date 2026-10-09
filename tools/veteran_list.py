"""Walk the whole Veteran Roster and write it to a file, one record per card.

  python tools/veteran_list.py scan                 # read every card
  python tools/veteran_list.py scan --write-memo    # and stamp each with its id
  python tools/veteran_list.py scan --limit 5       # a short run, to check it
  python tools/veteran_list.py scan --no-frames     # skip the contact sheets
  python tools/veteran_list.py card                 # read the card already open
  python tools/veteran_list.py nav                  # just get to the roster

The route is Enhance (bottom-left) -> Veteran Umamusume -> List. From there the
first card is opened once and the next arrow does the rest; core/veteran.py has
the whole story of why. The file is `logs/veterans.json` and it is rewritten
after **every** card, so a run that is stopped half way keeps what it read -
`--resume` picks it up from the next unread index.

`--write-memo` is the only thing here that changes anything in the game: it
puts the record's id (V001, V002, ...) in the card's memo so a row in the file
can be found again in the roster. It is off by default. The ids are positional,
so the roster is put in **oldest-first** order before the walk starts: that is
the only order where a career finishing later appends rather than renumbering
everything a memo has already been written for.

Every card also gets a **contact sheet** at `logs/veterans/<id>.jpg`: the
dialog's own header stacked above every pass of the Skills and Inspiration
panels, captioned with the id. That is the cross-check - a row in the JSON can
be argued with against the pixels it came from, without walking the roster
again - and it is why the sheet is several panels rather than one screenshot:
a long skill list is never all on screen at once. `--no-frames` turns it off.

A full 191-card roster takes something over an hour - every card is several
easyocr reads on a CPU - so it is meant to be left alone, like a career.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import core.veteran as veteran                      # noqa: E402
import utils.constants as constants                 # noqa: E402
from utils.log import info, warning, error          # noqa: E402
from utils.tools import sleep                       # noqa: E402

OUT = os.path.join(os.environ.get("UMA_LOG_DIR", "logs"), "veterans.json")
# One contact sheet per card, named for its id, beside the file it belongs to.
FRAMES = os.path.join(os.environ.get("UMA_LOG_DIR", "logs"), "veterans")
# JPEG, not PNG: a sheet is around 2,000px tall and there are 191 of them, so
# PNG would be about 150 MB of screenshots against 20.
FRAME_QUALITY = 82
CAPTION_HEIGHT = 34
FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf")
# The memo caps at 9 characters, so the id is a prefix and three digits.
ID_FORMAT = "V{:03d}"
# An id as it comes back off the card. easyocr reads the zeros as letter O
# about half the time, which is cosmetic - the shape is what identifies it.
ID_READ = re.compile(r"^[vV][0oO\d]{3}$")


def load(path):
  if not os.path.exists(path):
    return {"umas": []}
  with open(path, encoding="utf-8") as handle:
    return json.load(handle)


def save(path, data):
  os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
  # Written whole and moved into place, because this is rewritten after every
  # card and a run interrupted mid-write would otherwise lose the lot.
  temporary = path + ".tmp"
  with open(temporary, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=1, ensure_ascii=False)
  os.replace(temporary, path)


def caption_font():
  for path in FONTS:
    if os.path.exists(path):
      return ImageFont.truetype(path, 22)
  return ImageFont.load_default()


def contact_sheet(card, parts, path):
  """Stack what the card was read from into one image, captioned with its id.

  The point is that a row in the JSON can be argued with. The sheet carries
  the dialog's own header - name, rank, rating, memo, stats, aptitudes - and
  then every pass of the Skills and Inspiration panels, because a long skill
  list is never all on screen at once.

  The caption repeats the id in the picture as well as in the filename, so a
  sheet that gets copied somewhere on its own still says which card it is.
  """
  panels = [parts.get("top")] + list(parts.get("skills") or []) + list(parts.get("sparks") or [])
  panels = [panel for panel in panels if panel is not None]
  if not panels:
    return None
  width = max(panel.width for panel in panels)
  sheet = Image.new("RGB", (width, CAPTION_HEIGHT + sum(p.height for p in panels)), "white")
  draw = ImageDraw.Draw(sheet)
  draw.rectangle([0, 0, width, CAPTION_HEIGHT], fill=(40, 44, 48))
  label = (f"{card['id']}  #{card['index']}  {card['variant']} {card['name']}"
           f"  {card['rank'] or '?'}  {card['rating']}")
  draw.text((8, 6), label[:72], fill="white", font=caption_font())
  y = CAPTION_HEIGHT
  for panel in panels:
    sheet.paste(panel, ((width - panel.width) // 2, y))
    y += panel.height
  os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
  sheet.save(path, quality=FRAME_QUALITY, optimize=True)
  return path


def on_roster(tries=4):
  """Whether the roster is up, allowing for the grid fading in.

  Polled rather than read once. The footer is drawn with the grid, and a
  single read taken during the fade comes back empty - which used to send the
  walk below down the from-Home path while it was *already* on the roster,
  where its taps land on the grid and open a card.
  """
  for attempt in range(tries):
    if veteran.read_registered(veteran.grab())[0] > 0:
      return True
    sleep(0.8)
  return False


def leave_dialogs():
  """Close anything stacked over the roster, and say whether it worked."""
  if veteran.on_memo():
    warning("A memo dialog is open; cancelling out of it.")
    veteran.tap(constants.VETERAN_MEMO_CANCEL_MOUSE_POS, settle=1.0)
  for attempt in range(3):
    if not veteran.on_details():
      return True
    veteran.tap(constants.VETERAN_CLOSE_MOUSE_POS, settle=1.5 + attempt)
  return not veteran.on_details()


def to_roster():
  """Get to the Veteran Roster from wherever the game is, or return False."""
  leave_dialogs()
  if on_roster():
    return True

  # Not there, so walk in from the bottom nav. **Every step is checked before
  # the next one is pressed.** These three positions are only meaningful on
  # the screens they belong to: `(552,686)` is List on the Veteran Umamusume
  # menu and a card in the fourth row of the roster grid, so pressing it
  # blindly is how an aborted run left a card open instead of recovering.
  steps = ((constants.VETERAN_HOME_ENHANCE_MOUSE_POS, constants.VETERAN_ENHANCE_MENU_MOUSE_POS,
            "veteran"),
           (constants.VETERAN_ENHANCE_MENU_MOUSE_POS, constants.VETERAN_LIST_MOUSE_POS, "list"))
  for press, next_button, expected in steps:
    for attempt in range(3):
      veteran.tap(press, settle=2.0)
      if expected in veteran.label_near(veteran.grab(), next_button):
        break
    else:
      error(f"After pressing {press}, the screen never showed {expected!r}."
            " Is the game on the Home screen?")
      return False
  veteran.tap(constants.VETERAN_LIST_MOUSE_POS, settle=2.5)
  if not on_roster():
    error("Could not reach the Veteran Roster.")
    return False
  registered, capacity = veteran.read_registered(veteran.grab())
  info(f"Veteran Roster: {registered}/{capacity} registered.")
  return True


def scan(args):
  if not to_roster():
    return 1
  if not veteran.ensure_ascending() and not args.any_order:
    error("The roster is not in oldest-first order, so the ids would not be"
          " stable. Fix the sort on screen, or pass --any-order to scan anyway.")
    return 1

  screen = veteran.grab()
  registered, capacity = veteran.read_registered(screen)
  key, order = veteran.read_sort(screen)
  total = min(registered, args.limit) if args.limit else registered

  data = load(OUT) if args.resume else {"umas": []}
  done = {record["index"]: record for record in data.get("umas", [])}
  data = {
    "scanned_at": datetime.now().isoformat(timespec="seconds"),
    "sort": f"{key} {order}",
    "registered": registered,
    "capacity": capacity,
    "umas": [done[i] for i in sorted(done)],
  }

  veteran.tap(constants.VETERAN_ROSTER_FIRST_CARD_MOUSE_POS, settle=2.0)
  if not veteran.on_details():
    error("Tapping the first card did not open Umamusume Details.")
    return 1

  started = time.time()
  first = None
  seen = None                    # the fingerprint of the card last read
  for index in range(1, total + 1):
    if index > 1 and not veteran.next_card(previous=seen):
      error(f"The roster stopped advancing at card {index}; stopping with"
            f" {len(data['umas'])} read. Re-run with --resume to carry on.")
      break
    seen = veteran.fingerprint()
    if index in done:
      continue

    parts = None if args.no_frames else {}
    card = veteran.read_card(keep=parts)
    card["index"] = index
    card["id"] = ID_FORMAT.format(index)

    # A card that already carries an id is the cross-check on the order. The
    # same id means a previous run put it there and the positions still line
    # up; a different one means the roster has been re-sorted or a veteran was
    # transferred out, and every memo from here on is now on the wrong card.
    if ID_READ.match(card["memo"] or ""):
      if veteran.same_memo(card["memo"], card["id"]):
        card["memo"] = card["id"]
      else:
        card["warnings"].append(f"card carries memo {card['memo']!r}, not {card['id']}"
                                " - the roster order has changed since it was written")

    # The arrow wraps, so landing back on the first card means the roster is
    # shorter than its footer claimed - worth saying rather than looping.
    signature = (card["name"], card["rating"])
    if index == 1:
      first = signature
    elif signature == first:
      warning(f"Card {index} reads the same as card 1; the list has wrapped."
              " Stopping here rather than reading it twice.")
      break

    if args.write_memo:
      # Already stamped - by an earlier run, or by this one if it is being
      # resumed - so the dialog is not opened at all.
      if veteran.same_memo(card["memo"], card["id"]):
        card["memo"], card["memo_written"] = card["id"], True
      else:
        card["memo_written"] = veteran.write_memo(card["id"])
        if card["memo_written"]:
          card["memo"] = card["id"]

    if parts is not None:
      # After the memo, so a sheet from a --write-memo run shows the id the
      # game is now carrying rather than the dash it had a moment earlier.
      if args.write_memo:
        parts["top"] = veteran.grab().crop(constants.VETERAN_DIALOG_TOP_BBOX)
      sheet = contact_sheet(card, parts, os.path.join(FRAMES, card["id"] + ".jpg"))
      if sheet:
        card["frame"] = os.path.relpath(sheet, os.path.dirname(OUT) or ".")

    data["umas"].append(card)
    data["scanned_at"] = datetime.now().isoformat(timespec="seconds")
    save(OUT, data)

    per = (time.time() - started) / max(1, len(data["umas"]))
    left = int(per * (total - index) / 60)
    info(f"[{index}/{total}] {card['id']} {card['variant']} {card['name']}"
         f" {card['rank']} {card['rating']} "
         f"{len(card['skills'])} skills, {len(card['sparks'])} sparks"
         f"{' !' + '; '.join(card['warnings']) if card['warnings'] else ''}"
         f"  (~{left} min left)")

  veteran.tap(constants.VETERAN_CLOSE_MOUSE_POS, settle=1.5)
  if veteran.on_details():
    # Worth one more go rather than leaving the game on a dialog: the close
    # tap is the one press here with nothing after it to notice it failed.
    veteran.tap(constants.VETERAN_CLOSE_MOUSE_POS, settle=2.0)
  flagged = [c for c in data["umas"] if c.get("warnings")]
  info(f"Wrote {len(data['umas'])} veterans to {OUT}; {len(flagged)} with warnings.")
  if not args.no_frames:
    info(f"Contact sheets, one per card, are in {FRAMES}/.")
  return 0


def card(args):
  """Read whatever card is already open, without stepping or writing."""
  if not veteran.on_details():
    error("No Umamusume Details dialog on screen.")
    return 1
  print(json.dumps(veteran.read_card(), indent=1, ensure_ascii=False))
  return 0


def main():
  parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = parser.add_subparsers(dest="what")

  run = sub.add_parser("scan", help="read the whole roster into logs/veterans.json")
  run.add_argument("--write-memo", action="store_true",
                   help="also stamp each card's memo with its id (changes the game)")
  run.add_argument("--limit", type=int, default=0, help="stop after this many cards")
  run.add_argument("--resume", action="store_true",
                   help="keep what is already in the file and read only what is missing")
  run.add_argument("--any-order", action="store_true",
                   help="scan even when the roster is not oldest-first")
  run.add_argument("--no-frames", action="store_true",
                   help=f"skip the per-card contact sheets in {FRAMES}/")
  run.set_defaults(func=scan)

  sub.add_parser("card", help="read the card already on screen").set_defaults(func=card)
  sub.add_parser("nav", help="get to the roster and stop").set_defaults(
    func=lambda args: 0 if to_roster() else 1)

  args = parser.parse_args()
  if not getattr(args, "func", None):
    parser.print_help()
    return 0
  return args.func(args)


if __name__ == "__main__":
  sys.exit(main())
