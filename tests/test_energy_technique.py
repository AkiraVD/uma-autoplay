"""Pricing an Energy technique on the Grand Concert Lessons board.

Energy is what caps a career's TOTAL stats - in the 2026-10-13 career every
one of the ten rests was forced by the energy floor - so points turned into
energy come back as whole extra trainings. Two things were wrong with how the
board priced them, and both are pinned here.

**The cliff.** Energy used to be worth 1.5 a point below ENERGY_TECHNIQUE_BELOW
and 0.05 above it, so the same Energy +30 scored 45 on 49 energy and 1.5 on 51,
though at 51 it lands whole and wastes nothing. Only the part that overflows
the cap is lost, and now only that part is discounted.

**The dropped argument.** `core/execute.py` called `lessons.to_lessons()`
without `energy`, so every visit reached from a Schedule Notification priced
energy as if the tank were full. The six offers below are the real ones from
that career, with the energy the log recorded beside each; the two the bot
refused came in on that path.

Pure arithmetic over `technique_value` - no OCR, no game.
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


def tech(name, effects):
  return {"kind": "technique", "name": name, "effects": effects,
          "cost": {"da": 20, "pa": 0, "vo": 0, "vi": 0, "co": 0},
          "learnable": True, "scheduled": False}


# (energy at the time, the card, what the career did) - read off the log.
OFFERS = [
  (44.5, "Relaxing Body Massage", 30, "declined"),
  (48.3, "Facial-Slimming Massage", 20, "declined"),
  (62.7, "Facial-Slimming Massage", 20, "bought"),
  (85.2, "Relaxing Body Massage", 30, "declined"),
  (72.9, "Relaxing Body Massage", 30, "bought"),
  (25.0, "Facial-Slimming Massage", 20, "bought"),
]


def main():
  import core.state as state
  import core.lessons as lessons

  state.PRIORITY_STAT = ["spd", "sta", "pwr", "wit", "guts"]
  state.PRIORITY_EFFECTS_LIST = {0: 2.5, 1: 1.0, 2: 1.4, 3: 1.4, 4: 0.6}
  state.ENERGY_TECHNIQUE_BELOW = 50

  # --- the cliff is gone -----------------------------------------------------
  at49 = lessons.technique_value(tech("Massage", ["Energy +30"]), 49)
  at51 = lessons.technique_value(tech("Massage", ["Energy +30"]), 51)
  ok("+30 is worth about the same at 49 and 51 energy", abs(at49 - at51) < 1.0,
     f"{at49:.1f} vs {at51:.1f}")
  ok("...and both are comfortably worth taking", min(at49, at51) > lessons.WASTED_TECHNIQUE_FLOOR * 4,
     f"{min(at49, at51):.1f}")

  # --- but overflow is still discounted -------------------------------------
  at95 = lessons.technique_value(tech("Massage", ["Energy +30"]), 95)
  ok("+30 at 95 energy is nearly worthless (only 5 would land)", at95 < 10,
     f"{at95:.1f}")
  ok("...and is worth far less than the same card at 49", at95 < at49 / 4,
     f"{at95:.1f} vs {at49:.1f}")
  full = lessons.technique_value(tech("Massage", ["Energy +30"]), 100)
  ok("+30 on a full tank is worth almost nothing", full < 2, f"{full:.1f}")

  # --- an unknown reading must not read as "full" ---------------------------
  # This is the bug: to_lessons passed None, and None used to mean "no value".
  unknown = lessons.technique_value(tech("Massage", ["Energy +30"]), None)
  ok("an unknown energy reading is treated as room, not as waste",
     unknown > WORTH_TAKING, f"{unknown:.1f}")

  # --- the two the career wrongly refused -----------------------------------
  for energy, name, amount, did in OFFERS:
    value = lessons.technique_value(tech(name, [f"Energy +{amount}"]), energy)
    wasted = value < lessons.WASTED_TECHNIQUE_FLOOR
    if energy < 50:
      ok(f"{name} +{amount} at {energy} energy is now worth taking (career {did})",
         not wasted, f"{value:.1f}")
    elif energy > 80:
      # Not "worthless": at 85 energy nearly 15 points of a +30 still land,
      # which is most of a training's cost. What must hold is the ORDERING -
      # a near-full tank has to lose to an ordinary stat technique.
      rival = lessons.technique_value(tech("Dance Step Advanced", ["Speed +12"]), energy)
      ok(f"{name} +{amount} at {energy} energy loses to a Speed +12 (career {did})",
         value < rival, f"{value:.1f} vs {rival:.1f}")

  # --- the cap is the bar the game actually drew, not 100 -------------------
  # The Grand Concert extends the energy bar: the 2026-10-13 career sat at
  # 97-104 for eighteen turns. Pricing those against a flat 100 calls a tank
  # full when it still has headroom.
  try:
    lessons._energy_cap = None
    at104_default = lessons.energy_value(30, 104)
    lessons._energy_cap = 120
    at104_real = lessons.energy_value(30, 104)
    at60_real = lessons.energy_value(30, 60)
    lessons._energy_cap = None
    at60_default = lessons.energy_value(30, 60)
  finally:
    lessons._energy_cap = None
  ok("over a 100 bar, 104 energy reads as full", at104_default < 2,
     f"{at104_default:.1f}")
  ok("...but on the real 120 bar it still has room", at104_real > at104_default,
     f"{at104_real:.1f} vs {at104_default:.1f}")
  ok("a wider bar makes the same card worth more at the same energy",
     at60_real > at60_default, f"{at60_real:.1f} vs {at60_default:.1f}")
  ok("an unreadable cap falls back to ENERGY_CAP", lessons.ENERGY_CAP == 100)

  # --- a stat technique is unaffected ---------------------------------------
  spd = lessons.technique_value(tech("Dance Step Advanced", ["Speed +12"]), 90)
  ok("a Speed technique is priced the same whatever the energy",
     abs(spd - lessons.technique_value(tech("x", ["Speed +12"]), 10)) < 1e-9,
     f"{spd:.1f}")

  # --- the reserve the board holds back for a wit training -------------------
  # career_lobby scans the training board BEFORE the visit now, so the reserve
  # is this turn's real number rather than the deck's worst case. On a race day
  # there is no training to hand anything back, so it is nil.
  tech30 = dict(tech("Energy Massage", ["Energy +30"]), slot=0)
  locked_rival = dict(tech("Dance Step Advanced", ["Speed +12"]), slot=1, learnable=False)
  try:
    lessons._energy_cap = 105
    # Through choose(), not energy_offer: the verdict is only half the job - the
    # caller has to drop a preserved card from the ranking that follows, and it
    # did not until 2026-10-13.
    def buys(energy, wit_back):
      lessons.set_wit_return(wit_back)
      lessons.reset()
      lessons._energy_cap = 105
      lessons._songs.clear()
      lessons._songs.update({0: 2, 1: 2})
      action, card, _why = lessons.choose(
        [dict(tech30), dict(locked_rival)], energy, "Classic Year Early Apr",
        turn=30, points={"da": 54, "pa": 27, "vo": 30, "vi": 1, "co": 12})
      return action == "learn" and card is not None and "Energy" in card["name"]
    ok("with no wit training on the board the reserve is nil, so it buys",
       buys(70.0, 0))
    ok("...and with two max-bond wit cards on it, the same offer is preserved",
       not buys(70.0, 14.5))
    ok("an unpublished reserve falls back to the constant",
       not buys(70.0, None) if lessons.WIT_ENERGY_RETURN > 5 else True,
       f"constant {lessons.WIT_ENERGY_RETURN}")
    ok("and a low tank buys whatever the reserve is",
       buys(20.0, 14.5) and buys(20.0, 0))
  finally:
    lessons.set_wit_return(None)
    lessons._energy_cap = None

  # --- shop reports an energy purchase, because failure % depends on energy --
  ok("a fresh visit starts with no energy purchase recorded",
     lessons.bought_energy() is False)

  print()
  if failures:
    print(f"{len(failures)} check(s) failed:")
    for label in failures:
      print("  - " + label)
    return 1
  print("all checks passed")
  return 0


WORTH_TAKING = 3.0

if __name__ == "__main__":
  sys.exit(main())
