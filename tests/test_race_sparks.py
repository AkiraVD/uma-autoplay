"""The Spark a race pays for winning it, read out of master.mdb.

Run with `python tests/test_race_sparks.py` from the repo root.

master.mdb draws **no** join between a race and the Spark it pays. The only
link is that the Spark carries the race's name in the game's abbreviated
spelling, so `server/master_data.py` matches it against the race's own short
name (text_data 29) and carries two aliases for the pair that abbreviate
further than any name the game stores - `J.D. Derby` and `JBC L. Classic`.

That is the whole reason this file exists. A name match is exactly the kind of
thing a patch breaks quietly: an unmatched Spark does not raise, it just stops
being shown, and nobody notices a badge that is missing. So the first check is
that **all 34 race Sparks still land on a race**, by name, with no silent
drops.

It also pins two numbers data/races.json had wrong before master.mdb became the
source (checked 2026-09-29): Hopeful Stakes pays Speed and Stamina, not Speed
and Power, and Arima Kinen pays Guts, not Power.

The mapping checks need master.mdb and are skipped without it; the planner
checks run on a synthetic pool.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import server.master_data as M  # noqa: E402
import server.race_plan as P  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def race(name, date, sparks=None):
  return {"name": name, "year": "Classic Year", "date": date, "grade": "G1",
          "terrain": "Turf", "racetrack": "Tokyo",
          "distance": {"type": "Mile", "meters": 1600},
          "fans": {"required": 0, "gained": 1000}, "sparks": sparks or []}


def main():
  if M.MDB_PATH.exists():
    con = M._connect()
    try:
      names = M._texts(con, M.TEXT_FACTOR_NAME)
      wanted = {M._factor_key(names.get(fid))
                for fid, in con.execute(
                  "select factor_id from succession_factor"
                  " where factor_type=? and rarity=1", (M.FACTOR_RACE,))}
      sparks = M._race_sparks(con)
    except sqlite3.Error as e:
      con.close()
      print(f"FAIL master.mdb unreadable: {e}")
      return 1
    con.close()

    print("-- every race Spark lands on a race")
    ok("master.mdb still holds 34 of them", len(wanted) == 34, len(wanted))
    # Each Spark is named after its race, so the set of names it resolved to is
    # the set of races that pay one. Aliases included, that must be all of them.
    paid = {s for s in sparks}
    ok("and every one of them mapped to a race",
       len(paid) == len(wanted), f"{len(paid)} races for {len(wanted)} Sparks")
    ok("the two abbreviated ones resolved",
       "Japan Dirt Derby" in sparks and "JBC Ladies' Classic" in sparks,
       sorted(n for n in sparks if "Derby" in n or "JBC" in n))

    print("\n-- a Spark reads hint first, then stats")
    ok("Oka Sho pays the Hanshin hint and Guts",
       sparks.get("Oka Sho") == ["Hanshin Racecourse ○", "Guts"],
       sparks.get("Oka Sho"))
    ok("a hintless Spark is stats only",
       sparks.get("Asahi Hai Futurity Stakes") == ["Speed", "Guts"],
       sparks.get("Asahi Hai Futurity Stakes"))
    ok("Hopeful Stakes pays Stamina, not Power",
       sparks.get("Hopeful Stakes") == ["Speed", "Stamina"],
       sparks.get("Hopeful Stakes"))
    ok("Arima Kinen pays Guts, not Power",
       sparks.get("Arima Kinen") == ["Nakayama Racecourse ○", "Guts"],
       sparks.get("Arima Kinen"))
    ok("every Spark names one or two stats",
       all(1 <= len([n for n in v if n in M.FACTOR_STATS.values()]) <= 2
           for v in sparks.values()))

    print("\n-- the race pool carries them")
    pool = M.get_races()["races"]
    flat = {n: d for year in pool.values() for n, d in year.items()}
    ok("every race has a sparks list", all("sparks" in d for d in flat.values()))
    ok("only the 34 Sparked races have one",
       {n for n, d in flat.items() if d["sparks"]} == paid,
       sorted({n for n, d in flat.items() if d["sparks"]} ^ paid))
  else:
    print("-- master.mdb absent; skipping the mapping checks")

  print("\n-- Spark hunting narrows the pool to the races that pay one")
  mixed = [race("G1 Sparker", "Early Apr", ["Speed"]),
           dict(race("G3 Filler", "Late Apr"), grade="G3"),
           dict(race("OP Filler", "Early May"), grade="OP")]
  out = P.plan(races=mixed, fill=True)
  ok("without it, everything runnable is scheduled",
     out["totals"]["races"] == 3, out["totals"]["races"])
  out = P.plan(races=mixed, fill=True, grades=P.SPARK_GRADES)
  ok("with it, only the G1 is",
     [r["name"] for r in out["schedule"]] == ["G1 Sparker"],
     [r["name"] for r in out["schedule"]])
  ok("and the turns it cannot fill offer nothing to pick",
     all(not t["options"] for t in out["turns"] if t["date"] in ("Late Apr", "Early May")))
  ok("a narrowed pool still reports its Sparks", out["totals"]["sparks"] == 1,
     out["totals"]["sparks"])

  if M.MDB_PATH.exists():
    # The mode only means "hunt Sparks" because the two sets are the same one.
    # If a patch ever adds a G1 that pays nothing, or a Spark below G1, the
    # filter stops being the thing the page calls it.
    everything = P.pool(None)
    g1 = {r["name"] for r in everything if r.get("grade") == "G1"}
    paid = {r["name"] for r in everything if r.get("sparks")}
    ok("every G1 pays a Spark and every Spark race is a G1", g1 == paid,
       sorted(g1 ^ paid))
    ok("SPARK_GRADES names the grade that does it", P.SPARK_GRADES == ("G1",),
       P.SPARK_GRADES)

  print("\n-- the planner reports them")
  pool = [race("Sparker", "Early Apr", ["Tokyo Racecourse ○", "Guts"]),
          race("Plain", "Late Apr"),
          race("Twice", "Early May", ["Speed"])]
  out = P.plan(races=pool, fill=True)
  ok("every scheduled race carries a sparks list",
     all(isinstance(r["sparks"], list) for r in out["schedule"]))
  ok("only the Sparked races are listed",
     [r["name"] for r in out["sparks"]] == ["Sparker", "Twice"],
     [r["name"] for r in out["sparks"]])
  ok("the list keeps the Spark's own names",
     out["sparks"][0]["sparks"] == ["Tokyo Racecourse ○", "Guts"],
     out["sparks"][0]["sparks"])
  ok("the total counts them", out["totals"]["sparks"] == 2,
     out["totals"]["sparks"])

  # The same race in two years pays its Spark once, and the total says so even
  # though both turns are listed.
  twice = [race("JBC Sprint", "Early Nov", ["Power", "Guts"]),
           dict(race("JBC Sprint", "Early Nov", ["Power", "Guts"]),
                year="Senior Year")]
  out = P.plan(races=twice, fill=True)
  ok("a race won in two years counts as one Spark",
     out["totals"]["sparks"] == 1 and len(out["sparks"]) == 2,
     (out["totals"]["sparks"], len(out["sparks"])))

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0


if __name__ == "__main__":
  sys.exit(main())
