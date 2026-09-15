"""Read the Veteran Roster and decide which veterans are transferable.

The roster holds 260 finished careers and the game can only filter attribute
sparks, so "rank A or below with no 3-star spark of any kind" has to be worked
out by opening each candidate. This reads the grid, opens the ones that qualify
on rank, reads their own Sparks section (not the Legacy Origin sparks below it)
and writes the verdicts to a file for review.

  python tools/veteran_scan.py probe        # classify what is on screen
  python tools/veteran_scan.py drag 4       # scroll down four rows, no taps
  python tools/veteran_scan.py card 2 3     # open one card and read its sparks
  python tools/veteran_scan.py scan         # the whole roster -> shots/veterans.json

Nothing here taps Transfer or any confirmation: it only reads.
"""
import json
import os
import sys
import time

import cv2
import numpy as np
from PIL import ImageGrab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from core.ocr import extract_number                    # noqa: E402
from utils.screenshot import enhance_for_reading       # noqa: E402
import utils.control as control                        # noqa: E402


# Grid geometry, measured on the 1920x1080 Steam window.
COLUMNS = [327, 439, 551, 663, 775]
RATING_YS = [215, 347, 479, 611, 743]      # five fully visible rows
ROW_PITCH = 132
CARD_ABOVE_RATING = 65                     # card centre, from its rating text
BADGE_DX, BADGE_DY, BADGE_SIZE = 8, -117, 48
RANKS = {
  "A": "assets/roster/rank_a.png",
  "B+": "assets/roster/rank_bplus.png",
  "A+": "assets/roster/rank_aplus.png",
}
RANK_MATCH = 0.80
# Ranks that qualify for transfer, by the user's rule (A and below).
TRANSFERABLE = {"A", "B+", "B", "C", "C+", "D", "E", "F", "G"}

DETAILS_INSPIRATION = (552, 467)
DETAILS_CLOSE = (552, 997)
LEGACY_HEADER = "assets/roster/legacy_origin.png"
SPARK_BAND = (300, 840)                    # x range of the spark pills
STAR_GOLD = lambda a: (a[:, :, 0] > 200) & (a[:, :, 1] > 150) & (a[:, :, 2] < 120)

def grab():
  return ImageGrab.grab()

def match(template, screen=None, region=None, confidence=RANK_MATCH):
  """Best hit for a template, as (x, y, w, h) in screen coordinates."""
  image = np.asarray((screen or grab()).convert("RGB"))
  if region:
    left, top, right, bottom = region
    image = image[top:bottom, left:right]
  tpl = cv2.imread(template, cv2.IMREAD_COLOR)
  if tpl is None:
    return None
  result = cv2.matchTemplate(cv2.cvtColor(image, cv2.COLOR_RGB2BGR), tpl, cv2.TM_CCOEFF_NORMED)
  _, best, _, loc = cv2.minMaxLoc(result)
  if best < confidence:
    return None
  h, w = tpl.shape[:2]
  x, y = loc
  if region:
    x, y = x + region[0], y + region[1]
  return (x, y, w, h)

def visible_rows(screen):
  """Where the rows actually sit: a drag leaves the grid a few pixels off, so
  the rank badges (the only strong orange in the grid) give the phase."""
  image = cv2.cvtColor(np.asarray(screen.convert("RGB")), cv2.COLOR_RGB2BGR)
  tops = []
  for path in RANKS.values():
    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
    if tpl is None:
      continue
    result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= 0.62)
    tops.extend(int(y) for y, x in zip(ys, xs) if 80 <= y <= 860 and COLUMNS[0] <= x <= COLUMNS[-1] + 60)
  if not tops:
    return list(RATING_YS)
  tops.sort()
  rows, group = [], [tops[0]]
  for y in tops[1:]:
    if y - group[-1] > 40:                 # rows are 132px apart, badges ~48 tall
      rows.append(sum(group) // len(group))
      group = []
    group.append(y)
  rows.append(sum(group) // len(group))
  # badge top -> rating text, and only rows whose rating is still on screen
  return [y - BADGE_DY for y in rows if y - BADGE_DY < 800]

def read_grid(screen=None, rows=None):
  """The visible cards as [{row, col, rating, rank}], top-left first."""
  screen = screen or grab()
  cards = []
  for row, rating_y in enumerate(rows if rows is not None else visible_rows(screen)):
    for col, cx in enumerate(COLUMNS):
      rating = read_rating(screen, cx, rating_y)
      badge = screen.crop((cx + BADGE_DX, rating_y + BADGE_DY,
                           cx + BADGE_DX + BADGE_SIZE, rating_y + BADGE_DY + BADGE_SIZE))
      rank, score = None, 0
      for name, path in RANKS.items():
        tpl = cv2.imread(path, cv2.IMREAD_COLOR)
        if tpl is None:
          continue
        result = cv2.matchTemplate(
          cv2.cvtColor(np.asarray(badge.convert("RGB")), cv2.COLOR_RGB2BGR), tpl, cv2.TM_CCOEFF_NORMED)
        _, best, _, _ = cv2.minMaxLoc(result)
        if best > score:
          rank, score = name, best
      # Argmax over the badges rather than a hard threshold: the card art shows
      # through the badge's edges, so an A on a bright card scores 0.65 while
      # the same badge on a dark one scores 0.95. Anything genuinely unclear is
      # left as "unknown" and opened individually rather than guessed at.
      cards.append({"row": row, "col": col, "rating": rating,
                    "rank": rank if score >= 0.60 else "unknown", "score": round(float(score), 3)})
  return cards

def read_rating(screen, cx, rating_y):
  """The rating under a card. It carries a comma, so the digits are pulled out
  of the text rather than read as a number."""
  from core.ocr import extract_text
  crop = screen.crop((cx - 54, rating_y - 17, cx + 54, rating_y + 17))
  digits = "".join(ch for ch in (extract_text(enhance_for_reading(crop)) or "") if ch.isdigit())
  return int(digits) if digits else -1

def card_point(row, col):
  return (COLUMNS[col], RATING_YS[row] - CARD_ABOVE_RATING)

def tap(point, wait=1.2):
  control.moveTo(point, duration=0.15)
  time.sleep(0.1)
  control.click()
  time.sleep(wait)

def drag(rows):
  """Scroll the grid by whole rows.

  The scrollbar gutter only drags while the thumb is under the cursor, so this
  drags the grid itself - and the release sometimes still reads as a tap and
  opens a card, which is why it closes any dialog afterwards.
  """
  # One gesture can only travel as far as the window, so long scrolls repeat.
  step = 4 if rows > 0 else -4
  while abs(rows) > 4:
    drag(step)
    rows -= step
  distance = int(ROW_PITCH * rows)
  start = (552, 430 + (200 if distance < 0 else 0))
  control.moveTo(start, duration=0.15)
  control.mouseDown()
  steps = max(10, abs(distance) // 15)
  for i in range(1, steps + 1):
    control.moveTo(start[0], start[1] - int(distance * i / steps), duration=0.015)
  # A short pause at the end stops the release being read as a flick.
  time.sleep(0.35)
  control.mouseUp()
  time.sleep(1.0)
  close_dialog_if_open()

def close_dialog_if_open():
  """A stray tap opens Umamusume Details over the grid; shut it."""
  screen = grab()
  if len(visible_rows(screen)) >= 3:
    return False
  tap(DETAILS_CLOSE, wait=1.0)
  return True

def own_spark_stars(screen=None):
  """Highest star count among the Uma's own sparks, or -1 if unreadable.

  The dialog lists the Uma's sparks first and its Legacy Origin's below, so the
  header is the boundary: anything under it belongs to the ancestor.
  """
  screen = screen or grab()
  legacy = match(LEGACY_HEADER, screen=screen, confidence=0.75)
  top = 520
  bottom = legacy[1] if legacy else 700
  if bottom <= top:
    return -1
  image = np.asarray(screen.convert("RGB")).astype(int)
  best = 0
  # Each row holds two pills side by side; counted together, a row of two
  # 2-star sparks reads as four stars, so the columns are counted apart.
  for left, right in ((365, 600), (600, 840)):
    band = image[top:bottom, left:right]
    gold = STAR_GOLD(band)
    rows, start, previous = [], None, None
    for y in np.flatnonzero(gold.sum(axis=1) > 2):
      if start is None:
        start = y
      elif y - previous > 4:
        rows.append((start, previous))
        start = y
      previous = y
    if start is not None:
      rows.append((start, previous))
    for y0, y1 in rows:
      columns = np.flatnonzero(gold[y0:y1 + 1].sum(axis=0) > 1)
      if not columns.size:
        continue
      groups, last = 1, columns[0]
      for x in columns[1:]:
        if x - last > 6:
          groups += 1
        last = x
      best = max(best, min(groups, 3))
  return best

def rank_in_dialog(screen):
  """The rank badge beside the portrait in Umamusume Details, so a card whose
  grid badge would not read is still classified from its own page."""
  best, name = 0, None
  for rank, path in RANKS.items():
    hit = match(path, screen=screen, region=(400, 90, 530, 200), confidence=0.55)
    if not hit:
      continue
    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
    crop = np.asarray(screen.convert("RGB"))[hit[1]:hit[1] + hit[3], hit[0]:hit[0] + hit[2]]
    score = cv2.matchTemplate(cv2.cvtColor(crop, cv2.COLOR_RGB2BGR), tpl, cv2.TM_CCOEFF_NORMED).max()
    if score > best:
      best, name = score, rank
  return name if best >= 0.55 else None

def main():
  what = sys.argv[1] if len(sys.argv) > 1 else "probe"
  if what == "probe":
    for card in read_grid():
      print(f"r{card['row']}c{card['col']} {card['rating']:>6} {card['rank']:>6} ({card['score']})")
  elif what == "drag":
    before = read_grid()[0]["rating"]
    drag(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
    after = read_grid()[0]["rating"]
    print(f"top rating {before} -> {after}")
  elif what == "sweep":
    # Sorted by rating ascending, every transferable rank sits before the first
    # A+, so the sweep stops there rather than reading all 260.
    drag(-40)                                # back to the top
    time.sleep(1)
    seen, order, stop = {}, [], False
    for _ in range(40):
      rows = visible_rows(grab())
      cards = read_grid(rows=rows)
      for card in cards:
        if card["rating"] <= 0:
          continue
        if card["rank"] in ("A+", "higher"):
          stop = True
        key = card["rating"]
        if key not in seen:
          seen[key] = card["rank"]
          order.append(key)
      if stop:
        break
      drag(len(rows) - 1)
    candidates = [r for r in order if seen[r] in TRANSFERABLE]
    unknown = [r for r in order if seen[r] == "unknown"]
    out = {"by_rating": seen, "order": order, "candidates": candidates, "unknown": unknown}
    with open("shots/veterans_scan.json", "w", encoding="utf-8") as f:
      json.dump(out, f, indent=1)
    print(f"read {len(order)} cards up to the first A+")
    print(f"transferable by rank: {len(candidates)} (ratings {candidates[0] if candidates else '-'}"
          f" to {candidates[-1] if candidates else '-'})")
    print(f"unclear badges: {len(unknown)} {unknown[:10]}")
  elif what == "check":
    # Open every card that qualifies on rank and read its own sparks. Saved as
    # it goes, so a stall does not lose the work already done.
    path = "shots/veterans_check.json"
    results = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    drag(-60)
    done = False
    for screen_no in range(45):
      rows = visible_rows(grab())
      cards = read_grid(rows=rows)
      for card in cards:
        rating, rank = card["rating"], card["rank"]
        if rating <= 0:
          continue
        if rank in ("A+", "higher"):
          done = True
          continue
        if str(rating) in results:
          continue
        tap(card_point(card["row"], card["col"]))
        tap(DETAILS_INSPIRATION, wait=0.9)
        shot = grab()
        stars = own_spark_stars(shot)
        shown = rank_in_dialog(shot) or rank
        tap(DETAILS_CLOSE, wait=0.7)
        results[str(rating)] = {"rank": shown, "stars": stars, "grid_rank": rank}
        with open(path, "w", encoding="utf-8") as f:
          json.dump(results, f, indent=1)
        print(f"{rating:>6} {shown:>7} max stars {stars}"
              f" -> {'KEEP' if stars >= 3 or shown not in TRANSFERABLE else 'transfer'}")
      if done:
        break
      drag(len(rows) - 1)
    transfer = [int(r) for r, v in results.items() if v["stars"] < 3 and v["rank"] in TRANSFERABLE]
    keep = [int(r) for r, v in results.items() if v["stars"] >= 3]
    print(f"\nchecked {len(results)}: {len(transfer)} to transfer, {len(keep)} spared for a 3-star spark")
  elif what == "find":
    wanted = int(sys.argv[2])
    drag(-60)
    for _ in range(45):
      rows = visible_rows(grab())
      for card in read_grid(rows=rows):
        if card["rating"] == wanted:
          tap(card_point(card["row"], card["col"]))
          tap(DETAILS_INSPIRATION, wait=0.9)
          shot = grab()
          shot.save(f"shots/gl/veteran_{wanted}.png")
          print(f"{wanted}: rank {rank_in_dialog(shot)}, max own stars {own_spark_stars(shot)}")
          tap(DETAILS_CLOSE, wait=0.7)
          return
      drag(len(rows) - 1)
    print(f"{wanted} not found")
  elif what == "card":
    row, col = int(sys.argv[2]), int(sys.argv[3])
    tap(card_point(row, col))
    tap(DETAILS_INSPIRATION, wait=1.0)
    shot = grab()
    shot.save("shots/gl/veteran_card.png")
    print("max own spark stars:", own_spark_stars(shot))
    tap(DETAILS_CLOSE, wait=0.8)
  else:
    print(__doc__)

if __name__ == "__main__":
  main()
