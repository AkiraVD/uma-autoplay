"""Keeping the spark the duels were run for.

Run with `python tests/test_duel_spark.py` from the repo root.

The chain a parent-making URA career depends on is: win the right duel, get the
hint, **buy the skill**, then roll the spark. The buying is the step nothing did
before - `skill_score.plan` values `Racing Spirit: Mood` at about 3.4 expected
SV for 150 points, which loses to almost anything - and the keeping is the step
that could undo it, because the reroll compares two sets on stars and white
*count* alone.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

from PIL import Image  # noqa: E402

import core.masterdb as masterdb  # noqa: E402
import core.skill_score as skill_score  # noqa: E402
import core.sparks as sparks  # noqa: E402
import core.state as state  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(("ok   " if condition else "FAIL ") + label + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def row(kind, stars=1, name=None):
  out = {"kind": kind, "stars": stars}
  if name is not None:
    out["name"] = name
  return out


def a_set(*names, blue=1):
  """A plausible set: the three coloured sparks plus named greys."""
  return ([row("stat", blue), row("aptitude", 2), row("unique", 2)]
          + [row("skill", 1, n) for n in names])


def test_the_optimizer_would_never_buy_them():
  """The premise of the forced path. If this ever stops being true the force
  is redundant, and this test is where that shows up."""
  print("\n-- test_the_optimizer_would_never_buy_them")
  records = {r["name"]: r for r in masterdb.skills()}
  if not records:
    ok("master.mdb is readable", False, "no skills loaded")
    return
  for name in ("Racing Spirit: Mood", "Racing Spirit: Stamina"):
    record = records.get(name)
    if not record:
      ok(f"{name} is in master.mdb", False)
      continue
    sv = skill_score.expected_sv(record)
    ok(f"{name} is priced low enough to lose the knapsack",
       sv < 5.0 and record["cost"] == 150, f"{sv:.2f} SV at {record['cost']} points")
    ok(f"{name} is not a volatile green (so it is offered at all)",
       not skill_score.is_volatile_green(record))


def test_a_wanted_spark_is_counted():
  print("\n-- test_a_wanted_spark_is_counted")
  before = state.URA_KEEP_SPARKS
  try:
    state.URA_KEEP_SPARKS = ["Racing Spirit: Mood"]
    rows = a_set("racing spirit: mood", "hawkeye")
    ok("a named row counts", sparks.wanted(rows) == 1, sparks.wanted(rows))
    ok("an unnamed set counts nothing",
       sparks.wanted(a_set("hawkeye", "triple 7s")) == 0)
    state.URA_KEEP_SPARKS = []
    ok("and nothing is wanted when config names nothing",
       sparks.wanted(rows) == 0)
  finally:
    state.URA_KEEP_SPARKS = before


def test_a_wanted_spark_outranks_stars():
  print("\n-- test_a_wanted_spark_outranks_stars")
  before = state.URA_KEEP_SPARKS
  try:
    state.URA_KEEP_SPARKS = ["Racing Spirit: Mood"]
    keeper = a_set("racing spirit: mood", blue=1)
    fatter = a_set("hawkeye", "triple 7s", "extra tank", blue=3)
    ok("the set with the wanted spark ranks higher",
       sparks.rank(keeper) > sparks.rank(fatter),
       f"{sparks.rank(keeper)} vs {sparks.rank(fatter)}")
    ok("and it is not rerolled away despite a 1-star blue",
       sparks.worth_rerolling(keeper) is False)
    ok("while the same set without it still rerolls",
       sparks.worth_rerolling(a_set("hawkeye", blue=1)) is True)
  finally:
    state.URA_KEEP_SPARKS = before


def test_the_ordinary_rule_is_untouched():
  """Every career that names no spark must behave exactly as before."""
  print("\n-- test_the_ordinary_rule_is_untouched")
  before = state.URA_KEEP_SPARKS
  try:
    state.URA_KEEP_SPARKS = []
    ok("a 3-star blue is kept", sparks.worth_rerolling(a_set("x", blue=3)) is False)
    ok("a 2-star blue is rerolled", sparks.worth_rerolling(a_set("x", blue=2)) is True)
    ok("more whites still break a tie",
       sparks.rank(a_set("a", "b", blue=2)) > sparks.rank(a_set("a", blue=2)))
  finally:
    state.URA_KEEP_SPARKS = before


def test_row_names_read_off_a_real_screen():
  print("\n-- test_row_names_read_off_a_real_screen")
  path = os.path.join("tests", "fixtures", "sparks", "sparks_speed3star_c4.png")
  if not os.path.exists(path):
    return
  before = state.URA_KEEP_SPARKS
  try:
    state.URA_KEEP_SPARKS = ["Japanese Derby"]
    rows = sparks.read(Image.open(path))
    named = [r.get("name") for r in rows if r["kind"] == "skill"]
    ok("every grey row is named", all(named), named)
    ok("and a config name matches one of them",
       sparks.wanted(rows) == 1, f"{sparks.wanted(rows)} from {named}")
  finally:
    state.URA_KEEP_SPARKS = before


def test_the_plus_suffix_a_live_career_actually_produced():
  """The bug this rule was written to prevent, and then caused itself.

  On 2026-09-25 the rerolled set held `Racing Spirit: Mood` and the rule scored
  it 0, because the screen puts a `+` after a spark's name and easyocr keeps it
  (`racing spirit: mood +`). `base_name` strips the rank glyph but not that, so
  the exact match failed and the set was rerolled away.
  """
  print("\n-- test_the_plus_suffix_a_live_career_actually_produced")
  ok("a trailing + is not part of the name",
     sparks.match_key("racing spirit: mood +") == "racing spirit: mood",
     sparks.match_key("racing spirit: mood +"))
  ok("and a rank glyph still goes too",
     sparks.match_key("Standard Distance 0") == "standard distance")

  original = os.path.join("tests", "fixtures", "sparks", "sparks_ura_wit_spark.png")
  rerolled = os.path.join("tests", "fixtures", "sparks", "sparks_ura_mood_spark.png")
  if not (os.path.exists(original) and os.path.exists(rerolled)):
    return
  before = state.URA_KEEP_SPARKS
  try:
    state.URA_KEEP_SPARKS = ["Racing Spirit: Mood", "Racing Spirit: Stamina"]
    o = sparks.read(Image.open(original))
    r = sparks.read(Image.open(rerolled))
    ok("the set holding Mood is recognised", sparks.wanted(r) == 1, sparks.wanted(r))
    ok("the set without it is not", sparks.wanted(o) == 0, sparks.wanted(o))
    ok("and it is kept despite a worse blue star",
       sparks.rank(r) > sparks.rank(o), f"{sparks.rank(r)} vs {sparks.rank(o)}")
    ok("so it is not rerolled away", sparks.worth_rerolling(r) is False)
  finally:
    state.URA_KEEP_SPARKS = before


for test in (test_the_optimizer_would_never_buy_them,
             test_the_plus_suffix_a_live_career_actually_produced,
             test_a_wanted_spark_is_counted,
             test_a_wanted_spark_outranks_stars,
             test_the_ordinary_rule_is_untouched,
             test_row_names_read_off_a_real_screen):
  test()

print()
if failures:
  print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
  sys.exit(1)
print("all checks passed")
