"""The race-row key: that it parses, and that it is actually unique.

Run with `python tests/test_race_row.py` from the repo root.

`core/race_row.py` replaces the 30-file picture bank with what the row prints:
track + surface + metres + fans gained. The whole design rests on that key
identifying one race per turn, so the uniqueness claim is re-derived here from
the installed master.mdb rather than trusted from a comment. A game patch that
adds a second clashing pair should fail this test, not a career.

The one known clash is Akamatsu Sho vs Begonia Sho (Junior Late Nov, both
Pre-OP, Tokyo Turf 1600m, both +1,000 fans). It is allowed by name, so it
cannot quietly grow a third member.
"""
import collections
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.masterdb as masterdb  # noqa: E402
import core.race_row as R  # noqa: E402
import utils.constants as C  # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


KNOWN_CLASH = {"Akamatsu Sho", "Begonia Sho"}

# single_mode_program.race_permission -> the years that turn-slot belongs to.
# 3 is "Classic or Senior", so it lands in both.
PERMISSION_YEARS = {1: [1], 2: [2], 3: [2, 3], 4: [3]}


def per_turn_keys():
  """{(year, month, half): {race name: key}} - what one race list can show.

  None when master.mdb is not installed, so the uniqueness check is skipped
  rather than failed on a machine without the game.
  """
  path = masterdb.local_copy()
  if not path:
    return None
  with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
    names = dict(con.execute(
      'select "index", text from text_data where category = ?', (R.RACE_NAMES,)))
    rows = con.execute("""
      select p.race_instance_id, p.race_permission, p.month, p.half
      from single_mode_program p
    """).fetchall()

  keys = R.race_keys()
  slots = collections.defaultdict(dict)
  for instance_id, permission, month, half in rows:
    name = names.get(instance_id)
    if not name or name not in keys or permission not in PERMISSION_YEARS:
      continue
    if not 1 <= month <= 12:
      continue
    for year in PERMISSION_YEARS[permission]:
      slots[(year, month, half)].setdefault(name, keys[name])
  return slots


def main():
  print("-- the key comes from somewhere")
  keys = R.race_keys()
  ok("races are keyed at all", len(keys) > 40, f"{len(keys)} races")
  ok("more than the 30 picture assets could ever reach", len(keys) > 30,
     f"{len(keys)} races")
  ok("every key is complete",
     all(k["track"] and k["surface"] and k["meters"] and k["fans"]
         for k in keys.values()),
     [n for n, k in keys.items()
      if not (k["track"] and k["surface"] and k["meters"] and k["fans"])][:3])

  print("\n-- a configured name finds its key, however it is spelled")
  derby = R.key_for("Tokyo Yushun Japanese Derby")  # the assets/races spelling
  ok("the Derby is found without its parentheses", derby is not None)
  if derby:
    ok("and it is Tokyo Turf 2400m",
       (derby["track"], derby["surface"], derby["meters"]) == ("Tokyo", "Turf", 2400),
       derby)
  ok("a race that does not exist is refused", R.key_for("Qwerty Kinen") is None)

  print("\n-- the track line parses")
  line = R.parse_track_line("Niigata Turf 1600m (Mile) Left / Outer")
  ok("track, surface and metres come out", line == {
    "track": "Niigata", "surface": "Turf", "meters": 1600}, line)
  ok("a dirt line too",
     R.parse_track_line("Sapporo Dirt 1700m (Mile) Right") == {
       "track": "Sapporo", "surface": "Dirt", "meters": 1700})
  ok("an OCR'd track name still resolves",
     (R.parse_track_line("Niiqata Turf 1600m (Mile) Left / Outer") or {}).get("track")
     == "Niigata")
  ok("a line with no racetrack in it is refused",
     R.parse_track_line("Qwerty Turf 1600m (Mile) Left") is None)
  ok("and so is a line that is not a track line",
     R.parse_track_line("+3,100 fans") is None)

  print("\n-- the fans number parses")
  ok("a comma is not a digit", R.parse_fans("+3,100 fans") == 3100)
  ok("nor is the plus", R.parse_fans("+900 fans") == 900)
  ok("a five-figure count", R.parse_fans("+15,000 fans") == 15000)
  ok("a line with no fans on it", R.parse_fans("Tokyo Turf 2400m") is None)

  print("\n-- matching is exact, because the numbers are what separate races")
  key = {"track": "Tokyo", "surface": "Turf", "meters": 2400, "fans": 20000}
  row = {"track": "Tokyo", "surface": "Turf", "meters": 2400, "fans": 20000}
  ok("the right row matches", R.row_matches(row, key))
  ok("one metre out does not", not R.row_matches({**row, "meters": 2000}, key))
  ok("a near miss on fans does not", not R.row_matches({**row, "fans": 2000}, key))
  ok("the wrong surface does not", not R.row_matches({**row, "surface": "Dirt"}, key))

  print("\n-- find_row refuses rather than guesses")
  others = [{"track": "Kyoto", "surface": "Turf", "meters": 3200, "fans": 9000}]
  ok("it finds the one row", R.find_row(others + [row], key) is row)
  ok("no match is None", R.find_row(others, key) is None)
  ok("two matching rows is None, not the first one",
     R.find_row([row, dict(row)], key, "Tokyo Yushun") is None)

  print("\n-- the two scroll anchors, which is where six races were lost")
  # 2026-09-27: the rewind dragged up from the down anchor (560,850) by +258,
  # targeting y=1108 on a 1080-tall screen. It clamps, so an up drag travelled
  # less than a down drag, the list never rewound, and every race the scan
  # found on a second screen was then "not on the screen it was read from".
  # The same mistake is written up for the skill list in utils/constants.py.
  # This is arithmetic, so it is checked as arithmetic - no game needed.
  left, top, right, bottom = C.RACE_ROW_LIST_BBOX
  down_from = C.RACE_ROW_SCROLL_DOWN_FROM_MOUSE_POS
  up_from = C.RACE_ROW_SCROLL_UP_FROM_MOUSE_POS
  ends = {
    "down start": down_from,
    "down end": (down_from[0], down_from[1] + C.RACE_ROW_SCROLL),
    "up start": up_from,
    "up end": (up_from[0], up_from[1] - C.RACE_ROW_SCROLL),
  }
  for label, (x, y) in ends.items():
    ok(f"{label} is on a 1920x1080 screen", 0 <= x < 1920 and 0 <= y < 1080, (x, y))
    ok(f"{label} is inside the list", left <= x <= right and top <= y <= bottom, (x, y))
  ok("an up drag travels exactly as far as a down drag",
     ends["down start"][1] - ends["down end"][1] == ends["up end"][1] - ends["up start"][1],
     (ends["down start"][1] - ends["down end"][1],
      ends["up end"][1] - ends["up start"][1]))
  ok("a drag is a whole number of rows",
     abs(C.RACE_ROW_SCROLL) % C.RACE_ROW_PITCH == 0, C.RACE_ROW_SCROLL)

  print("\n-- the key is unique within a turn, which is the whole design")
  slots = per_turn_keys()
  if slots is None:
    print("skip master.mdb is not installed, so uniqueness cannot be checked")
  else:
    ok("a career's worth of turn-slots was read", len(slots) > 50, len(slots))
    clashes = []
    for slot, races in sorted(slots.items()):
      seen = collections.defaultdict(list)
      for name, k in races.items():
        seen[(k["track"], k["surface"], k["meters"], k["fans"])].append(name)
      for k, group in seen.items():
        if len(group) > 1:
          clashes.append((slot, k, sorted(group)))
    unexpected = [c for c in clashes if set(c[2]) != KNOWN_CLASH]
    ok("no race list can show two rows with the same key",
       not unexpected,
       "; ".join(f"{s} {k} {g}" for s, k, g in unexpected[:4])
       or f"{len(clashes)} known clash")
    ok("the known Akamatsu/Begonia clash is still exactly two races",
       len(clashes) <= 1,
       [c[2] for c in clashes])

  print()
  if failures:
    print(f"{len(failures)} FAILED: {failures}")
    return 1
  print("all ok")
  return 0


if __name__ == "__main__":
  sys.exit(main())
