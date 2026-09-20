"""Trackblazer epithet prices, rules, and what counts as a qualifying win.

Run with `python tests/test_epithets.py` from the repo root.

The conditions are matched by a hand-written rule per epithet rather than by
parsing the mdb prose, because the prose has at least six shapes and a regex
that misread one would fail silently - a schedule that quietly misses an
epithet still looks like a schedule. So the rules are what need pinning.

Two of these assertions exist because the bug happened, not because it was
imagined:

- `Globe-Trotter` was written from a hand-typed country list and missed two of
  the eight country-named races, `Copa Republica Argentina` and `Saudi Arabia
  Royal Cup`. Auditing the race table found them.
- the racecourse epithets say *graded* races, so an OP race at Kokura must not
  count toward `Kokura Constable`. Admitting OP races to the race pool is on
  the cards, which is exactly when this would have started silently passing.

Everything except the master.mdb block runs without the game installed:
`load()` falls back to the rule table, so matching is testable offline.
"""
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.epithets as E  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def race(name, grade="G3", terrain="Turf", track="Tokyo", dtype="Mile", meters=1600):
  return {"name": name, "grade": grade, "terrain": terrain, "racetrack": track,
          "distance": {"type": dtype, "meters": meters}}


def main():
  rows = E.load()

  print("-- the table loads")
  ok("40 Trackblazer epithets", len(rows) == 40, len(rows))
  ok("29 carry a matching rule",
     sum(1 for r in rows.values() if r["rule"]) == 29,
     sum(1 for r in rows.values() if r["rule"]))

  print("\n-- prices, in per-stat units")
  ok("33 carry a stat price",
     sum(1 for r in rows.values() if r["value"]) == 33,
     sum(1 for r in rows.values() if r["value"]))
  ok("3 pay a skill hint instead",
     sum(1 for r in rows.values() if r["hint"]) == 3)
  ok("prices are only ever 5, 10 or 15",
     {r["value"] for r in rows.values() if r["value"]} == {5, 10, 15},
     sorted({r["value"] for r in rows.values() if r["value"]}))
  ok("the four career milestones are unpriced",
     all(rows[m]["value"] == 0 and not rows[m]["hint"] for m in E.MILESTONES))
  ok("a hint epithet scores no stats", E.value_of("Legendary") == 0)
  ok("Lady is +10 per stat, not +20 total", E.value_of("Lady") == 10)

  print("\n-- what is deliberately not modelled")
  un = E.unmodelled()
  ok("11 are unmodelled", len(un) == 11, sorted(un))
  ok("every unmodelled one has a rule of None",
     set(un) == {n for n, r in E.RULES.items() if r is None})
  ok("milestones say why", all("milestone" in un[m] for m in E.MILESTONES))
  ok("chained ones name their prerequisite", "Lady" in un["Heroine"], un["Heroine"])

  print("\n-- name patterns")
  juniors = [race(f"{t} Junior Stakes") for t in ("Hakodate", "Niigata", "Sapporo")]
  ok("Junior Jewel takes three Junior Stakes", E.satisfied("Junior Jewel", juniors))
  ok("and not two", not E.satisfied("Junior Jewel", juniors[:2]))
  ok("Umatastic matches the game's spelling, no space",
     E.matches(E.RULES["Umatastic"], race("Fuchu Umamusume Stakes")))

  print("\n-- Globe-Trotter, the country list that was audited")
  ok("Saudi Arabia Royal Cup counts",
     E.matches(E.RULES["Globe-Trotter"], race("Saudi Arabia Royal Cup")))
  ok("Copa Republica Argentina counts",
     E.matches(E.RULES["Globe-Trotter"], race("Copa Republica Argentina")))
  ok("Japanese Oaks counts through 'Japan'",
     E.matches(E.RULES["Globe-Trotter"], race("Japanese Oaks")))
  ok("an ordinary race does not",
     not E.matches(E.RULES["Globe-Trotter"], race("Arima Kinen")))
  ok("Brazil Cup counts, which only the OP pool revealed",
     E.matches(E.RULES["Globe-Trotter"], race("Brazil Cup")))
  # Deliberate: "Nippon" is Japan's name in Japanese and may well qualify, but
  # counting a race the game does not would build a schedule around an epithet
  # that never fires. Flip this assertion once the game confirms it pays.
  ok("Nippon is excluded until the game confirms it",
     not E.matches(E.RULES["Globe-Trotter"], race("Radio Nippon Sho")))

  print("\n-- racecourse sets are graded-only")
  graded = [race("Kokura Kinen", track="Kokura"), race("Kitakyushu Kinen", track="Kokura")]
  ok("Kokura Constable takes two graded wins there",
     E.satisfied("Kokura Constable", graded))
  ok("an OP race at Kokura does not count",
     not E.satisfied("Kokura Constable",
                     [dict(r, grade="OP") for r in graded]))
  ok("Kanto Conqueror includes Kawasaki, which the web table drops",
     E.matches(E.RULES["Kanto Conqueror"], race("Kawasaki Kinen", track="Kawasaki")))
  ok("Tohoku Top Dog includes Morioka, likewise",
     E.matches(E.RULES["Tohoku Top Dog"], race("Cluster Cup", track="Morioka")))

  print("\n-- counts by surface and grade")
  dirt_g1 = [race(f"Dirt G1 {i}", grade="G1", terrain="Dirt") for i in range(3)]
  ok("Dirt G1 Achiever wants three", E.satisfied("Dirt G1 Achiever", dirt_g1))
  ok("Dirt G1 Star wants four", not E.satisfied("Dirt G1 Star", dirt_g1))
  ok("turf G1s do not count toward a dirt epithet",
     not E.satisfied("Dirt G1 Achiever", [dict(r, terrain="Turf") for r in dirt_g1]))

  print("\n-- standard distance is a multiple of 400m")
  std = E.RULES["Standard Distance Leader"]
  non = E.RULES["Non-Standard Distance Leader"]
  ok("1600m is standard", E.matches(std, race("x", meters=1600)))
  ok("2400m is standard", E.matches(std, race("x", meters=2400)))
  ok("1800m is not", not E.matches(std, race("x", meters=1800)))
  ok("1800m is non-standard", E.matches(non, race("x", meters=1800)))

  print("\n-- spread epithets need each bucket, not just the count")
  turf = [race("a", dtype="Sprint"), race("b", dtype="Mile"),
          race("c", dtype="Medium"), race("d", dtype="Long")]
  ok("Turf Tussler takes one of each turf distance",
     E.satisfied("Turf Tussler", turf))
  ok("and fails without a long race", not E.satisfied("Turf Tussler", turf[:3]))
  ok("four sprints are not a spread",
     not E.satisfied("Turf Tussler", [race(f"s{i}", dtype="Sprint") for i in range(4)]))
  ok("dirt races do not satisfy the turf spread",
     not E.satisfied("Turf Tussler", [dict(r, terrain="Dirt") for r in turf]))

  print("\n-- named race sets need every race named")
  stunning = [race("Satsuki Sho"), race("Tokyo Yushun Japanese Derby"), race("Kikuka Sho")]
  ok("Stunning takes its three", E.satisfied("Stunning", stunning))
  ok("and not two of the three", not E.satisfied("Stunning", stunning[:2]))
  ok("three unrelated wins are not Stunning",
     not E.satisfied("Stunning", [race("Arima Kinen"), race("Japan Cup"), race("Oka Sho")]))

  print("\n-- an unmodelled epithet never claims to be satisfied")
  ok("Legendary is never satisfied by races alone",
     not E.satisfied("Legendary", stunning + turf + dirt_g1))
  ok("a career milestone is never satisfied",
     not E.satisfied("Moneymaker", stunning + turf))
  ok("candidates() is empty for an unmodelled epithet",
     E.candidates("Climax King", turf) == [])

  from_mdb = sum(1 for r in rows.values() if r["condition"])
  if from_mdb:
    print("\n-- master.mdb is present, so the rules can be checked against it")
    ok("every epithet carries the game's condition text", from_mdb == 40, from_mdb)
    problems = E.check()
    ok("check() finds no rule disagreeing with the mdb", problems == [], problems)
    ranks = dict(collections.Counter(r["rank"] for r in rows.values()))
    ok("rank distribution is 6/22/12", ranks == {1: 6, 2: 22, 3: 12}, ranks)
    ok("Kanto Conqueror's condition still names Funabashi",
       "Funabashi" in rows["Kanto Conqueror"]["condition"])
  else:
    print("\n-- master.mdb absent; skipping the condition checks")
    ok("the rule table still loads without the game",
       len(rows) == 40 and all(r["value"] or r["hint"] or r["name"] in E.MILESTONES
                               for r in rows.values()))

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0


if __name__ == "__main__":
  sys.exit(main())
