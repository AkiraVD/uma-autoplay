"""Building a Trackblazer race schedule: scarcity, pinning, and what it refuses.

Run with `python tests/test_race_plan.py` from the repo root.

Most of this runs on a synthetic race pool passed in through `races=`, so it
needs neither the game nor master.mdb. The few assertions that need the real
calendar say so and are skipped when the mdb is absent.

Four of these exist because the bug happened:

- **Nested epithets must share races.** Winning 15 dirt races satisfies
  `Eat My Dust`, `Playing Dirty` and `Dirty Work` together. An early version
  counted only *free* turns, so the three billed 30 turns instead of 15; the
  targets between them reserved all 59 turns of the career, and 18 epithets
  came back "not enough free turns" while being charged for races already on
  the schedule.
- **Scarcity must beat value.** `Lady` has exactly three candidate races on
  three turns and no slack; `Standard Distance Leader` takes any 10 of 133.
  Ordering by value spent the scarce turns on flexible targets, then called the
  scarce ones unreachable.
- **A turn may hold one race.** Everything else rests on that.
- **A pinned turn is the user overriding the solver**, so it survives run
  thinning and is never reassigned.

`Lady` against `Stunning` is *not* a bug and is pinned here so nobody "fixes"
it: the Triple Tiara and the Triple Crown fall on the same three Classic turns,
so a schedule may have one or the other, never both.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.epithets as E  # noqa: E402
import server.race_plan as P  # noqa: E402
import utils.constants as constants  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def race(name, date, year="Classic Year", grade="G3", terrain="Turf",
         track="Tokyo", dtype="Mile", meters=1600, fans=1000):
  return {"name": name, "year": year, "date": date, "grade": grade,
          "terrain": terrain, "racetrack": track,
          "distance": {"type": dtype, "meters": meters},
          "fans": {"required": 0, "gained": fans}, "has_image": False}


def dirt_pool(n):
  """n dirt races on consecutive Classic turns, all G1 so they count everywhere."""
  return [race(f"Dirt {i}", constants.DATE_ARRAY[i], grade="G1", terrain="Dirt")
          for i in range(n)]


def main():
  print("-- a turn holds one race")
  pool = dirt_pool(20)
  out = P.plan(races=pool, fill=True)
  turns = [(r["year"], r["date"]) for r in out["schedule"]]
  ok("no turn is used twice", len(turns) == len(set(turns)), len(turns))
  ok("every scheduled race came from the pool",
     {r["name"] for r in out["schedule"]} <= {r["name"] for r in pool})

  print("\n-- nested epithets share their races")
  out = P.plan(targets=["Eat My Dust", "Playing Dirty", "Dirty Work"],
               races=dirt_pool(20), fill=False)
  earned = [e["name"] for e in out["epithets"]]
  ok("all three nested dirt epithets are earned", len(earned) == 3, earned)
  ok("and they cost 15 races, not 30", out["totals"]["races"] == 15,
     out["totals"]["races"])

  print("\n-- a target already satisfied costs nothing extra")
  out = P.plan(targets=["Eat My Dust", "Dirty Work"], races=dirt_pool(20), fill=False)
  ok("adding the cheaper nested target adds no races",
     out["totals"]["races"] == 15, out["totals"]["races"])

  print("\n-- the schedule is the shape config.race_schedule takes")
  entry = out["schedule"][0]
  ok("every entry has name, year and date",
     all(k in entry for k in ("name", "year", "date")), sorted(entry))

  print("\n-- an unreachable target is reported, never silently dropped")
  out = P.plan(targets=["Eat My Dust"], races=dirt_pool(5), fill=False)
  ok("15 dirt wins cannot come from 5 races", out["epithets"] == [], out["epithets"])
  ok("and it says so", "Eat My Dust" in out["missed"], out["missed"])

  print("\n-- unmodelled epithets are never claimed")
  out = P.plan(targets=["Legendary", "Moneymaker"], races=dirt_pool(20), fill=False)
  ok("no unmodelled epithet is earned", out["epithets"] == [])
  ok("both are reported as missed", set(out["missed"]) == {"Legendary", "Moneymaker"},
     out["missed"])

  print("\n-- aptitudes filter the pool")
  mixed = dirt_pool(10) + [race(f"Turf {i}", constants.DATE_ARRAY[i + 10])
                           for i in range(10)]
  apt = {"surface_turf": "A", "surface_dirt": "G",
         "distance_mile": "A", "distance_sprint": "G",
         "distance_medium": "G", "distance_long": "G"}
  out = P.plan(races=mixed, aptitudes=apt, fill=True)
  ok("no dirt race survives a G dirt aptitude",
     not [r for r in out["schedule"] if r["terrain"] == "Dirt"],
     [r["name"] for r in out["schedule"] if r["terrain"] == "Dirt"])
  out = P.plan(races=mixed, fill=True)
  ok("and without aptitudes the dirt races are back",
     any(r["terrain"] == "Dirt" for r in out["schedule"]))

  print("\n-- the aptitude floor is adjustable")
  apt_b = {"surface_turf": "B", "surface_dirt": "G", "distance_mile": "B",
           "distance_sprint": "G", "distance_medium": "G", "distance_long": "G"}
  out = P.plan(races=mixed, aptitudes=apt_b, min_aptitude="b", fill=True)
  ok("a B aptitude runs at floor B", out["totals"]["races"] > 0, out["totals"]["races"])
  out = P.plan(races=mixed, aptitudes=apt_b, min_aptitude="a", fill=True)
  ok("and not at floor A", out["totals"]["races"] == 0, out["totals"]["races"])

  print("\n-- OP races can be kept out")
  op = [race("Op 1", constants.DATE_ARRAY[0], grade="OP"),
        race("G3 1", constants.DATE_ARRAY[1], grade="G3")]
  out = P.plan(races=op, include_op=False, fill=True)
  ok("only the graded race survives",
     [r["name"] for r in out["schedule"]] == ["G3 1"],
     [r["name"] for r in out["schedule"]])
  out = P.plan(races=op, include_op=True, fill=True)
  ok("and both are back when OP is allowed", out["totals"]["races"] == 2)

  print("\n-- the user overrides the solver")
  turn = P.key_of("Classic Year", constants.DATE_ARRAY[3])
  out = P.plan(races=dirt_pool(20), fill=True, skip=[turn])
  ok("a skipped turn holds no race",
     turn not in {P.key_of(r["year"], r["date"]) for r in out["schedule"]})
  out = P.plan(races=dirt_pool(20), fill=False, targets=[],
               locks={turn: "Dirt 3"})
  ok("a locked race is scheduled even with no targets",
     [r["name"] for r in out["schedule"]] == ["Dirt 3"],
     [r["name"] for r in out["schedule"]])
  out = P.plan(races=dirt_pool(20), fill=True, targets=[],
               locks={turn: "Dirt 3"}, max_consecutive=1)
  ok("and thinning never drops it",
     "Dirt 3" in {r["name"] for r in out["schedule"]})

  print("\n-- max_consecutive")
  out = P.plan(races=dirt_pool(20), targets=[], fill=True, max_consecutive=3)
  ok("no run longer than 3 survives", out["totals"]["longest_run"] <= 3,
     out["totals"]["longest_run"])
  out = P.plan(races=dirt_pool(20), targets=[], fill=True, max_consecutive=0)
  ok("0 means no limit", out["totals"]["races"] == 20, out["totals"]["races"])

  print("\n-- the turn grid covers the whole career")
  out = P.plan(races=dirt_pool(20), fill=True)
  ok("59 raceable turns", len(out["turns"]) == 59, len(out["turns"]))
  ok("every turn has a key and a year",
     all(t["key"] and t["year"] for t in out["turns"]))
  picked = {t["key"] for t in out["turns"] if t["picked"]}
  ok("the grid agrees with the schedule",
     picked == {P.key_of(r["year"], r["date"]) for r in out["schedule"]})

  print("\n-- progress is reported for unearned epithets too")
  out = P.plan(targets=["Dirty Work"], races=dirt_pool(20), fill=False)
  by_name = {e["name"]: e for e in out["progress"]}
  ok("Dirty Work is earned", by_name["Dirty Work"]["earned"])
  ok("Playing Dirty shows partial progress",
     by_name["Playing Dirty"]["have"] == 5 and by_name["Playing Dirty"]["need"] == 10,
     (by_name["Playing Dirty"]["have"], by_name["Playing Dirty"]["need"]))
  ok("progress never exceeds need",
     all(e["have"] <= e["need"] for e in out["progress"]))

  print("\n-- totals add up")
  out = P.plan(targets=["Eat My Dust", "Playing Dirty"], races=dirt_pool(20), fill=False)
  want = sum(E.value_of(e["name"]) * 2 for e in out["epithets"])
  ok("epithet_stats is the per-stat value doubled",
     out["totals"]["epithet_stats"] == want, (out["totals"]["epithet_stats"], want))
  ok("races counted matches the schedule",
     out["totals"]["races"] == len(out["schedule"]))
  ok("no stat, SP or fan column is reported",
     not ({"stats", "sp", "fans", "score"} & set(out["totals"])), sorted(out["totals"]))

  print("\n-- filling adds races but never removes epithets")
  bare = P.plan(races=dirt_pool(20), fill=False)
  full = P.plan(races=dirt_pool(20), fill=True)
  ok("fill never schedules fewer races",
     full["totals"]["races"] >= bare["totals"]["races"],
     (bare["totals"]["races"], full["totals"]["races"]))
  ok("fill never loses an epithet",
     full["totals"]["epithets"] >= bare["totals"]["epithets"])

  print("\n-- the catalogue offers every epithet")
  cat = P.catalogue()["epithets"]
  ok("40 entries", len(cat) == 40, len(cat))
  ok("unmodelled ones are not selectable and say why",
     all(e["why"] for e in cat if not e["selectable"]))

  if E.load().get("Lady", {}).get("condition"):
    print("\n-- the real calendar: Lady and Stunning cannot both be had")
    everything = P.pool(None)
    def turns_for(name):
      rule = E.load()[name]["rule"]
      return {P._turn(r) for r in everything if E.matches(rule, r)}
    lady, stunning = turns_for("Lady"), turns_for("Stunning")
    ok("both want exactly three turns", len(lady) == 3 and len(stunning) == 3,
       (len(lady), len(stunning)))
    ok("and they are the same three turns", lady == stunning,
       sorted(map(str, lady ^ stunning)))
    got = {e["name"] for e in P.plan(fill=False)["epithets"]}
    ok("a real plan earns one of them, not both",
       len({"Lady", "Stunning"} & got) == 1, sorted({"Lady", "Stunning"} & got))
    ok("each is earnable when asked for alone",
       {e["name"] for e in P.plan(targets=["Lady"], fill=False)["epithets"]} == {"Lady"})
    print("\n-- the real calendar: every turn in the grid is real")
    grid = P.plan(fill=True)["turns"]
    ok("Junior year opens at Late Jul",
       [t["date"] for t in grid if t["year"] == "Junior Year"][0] == "Late Jul")
    ok("Classic and Senior run 24 turns each",
       len([t for t in grid if t["year"] == "Classic Year"]) == 24
       and len([t for t in grid if t["year"] == "Senior Year"]) == 24)
  else:
    print("\n-- master.mdb absent; skipping the real-calendar checks")

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0


if __name__ == "__main__":
  sys.exit(main())
