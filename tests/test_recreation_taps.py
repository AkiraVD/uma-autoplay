"""The friend-row tap counter, which quietly cost a Light Hello chain.

`core/execute.py::recreation_tap_giving_up` decides when to stop tapping a
Recreation friend row and take plain recreation instead. The guard itself is
right - a spent row that keeps its label looped a career for three minutes on
2026-09-24 - but the count was module state that only ever reset on the
confirmation dialog, and in the 2026-10-12 Grand Concert career that dialog
never matched once. So the counter stopped meaning "taps at this row" and
started meaning "friend outings taken", tripping on every third one.

The whole of that career's evidence is in `VISITS` below: seven friend-row
visits, read straight out of the log by their chevron count, with give-ups on
the 1st, 4th and 7th. The 7th was at four of five chevrons, so the last step of
the chain - the one that pays the most - was never taken.

Pure logic, no OCR and no game: `core.execute` imports `core.state`, which
builds the easyocr Reader, so it is stubbed the way the other decision tests
stub it.
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["UMA_LOG_DIR"] = os.path.join("tests", "logs")

failures = []


def ok(label, cond):
  print(("ok   " if cond else "FAIL ") + label)
  if not cond:
    failures.append(label)


# One row per friend-row visit in the 2026-10-12 career: the time, the chevron
# count the panel read, and whether the bot gave up and took plain recreation.
VISITS = [
  ("04:36:23", 0, True),
  ("04:39:27", 0, False),
  ("04:49:18", 1, False),
  ("04:57:03", 2, True),
  ("05:27:34", 2, False),
  ("05:44:16", 3, False),
  ("05:56:14", 4, True),
]


def main():
  import core.execute as execute

  # --- one tap per turn, which is what a healthy outing looks like ----------
  execute._recreation.update({"waits": 0, "taps": 0, "turn": None})
  gave_up = [execute.recreation_tap_giving_up(("Junior Year", turn))
             for turn in range(12)]
  ok("a single tap per turn never gives up", not any(gave_up))

  # --- the recorded career, one tap per visit ------------------------------
  execute._recreation.update({"waits": 0, "taps": 0, "turn": None})
  replayed = [execute.recreation_tap_giving_up(("Senior Year", time))
              for time, _chevrons, _was in VISITS]
  ok("none of the seven recorded visits gives up now", not any(replayed))
  ok("the 4/5 chevron visit is no longer downgraded", not replayed[-1])

  # --- the guard it must not break: a row that will not answer -------------
  # Same turn throughout, which is what a stuck row actually looks like.
  execute._recreation.update({"waits": 0, "taps": 0, "turn": None})
  stuck = [execute.recreation_tap_giving_up(("Senior Year", 7)) for _ in range(3)]
  ok("a row that ignores three taps in one turn still gives up",
     stuck == [False, False, True])

  # --- and the give-up must not leak into the next turn --------------------
  after = execute.recreation_tap_giving_up(("Senior Year", 8))
  ok("the next turn starts clean after a give-up", not after)

  # --- the exact shape of the old bug, stated as a test --------------------
  # Taps counted across turns is what made every third outing fall back. If
  # the key stops changing, the old behaviour comes back - so this asserts the
  # key is what carries the fix, not an incidental reset somewhere else.
  execute._recreation.update({"waits": 0, "taps": 0, "turn": None})
  frozen = [execute.recreation_tap_giving_up(("Senior Year", "same"))
            for _ in range(7)]
  ok("with the turn held fixed, the 3rd and 6th taps give up",
     [i for i, g in enumerate(frozen) if g] == [2, 5])

  print()
  if failures:
    print(f"{len(failures)} check(s) failed:")
    for label in failures:
      print("  - " + label)
    return 1
  print("all checks passed")
  return 0


if __name__ == "__main__":
  sys.exit(main())
