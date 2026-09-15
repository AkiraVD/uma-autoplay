"""Cap-awareness of core.logic.gain_score.

Run with `python tests/test_gain_caps.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader, which takes longer
than the whole check.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

fake = types.ModuleType("core.state")
fake.PRIORITY_STAT = ["spd", "pwr", "wit", "sta", "guts"]
fake.PRIORITY_EFFECTS_LIST = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
fake.PRIORITY_WEIGHT = "MEDIUM"
fake.STAT_CAPS = {"spd": 1500, "sta": 500, "pwr": 1200, "guts": 500, "wit": 1100}
fake.CURRENT_YEAR = "Senior Year"
fake.MAX_FAILURE = 15
for name in ("check_current_year", "stat_state", "stat_caps_state",
             "check_energy_level", "check_aptitudes"):
  setattr(fake, name, lambda *a, **k: None)
sys.modules["core.state"] = fake

import core
core.state = fake
import core.logic as L  # noqa: E402

failures = []

def data(gains, unity=None):
  return {"gains": gains, "unity": unity or {}}

def uncapped(gains, unity=None):
  """gain_score with no headroom known, i.e. the pre-cap behaviour."""
  L._stat_headroom = {}
  return L.gain_score(data(gains, unity), "spd")

def check(label, got, want):
  ok = abs(got - want) < 1e-9
  print(f"{'ok  ' if ok else 'FAIL'} {label}: got {got:.4f}, want {want:.4f}")
  if not ok:
    failures.append(label)

def main():
  # A gain into a stat with no room left is worth nothing, so the score matches
  # the same training with that stat absent.
  L.set_stat_headroom({"spd": 900, "sta": 500})
  capped = L.gain_score(data({"spd": 30, "sta": 20}), "spd")
  check("capped secondary is worth nothing", capped, uncapped({"spd": 30}))

  # Partial room: 12 of a 20 gain lands.
  L.set_stat_headroom({"spd": 900, "sta": 488})
  partial = L.gain_score(data({"spd": 30, "sta": 20}), "spd")
  check("partial headroom clips the gain", partial, uncapped({"spd": 30, "sta": 12}))

  # Skill points have no cap.
  L.set_stat_headroom({"spd": 1500, "sta": 500, "pwr": 1200, "guts": 500, "wit": 1100})
  check("skill points survive a full board",
        L.gain_score(data({"spd": 40, "skill": 30}), "spd"),
        30 * L.SKILL_PT_WEIGHT * L.STAT_GAIN_POINTS)

  # An unreadable stat is -1 and must not be mistaken for a capped one.
  L.set_stat_headroom({"spd": -1, "sta": 500})
  unread = L.gain_score(data({"spd": 30, "sta": 20}), "spd")
  check("unreadable stat keeps full value", unread, uncapped({"spd": 30}))

  # Lower of configured (1500) and on-screen (1050) wins.
  L.set_stat_headroom({"spd": 1000}, {"spd": 1050})
  check("screen cap beats config cap", L._stat_headroom["spd"], 50)
  L.set_stat_headroom({"spd": 1000}, {"spd": -1})
  check("unreadable screen cap falls back to config", L._stat_headroom["spd"], 500)

  # The burst multiplier applies to what lands, not to what is printed.
  L.set_stat_headroom({"spd": 900, "sta": 500})
  burst = L.gain_score(data({"spd": 30, "sta": 20}, {"burst": 1}), "spd")
  check("burst multiplies the landed gains only",
        burst, uncapped({"spd": 30}) * L.BURST_GAIN_MULTIPLIER)

  # Nothing left anywhere scores 0.0, which hands the decision back to the
  # support-count proxies rather than to a meaningless ordering.
  L.set_stat_headroom({"spd": 1500, "sta": 500, "pwr": 1200, "guts": 500, "wit": 1100})
  check("fully capped board scores zero",
        L.gain_score(data({"spd": 30, "pwr": 12}), "spd"), 0.0)

  # filter_by_stat_caps still agrees with the shared cap rule.
  kept = L.filter_by_stat_caps({"spd": data({}), "sta": data({})},
                               {"spd": 1499, "sta": 500})
  check("filter_by_stat_caps drops the capped stat", float(len(kept)), 1.0)

  # --- the proxy term also has to respect headroom --------------------
  #
  # filter_by_stat_caps only drops a stat once it is fully capped, so a
  # facility with a handful of usable points left kept its whole rainbow
  # score. In the Finale of a live run Speed sat at 1304 against a 1316 cap
  # and still scored 11.3, beating a wit facility worth 113 skill points.
  # set_stat_headroom takes current stats, not room; caps are spd 1500,
  # sta 500. So spd 1488 leaves twelve points, sta 0 leaves the lot.
  L.set_stat_headroom({"spd": 1488, "sta": 0})
  check("twelve points left scores near the floor",
        L.headroom_factor("spd"),
        L.HEADROOM_FLOOR + (1 - L.HEADROOM_FLOOR) * 12 / L.HEADROOM_FULL)
  check("plenty of room scores in full", L.headroom_factor("sta"), 1.0)
  check("an unread stat is not treated as capped", L.headroom_factor("nope"), 1.0)
  L.set_stat_headroom({"spd": 1500, "sta": 0})
  check("no room at all keeps the floor, not zero",
        L.headroom_factor("spd"), L.HEADROOM_FLOOR)
  check("the floor is above zero - bond, hints and skill points survive",
        1.0 if L.HEADROOM_FLOOR > 0 else 0.0, 1.0)

  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0

if __name__ == "__main__":
  sys.exit(main())
