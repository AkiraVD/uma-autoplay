"""Support card effects, read from the game's own master.mdb.

Deck picks kept being made on Friendship Bonus plus rarity, because that is
what fits on a screenshot of the detail popup - the panel scrolls and the rest
of the list never got read. Every effect is in master.mdb, so read it there.

  python tools/support_cards.py find kitasan
  python tools/support_cards.py show "Fire at My Heels" --uncaps 4
  python tools/support_cards.py show "Beyond This Shining" --level 35
  python tools/support_cards.py compare "Fire at My Heels:4" "Two Pieces:4" "Piece of Mind:4"

**The cap is the whole story; the level is not.** Levelling a card up to its
cap is cheap and gets done, but the cap only moves by pulling the same card
again from gacha. So a card is assumed to sit **at its cap**, and `--uncaps`
(the number of filled diamonds, 0-4) is the only input that matters: it sets
the cap - 30/35/40/45/50 for SSR, five less for SR, ten for R - and the level
follows from it. Effects interpolate between level breakpoints, and a Unique
Perk that unlocks at Lv40 simply does not exist on a 1-uncap copy.

`--uncaps` **defaults to 0**, deliberately. Most copies are not MLB, and a
default of 4 quietly flatters every card it is not told about - which is the
same mistake as ranking on one number. State the diamonds you actually have.

`--level` overrides that for hypotheticals ("what would this be at 50?"); it is
not how a real card should be compared. `compare "X:0" "X:4"` prices a dupe:
it shows what another pull would actually buy, including effects that do not
exist at the lower cap at all.

Read-only: opens master.mdb with mode=ro and touches nothing else.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import core.masterdb as masterdb  # noqa: E402

MDB_PATH = Path(masterdb.master_path())

# text_data categories: 75 is the full "[Title] Name", 151 the effect names
# (its `index` IS the effect `type`), 155 the Unique Perk descriptions.
CAT_CARD_NAME = 75
CAT_EFFECT_NAME = 151
CAT_PERK_NAME = 155

# The level columns and the level each one states. Values between them are
# interpolated, which is what makes a plain "last non -1" read wrong: Silence
# Suzuka's Friendship Bonus is 25 at Lv30 and 35 at Lv50, and the game shows
# 27 at Lv35 - 25 + 10 * 5/20 - not 25.
LEVEL_COLUMNS = [
  ("init", 1), ("limit_lv5", 5), ("limit_lv10", 10), ("limit_lv15", 15),
  ("limit_lv20", 20), ("limit_lv25", 25), ("limit_lv30", 30), ("limit_lv35", 35),
  ("limit_lv40", 40), ("limit_lv45", 45), ("limit_lv50", 50),
]

RARITY = {1: "R", 2: "SR", 3: "SSR"}
# support_card_data.command_id, checked against cards whose type is known.
COMMAND = {101: "Speed", 102: "Power", 103: "Guts", 105: "Stamina", 106: "Wit"}

def connect():
  if not MDB_PATH.exists():
    sys.exit(f"master.mdb not found at {MDB_PATH}. Set UMA_MASTER_MDB to point at it.")
  return sqlite3.connect(f"file:{MDB_PATH.as_posix()}?mode=ro", uri=True)

def text_map(con, category):
  return {i: t for i, t in con.execute(
    'SELECT "index", text FROM text_data WHERE category=?', (category,))}

def find_cards(con, needle):
  """Every card whose "[Title] Name" contains `needle`, case-insensitively."""
  return con.execute(
    'SELECT "index", text FROM text_data WHERE category=? AND lower(text) LIKE ? ORDER BY "index"',
    (CAT_CARD_NAME, f"%{needle.lower()}%")).fetchall()

def level_cap(con, rarity, uncaps):
  """Max level for this rarity at `uncaps` filled diamonds (0-4)."""
  row = con.execute("SELECT limit_0, limit_1, limit_2, limit_3, limit_4 "
                    "FROM support_card_limit WHERE rarity=?", (rarity,)).fetchone()
  if not row:
    return None
  return row[max(0, min(4, uncaps))]

def interpolate(points, level):
  """Effect value at `level`, linearly between breakpoints, floored.

  Returns None below the first breakpoint: an effect the card has not unlocked
  yet is absent, not zero-valued, and printing "0" for it reads as if the card
  has a bad version of the effect rather than none.
  """
  if not points:
    return None
  points = sorted(points)
  if level < points[0][0]:
    return None
  prev = points[0]
  for lv, val in points:
    if lv == level:
      return val
    if lv > level:
      span = lv - prev[0]
      if span <= 0:
        return prev[1]
      return int(prev[1] + (val - prev[1]) * (level - prev[0]) / span)
    prev = (lv, val)
  return prev[1]

def card_effects(con, card_id, level):
  """{effect type: value} for one card at one level."""
  row = con.execute("SELECT effect_table_id FROM support_card_data WHERE id=?",
                    (card_id,)).fetchone()
  if not row:
    return {}
  cols = ",".join(c for c, _ in LEVEL_COLUMNS)
  out = {}
  for record in con.execute(
      f"SELECT type,{cols} FROM support_card_effect_table WHERE id=? ORDER BY type", (row[0],)):
    kind, values = record[0], record[1:]
    points = [(lv, v) for (_, lv), v in zip(LEVEL_COLUMNS, values) if v != -1]
    value = interpolate(points, level)
    if value:
      out[kind] = value
  return out

def card_meta(con, card_id):
  row = con.execute("SELECT rarity, command_id, support_card_type, unique_effect_id "
                    "FROM support_card_data WHERE id=?", (card_id,)).fetchone()
  if not row:
    return None
  rarity, command, card_type, perk_id = row
  kind = COMMAND.get(command) or ("Pal" if card_type == 2 else f"type{card_type}")
  perk_lv = con.execute("SELECT MIN(lv) FROM support_card_unique_effect WHERE id=?",
                        (perk_id,)).fetchone()
  return {"rarity": rarity, "kind": kind, "perk_id": perk_id,
          "perk_lv": perk_lv[0] if perk_lv else None}

def resolve(con, spec, default_uncaps):
  """"Name" or "Name:uncaps" -> (card_id, display name, uncaps)."""
  needle, _, tail = spec.rpartition(":")
  if needle and tail.isdigit():
    uncaps = int(tail)
  else:
    needle, uncaps = spec, default_uncaps
  hits = find_cards(con, needle)
  if not hits:
    sys.exit(f"no support card matching {needle!r}")
  if len(hits) > 1:
    exact = [h for h in hits if needle.lower() in h[1].lower()]
    hits = exact or hits
  return hits[0][0], hits[0][1], uncaps

def describe(con, card_id, name, uncaps, level=None):
  names = text_map(con, CAT_EFFECT_NAME)
  perks = text_map(con, CAT_PERK_NAME)
  meta = card_meta(con, card_id)
  cap = level_cap(con, meta["rarity"], uncaps)
  lv = level if level else cap
  effects = card_effects(con, card_id, lv)
  return {
    "name": name, "kind": meta["kind"], "rarity": RARITY.get(meta["rarity"], "?"),
    "level": lv, "cap": cap, "uncaps": uncaps,
    "perk": perks.get(meta["perk_id"], "-"), "perk_lv": meta["perk_lv"],
    "effects": {names.get(k, f"type{k}"): v for k, v in effects.items()},
  }

def print_card(card):
  locked = card["perk_lv"] and card["level"] < card["perk_lv"]
  print(f"\n{card['name']}  [{card['rarity']} {card['kind']}]")
  print(f"  Lv {card['level']} (cap {card['cap']} at {card['uncaps']} uncap"
        f"{'' if card['uncaps'] == 1 else 's'})")
  print(f"  Perk: {card['perk']} (Lv{card['perk_lv']})"
        + ("   *** LOCKED at this level ***" if locked else ""))
  for key, value in card["effects"].items():
    print(f"    {key:<28} {value}")

def print_compare(cards):
  keys = []
  for card in cards:
    for key in card["effects"]:
      if key not in keys:
        keys.append(key)
  width = max(len(k) for k in keys) if keys else 10
  head = f"{'effect':<{width}}" + "".join(f"{c['name'].split(']')[0][1:][:16]:>18}" for c in cards)
  print("\n" + head)
  print("-" * len(head))
  print(f"{'level / cap':<{width}}" + "".join(
    f"{str(c['level']) + '/' + str(c['cap']) + ' (' + str(c['uncaps']) + 'u)':>18}" for c in cards))
  for key in keys:
    row = f"{key:<{width}}"
    best = max((c["effects"].get(key, 0) for c in cards), default=0)
    for card in cards:
      value = card["effects"].get(key)
      cell = "-" if value is None else (f"{value}*" if value == best and best else str(value))
      row += f"{cell:>18}"
    print(row)
  print(f"\n{'perk':<{width}}")
  for card in cards:
    locked = card["perk_lv"] and card["level"] < card["perk_lv"]
    print(f"  {card['name']}: {card['perk']} (Lv{card['perk_lv']})"
          + ("  [LOCKED]" if locked else ""))
  print("\n* = highest for that effect among the cards shown.")

def main():
  parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  sub = parser.add_subparsers(dest="cmd", required=True)

  p_find = sub.add_parser("find", help="list cards whose name matches")
  p_find.add_argument("needle")

  p_show = sub.add_parser("show", help="full effect list for one card, at its cap")
  p_show.add_argument("needle")
  p_show.add_argument("--uncaps", type=int, default=0,
                      help="filled diamonds 0-4; sets the cap, and the card is read at it"
                           " (default 0 - an unstated card is shown un-uncapped, not assumed MLB)")
  p_show.add_argument("--level", type=int, default=None,
                      help="hypothetical level, overriding the cap; not for real comparisons")

  p_cmp = sub.add_parser("compare", help="side-by-side at each card's cap, NAME or NAME:uncaps")
  p_cmp.add_argument("specs", nargs="+")
  p_cmp.add_argument("--uncaps", type=int, default=0,
                     help="filled diamonds for any spec without its own :uncaps (default 0)")

  args = parser.parse_args()
  con = connect()

  if args.cmd == "find":
    for card_id, name in find_cards(con, args.needle):
      meta = card_meta(con, card_id)
      if not meta:
        continue
      print(f"  {card_id:>6}  {RARITY.get(meta['rarity'],'?'):<3} {meta['kind']:<8} {name}")
    return

  if args.cmd == "show":
    card_id, name, uncaps = resolve(con, args.needle, args.uncaps)
    print_card(describe(con, card_id, name, uncaps, args.level))
    return

  cards = []
  for spec in args.specs:
    card_id, name, uncaps = resolve(con, spec, args.uncaps)
    cards.append(describe(con, card_id, name, uncaps))
  print_compare(cards)

if __name__ == "__main__":
  main()
