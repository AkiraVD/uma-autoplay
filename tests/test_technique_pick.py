"""Which Technique a Lessons board buys, against the reserve kept for songs.

`core/lessons.py::choose` used to rank techniques by `(reserve dent, then
-value)`, so any dent at all lost to no dent however little the undented card
was worth. On 2026-10-12 that bought Guts +12 - worth 1.2, because that config
weights Guts at zero - over Speed +6 / Skill Pts +6 worth 13.8, because the
Speed card dented a 21-point Da reserve by two points.

Both boards below are read straight out of a log, with the points and the
reserve the bot printed beside them, so this is the real decision and not a
constructed one. The second is the case `reserve` was written for and is here
to pin the other side: a dent big enough to cost a song still has to lose.

Pure arithmetic over `choose`'s helpers - no OCR, no game.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["UMA_LOG_DIR"] = os.path.join("tests", "logs")

failures = []


def ok(label, cond, detail=""):
  print(("ok   " if cond else "FAIL ") + label + (f"   [{detail}]" if detail else ""))
  if not cond:
    failures.append(label)


def tech(name, effects, cost):
  da, pa, vo, vi, co = cost
  return {"kind": "technique", "name": name, "effects": effects,
          "cost": {"da": da, "pa": pa, "vo": vo, "vi": vi, "co": co},
          "learnable": True, "scheduled": False}


def pick(lessons, cards, points, held, energy=60):
  """The card `choose` would buy, by its own key."""
  return max(cards, key=lambda c: (
    lessons.technique_value(c, energy)
    - lessons.extra_deficit(lessons.card_cost(c), points, held) * lessons.RESERVE_DENT_COST,
    -lessons.cost_total(lessons.card_cost(c))))


def main():
  import core.state as state
  import core.lessons as lessons

  # The weights the 2026-10-12 career ran under: Guts last at 0, Speed first.
  state.PRIORITY_STAT = ["spd", "sta", "pwr", "wit", "guts"]
  state.PRIORITY_EFFECTS_LIST = {0: 1.4, 1: 1.2, 2: 1.0, 3: 0.9, 4: 0.0}
  state.ENERGY_TECHNIQUE_BELOW = 50

  # --- the board that went wrong, 06:02:42 Senior Year Early Nov -----------
  makeup = tech("Makeup Advanced Class", ["Guts +12"], (0, 0, 0, 24, 0))
  formation = tech("Formation Intermediate Class", ["Speed +6", "Skill Pts +6"],
                   (14, 0, 0, 10, 0))
  points = {"da": 33, "pa": 7, "vo": 38, "vi": 25, "co": 44}
  held = {"da": 21, "pa": 0, "vo": 21, "vi": 0, "co": 21}

  v_makeup = lessons.technique_value(makeup, 60)
  v_formation = lessons.technique_value(formation, 60)
  ok("Guts +12 is worth ~1.2 under these weights", abs(v_makeup - 1.2) < 0.01,
     f"{v_makeup:.2f}")
  ok("Speed +6 / Skill Pts +6 is worth ~13.8", abs(v_formation - 13.8) < 0.01,
     f"{v_formation:.2f}")
  d_makeup = lessons.extra_deficit(lessons.card_cost(makeup), points, held)
  d_formation = lessons.extra_deficit(lessons.card_cost(formation), points, held)
  ok("the Guts card dents the reserve by 0", d_makeup == 0, str(d_makeup))
  ok("the Speed card dents it by 2", d_formation == 2, str(d_formation))

  chosen = pick(lessons, [makeup, formation], points, held)
  ok("the Speed card is bought, not the Guts one",
     chosen["name"] == "Formation Intermediate Class", chosen["name"])

  # --- the other side: a dent that really does cost a song -----------------
  # Career 2's shape, which is why `reserve` exists: a Speed technique eating
  # the Da the last song needs. Worth more than the alternative and still has
  # to lose, or the fix above has simply moved the bug.
  speed12 = tech("Dance Step Advanced Class", ["Speed +12"], (24, 0, 0, 0, 0))
  cheap = tech("Group Lesson Basics", ["Skill Hint Lvl +1 (Long)"], (0, 0, 0, 0, 15))
  late_points = {"da": 33, "pa": 20, "vo": 20, "vi": 20, "co": 20}
  late_held = {"da": 21, "pa": 0, "vo": 0, "vi": 0, "co": 0}
  v_speed = lessons.technique_value(speed12, 60)
  d_speed = lessons.extra_deficit(lessons.card_cost(speed12), late_points, late_held)
  ok("the Speed +12 is the more valuable card", v_speed > lessons.technique_value(cheap, 60),
     f"{v_speed:.1f} vs {lessons.technique_value(cheap, 60):.1f}")
  ok("but it eats 12 points of the Da reserve", d_speed == 12, str(d_speed))
  chosen = pick(lessons, [speed12, cheap], late_points, late_held)
  ok("so the card that dents nothing is bought instead",
     chosen["name"] == "Group Lesson Basics", chosen["name"])

  # --- and a dent nobody has to pay for ------------------------------------
  # No reserve held at all: value alone should decide.
  free = {k: 0 for k in lessons.POINT_KEYS}
  chosen = pick(lessons, [makeup, formation], points, free)
  ok("with no reserve to protect, the better card wins",
     chosen["name"] == "Formation Intermediate Class", chosen["name"])

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
