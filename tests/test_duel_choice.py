"""Reading Happy Meek's Challenge and picking a contest.

Run with `python tests/test_duel_choice.py` from the repo root.

The fixture names carry the answer: `choice_4_dtc.png` is the fifth duel
captured, and its three rows were rated `d` (ringed dot), `t` (triangle) and
`c` (hollow ring) top to bottom. So the reader is checked against ground truth
written down at capture time rather than against itself.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

from PIL import Image  # noqa: E402

import core.duel as D  # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "duel")
failures = []


def ok(label, condition, detail=""):
  print(("ok   " if condition else "FAIL ") + label + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def fixture(name, where=FIXTURES):
  return Image.open(os.path.join(where, name))


def duel_fixtures():
  return sorted(f for f in os.listdir(FIXTURES) if f.startswith("choice_"))


def row(category=None, glyph=None):
  return {"y": 0, "category": category, "glyph": glyph}


def test_every_glyph_reads_as_captured():
  print("\n-- test_every_glyph_reads_as_captured")
  for name in duel_fixtures():
    want = name.split("_")[2].split(".")[0]
    rows = D.read_board(fixture(name))
    got = "".join(r["glyph"] or "?" for r in rows)
    ok(f"{name} reads {want}", got == want, f"got {got}")


def test_every_row_names_its_contest():
  print("\n-- test_every_row_names_its_contest")
  for name in duel_fixtures():
    rows = D.read_board(fixture(name))
    named = [r["category"] for r in rows]
    ok(f"{name} names all three contests",
       len(named) == 3 and all(named), f"got {named}")


def test_option_one_is_always_a_stat():
  """The duel always offers the trained facility's own stat first, so Energy
  can never be option 1 - which is the whole reason it is the scarcer target."""
  print("\n-- test_option_one_is_always_a_stat")
  for name in duel_fixtures():
    rows = D.read_board(fixture(name))
    ok(f"{name} does not lead with Energy",
       rows and rows[0]["category"] != "energy", f"got {rows[0]['category'] if rows else None}")


def test_a_normal_event_is_not_a_duel():
  print("\n-- test_a_normal_event_is_not_a_duel")
  for name in ("two_options_simple.png", "two_options_branched.png", "event_no_panel.png"):
    path = os.path.join("tests", "fixtures", "choices", name)
    if not os.path.exists(path):
      continue
    rows = D.read_board(Image.open(path))
    ok(f"{name} is not read as a duel", not D.is_duel(rows), f"got {D.describe(rows)}")


def test_pick_prefers_a_wanted_contest_at_good_odds():
  print("\n-- test_pick_prefers_a_wanted_contest_at_good_odds")
  rows = [row("wit", "d"), row("sta", "c"), row("energy", "c")]
  ok("energy is taken over stamina when both are good",
     D.pick(rows, ["energy", "sta"]) == 3)
  ok("and stamina when energy is not offered",
     D.pick([row("wit", "d"), row("sta", "c"), row("pwr", "d")], ["energy", "sta"]) == 2)


def test_pick_never_takes_a_cross():
  """A certain loss buys nothing; a likely win on an unwanted stat still levels
  Happy Meek toward the stronger final race."""
  print("\n-- test_pick_never_takes_a_cross")
  rows = [row("wit", "d"), row("pwr", "c"), row("energy", "x")]
  ok("a wanted contest at a cross is refused", D.pick(rows, ["energy", "sta"]) == 1)
  rows2 = [row("wit", "t"), row("pwr", "x"), row("energy", "x")]
  ok("and the best of a bad board is taken", D.pick(rows2, ["energy"]) == 1)
  rows3 = [row("wit", "x"), row("pwr", "x"), row("energy", "x")]
  ok("an all-cross board is left to the usual scoring",
     D.pick(rows3, ["energy"]) == 0)


def test_pick_falls_back_without_glyphs():
  print("\n-- test_pick_falls_back_without_glyphs")
  rows = [row("wit"), row("energy"), row("sta")]
  ok("the wanted contest is taken on its label alone",
     D.pick(rows, ["energy", "sta"]) == 2)
  ok("and nothing wanted means no opinion",
     D.pick([row("wit"), row("pwr")], ["energy", "sta"]) == 0)
  ok("an empty board is no opinion", D.pick([], ["energy"]) == 0)


def test_pick_on_the_real_boards():
  print("\n-- test_pick_on_the_real_boards")
  # choice_0 is WIT=@, SPD=@, ENERGY=X - energy is wanted but certain to lose,
  # so the best odds on the board win instead.
  rows = D.read_board(fixture("choice_0_ddx.png"))
  ok("choice_0: energy at a cross is passed over",
     D.pick(rows, ["energy", "sta"]) == 1, f"{D.describe(rows)} -> {D.pick(rows, ['energy', 'sta'])}")
  # choice_3 is WIT=O, STA=X, GUTS=X - stamina is wanted, but at a cross.
  rows = D.read_board(fixture("choice_3_cxx.png"))
  ok("choice_3: stamina at a cross is passed over",
     D.pick(rows, ["energy", "sta"]) == 1, f"{D.describe(rows)} -> {D.pick(rows, ['energy', 'sta'])}")


for test in (test_every_glyph_reads_as_captured,
             test_every_row_names_its_contest,
             test_option_one_is_always_a_stat,
             test_a_normal_event_is_not_a_duel,
             test_pick_prefers_a_wanted_contest_at_good_odds,
             test_pick_never_takes_a_cross,
             test_pick_falls_back_without_glyphs,
             test_pick_on_the_real_boards):
  test()

print()
if failures:
  print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
  sys.exit(1)
print("all checks passed")
