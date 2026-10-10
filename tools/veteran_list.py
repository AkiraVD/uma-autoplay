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
# The game runs a profanity filter over the memo and answers anything it does
# not like with "Contains invalid characters." - which it draws OVER the memo
# dialog, so it reads as a clean close unless you look for it. "69" anywhere
# in the string trips it: V069, V69, V690 and V069X were all refused, while
# V070 went in.
#
# Breaking the pair with a separator does not work either - "V06-9", "V06 9"
# and "V06.9" were all refused, so the filter strips non-alphanumerics before
# matching. A LETTER does work: "V06X9" is accepted. So a banned label keeps
# its digits and has an X pushed in front of the last one.
#
# Only 069 and 169 are affected in a 260-card roster. The list is here rather
# than inline because the filter's full contents are the game's business and
# this is the one entry it has taught us.
BANNED_IN_MEMO = ("69",)


def memo_id(index):
  """The id for a position: V001-style, dodged around the profanity filter.

  Computed the same way whether or not memos are being written, so a
  read-only scan and a later `--write-memo` run agree on what each card is
  called.
  """
  label = ID_FORMAT.format(index)
  if any(token in label for token in BANNED_IN_MEMO):
    label = label[:-1] + "X" + label[-1]
  return label
# An id as it comes back off the card, allowing for the font: easyocr reads
# 0 as O, 5 as S, 6 as G and 7 as z in this field about half the time, so the
# shape is all that identifies it.
ID_READ = re.compile(r"^[vV][0-9A-Za-z]{3,4}$")


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
  if veteran.dismiss_error():
    warning("An error dialog was open; closed it.")
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
    card["id"] = memo_id(index)

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
        else:
          card["warnings"].append(f"the memo was not set to {card['id']}")

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


def aptitudes(args):
  """Walk the roster filling in only the aptitude grades.

  A field added after the roster was scanned does not need the whole walk
  again: this reads the header and the ten grades and leaves the skills, the
  sparks, the memos and the sheets alone, which takes about a quarter of the
  time. It refuses to write to a record whose name and rating do not match
  what is on screen, so a roster that has been re-sorted stops it rather than
  scrambling the file.

  Read from the GAME, not from the saved sheets: at JPEG quality the grades
  lose about one in ten and misread another - V120's End read B against the
  card's E - and a plausible wrong grade is worse than no grade.
  """
  if not to_roster():
    return 1
  if not veteran.ensure_ascending() and not args.any_order:
    error("The roster is not in oldest-first order; the records would not line up.")
    return 1
  data = load(OUT)
  by_index = {u["index"]: u for u in data.get("umas", [])}
  if not by_index:
    error(f"{OUT} has no records to fill in.")
    return 1

  veteran.tap(constants.VETERAN_ROSTER_FIRST_CARD_MOUSE_POS, settle=2.0)
  if not veteran.on_details():
    error("Tapping the first card did not open Umamusume Details.")
    return 1

  seen, done, skipped = None, 0, []
  for index in sorted(by_index):
    if index > 1 and not veteran.next_card(previous=seen):
      error(f"The roster stopped advancing at card {index}.")
      break
    seen = veteran.fingerprint()
    screen = veteran.grab()
    head = veteran.read_header(screen)
    record = by_index[index]
    if head["rating"] != record["rating"] or head["name"] != record["name"]:
      skipped.append(f"{record['id']} (screen says {head['name']} {head['rating']})")
      continue
    record["aptitudes"] = veteran.read_aptitudes(screen)
    blank = [k for k, v in record["aptitudes"].items() if v is None]
    record["warnings"] = [w for w in record["warnings"] if "aptitudes did not read" not in w]
    if blank:
      record["warnings"].append(f"aptitudes did not read: {', '.join(blank)}")
    done += 1
    if done % 20 == 0 or blank:
      info(f"[{index}/{max(by_index)}] {record['id']} "
           f"{' '.join(record['aptitudes'][k] or '?' for k, _, _ in constants.VETERAN_APTITUDE_SLOTS)}"
           f"{' !' + ','.join(blank) if blank else ''}")
    save(OUT, data)

  veteran.tap(constants.VETERAN_CLOSE_MOUSE_POS, settle=1.5)
  info(f"Filled in aptitudes for {done} cards.")
  if skipped:
    warning(f"{len(skipped)} record(s) did not match what was on screen: {'; '.join(skipped[:5])}")
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

  apt = sub.add_parser("aptitudes", help="fill in only the aptitude grades on an existing file")
  apt.add_argument("--any-order", action="store_true",
                   help="walk even when the roster is not oldest-first")
  apt.set_defaults(func=aptitudes)

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
