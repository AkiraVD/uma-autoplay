"""Saved race lists: what survives a round trip, and what is refused.

Run with `python tests/test_race_lists.py` from the repo root. Needs neither
the game nor master.mdb - the store is plain files - and it writes to a
throwaway folder rather than the real `uma_race_lists/`.

The traversal cases are the point of the file. These routes are reachable over
the tailnet, so a name arriving from a browser is the one place a filename can
be steered from outside; `path_for` has to refuse anything that resolves
outside the folder rather than trusting the page to have behaved.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import server.race_lists as R  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def race(name, year="Classic Year", date="Early Apr", image=True):
  return {"name": name, "year": year, "date": date, "grade": "G1",
          "racetrack": "Tokyo", "terrain": "Turf", "has_image": image}


def main():
  tmp = Path(tempfile.mkdtemp(prefix="uma-race-lists-"))
  R.LISTS_DIR = tmp
  try:
    print("-- a name that can't be a filename is refused")
    for bad in ("../escape", "..", "/etc/passwd", "", "   ", "...", "./.."):
      ok(f"refused {bad!r}", R.path_for(bad) is None or
         R.path_for(bad).parent == tmp.resolve(), R.path_for(bad))
    ok("a traversal name never leaves the folder",
       all(R.path_for(b) is None or R.path_for(b).parent == tmp.resolve()
           for b in ("../escape", "../../etc/passwd", "a/../../b")))

    print("\n-- an ordinary name round-trips")
    path = R.path_for("Turf miler")
    ok("the name resolves", path is not None and path.parent == tmp.resolve())
    data = R.normalise({
      "title": "Turf miler",
      "races": [race("Osaka Hai"), race("Yasuda Kinen", date="Early Jun")],
      "settings": {"fill": True, "includeOp": False},
      "epithets": ["Breakneck Miler"],
    })
    R.write(path, data)
    back = R.read(path)
    ok("both races came back", len(back["races"]) == 2, len(back["races"]))
    ok("settings survived", back["settings"]["includeOp"] is False)
    ok("epithets survived", back["epithets"] == ["Breakneck Miler"])
    ok("a race keeps name, year and date",
       all(k in back["races"][0] for k in ("name", "year", "date")),
       sorted(back["races"][0]))

    print("\n-- junk is filtered, not stored")
    data = R.normalise({
      "title": "x" * 400,
      "races": [race("Good"), {"name": "No date"}, "not a dict",
                {"year": "Classic Year", "date": "Early Apr"}],
      "settings": ["not", "an", "object"],
      "epithets": ["fine", 42, None],
    })
    ok("only the complete race survived",
       [r["name"] for r in data["races"]] == ["Good"],
       [r.get("name") for r in data["races"]])
    ok("a non-object settings becomes {}", data["settings"] == {})
    ok("non-string epithets are dropped", data["epithets"] == ["fine"])
    ok("the title is capped", len(data["title"]) <= 120, len(data["title"]))
    ok("a non-object list is refused outright", R.normalise(["nope"]) is None)

    print("\n-- unknown race fields are not carried over")
    data = R.normalise({"races": [dict(race("Osaka Hai"), sneaky="payload")]})
    ok("an unlisted key is dropped", "sneaky" not in data["races"][0],
       sorted(data["races"][0]))

    print("\n-- listing")
    R.write(R.path_for("second"), R.normalise({
      "title": "Second", "races": [race("Arima Kinen", image=False)]}))
    rows = R.listing()
    ok("both lists are listed", len(rows) == 2, [r["name"] for r in rows])
    by_name = {r["name"]: r for r in rows}
    ok("counts are right", by_name["Turf miler"]["races"] == 2, by_name["Turf miler"])
    ok("runnable counts only races with a picture",
       by_name["second"]["runnable"] == 0 and by_name["Turf miler"]["runnable"] == 2,
       (by_name["second"]["runnable"], by_name["Turf miler"]["runnable"]))
    ok("newest first", rows == sorted(rows, key=lambda r: r["saved_at"], reverse=True))

    print("\n-- an unreadable file is listed, not fatal")
    (tmp / "broken.json").write_text("{ not json", encoding="utf-8")
    rows = R.listing()
    broken = [r for r in rows if r["name"] == "broken"]
    ok("the broken file is listed", len(broken) == 1)
    ok("and marked unreadable", broken and broken[0]["unreadable"])
    ok("the good lists are still there", len(rows) == 3, len(rows))

    print("\n-- a half-written file never appears")
    ok("write leaves no .tmp behind", not list(tmp.glob("*.tmp")),
       [p.name for p in tmp.glob("*.tmp")])

    print("\n-- delete")
    R.delete(R.path_for("second"))
    ok("it is gone", not R.path_for("second").exists())
    ok("and off the listing", "second" not in {r["name"] for r in R.listing()})

    print("\n-- the saved shape is what config.race_schedule takes")
    back = R.read(R.path_for("Turf miler"))
    entry = back["races"][0]
    ok("name, year, date and nothing required beyond them",
       all(isinstance(entry[k], str) for k in ("name", "year", "date")))
    ok("it is JSON-serialisable", json.dumps(back) and True)
  finally:
    shutil.rmtree(tmp, ignore_errors=True)

  print()
  if failures:
    print(f"{len(failures)} failing: " + ", ".join(failures))
    return 1
  print("all good")
  return 0


if __name__ == "__main__":
  sys.exit(main())
