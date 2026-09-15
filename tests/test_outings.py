"""Outing chain prediction and the Recreation decision it feeds.

Run with `python tests/test_outings.py` from the repo root. core.state is
stubbed: importing the real one builds an easyocr Reader, which takes longer
than the whole check. The chain data itself is the real
data/events/support_card.json, so a change to that file is caught here.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
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
import core.logic as L      # noqa: E402
import core.outings as O    # noqa: E402

failures = []

# MOOD_LIST is AWFUL BAD NORMAL GOOD GREAT UNKNOWN, so NORMAL is 2 and GREAT 4.
NORMAL, GOOD, GREAT = 2, 3, 4

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def close(label, got, want, tol=1e-6):
  ok(label, abs(got - want) < tol, f"got {got:.4f}, want {want:.4f}")

def test_parse():
  # Two random variants are averaged, not summed.
  eff = O.parse_effects("Randomly either\nEnergy +40\nSpeed +10\nor\nor\nEnergy +20\nSpeed +0")
  close("random variants average", eff["energy"], 30.0)
  # "+5/+10" is a variable amount.
  eff = O.parse_effects("Speed +5/+10\nStraightaway Adept hint +1/+3")
  close("slash amount averages", eff["stats"]["spd"], 7.5)
  close("slash hint averages", eff["hints"], 2.0)
  # All stats spreads over the five.
  eff = O.parse_effects("All stats +7\nSkill points +37")
  ok("all stats spreads", eff["stats"] == {k: 7.0 for k in O.STAT_KEYS}, str(eff["stats"]))
  close("skill points read", eff["skill"], 37.0)
  # Maximum Energy raises the ceiling; it is not energy in the tank.
  eff = O.parse_effects("Maximum Energy +4\nEnergy +35")
  close("maximum energy is not energy", eff["energy"], 35.0)
  # Conditions and bond.
  eff = O.parse_effects("Energy +35\nTazuna Hayakawa bond +5\nHeal a negative status effect")
  ok("heal detected", eff["heals"] is True)
  close("bond read", eff["bond"], 5.0)
  # "2 random stats +10" is two stats at +10 each, and not a stat named "random".
  eff = O.parse_effects("Energy +30\nMood +1\n2 random stats +10")
  close("random stats totalled", eff["random_stats"], 20.0)
  ok("random stats are not a named stat", eff["stats"] == {}, str(eff["stats"]))

def test_chain():
  ok("only friend chains are indexed",
     set(O.load_chains()) == set(O.FRIEND_CARDS), str(sorted(O.load_chains())))

  O.reset()
  seen = []
  for _ in range(6):
    effects, label = O.next_outing()
    seen.append((effects["energy"], effects["hints"], effects["heals"], label))
    O.advance()
  ok("step 2 clears a condition", seen[1][2] is True, seen[1][3])
  ok("step 4 clears a condition", seen[3][2] is True, seen[3][3])
  ok("step 5 carries hints", seen[4][1] > 1.0, f"hints={seen[4][1]:.2f}")
  ok("early steps carry no hints", seen[0][1] == 0.0)
  # The badge disappears when the chain is spent and should_recreate is gated
  # on it, so an over-run depth is a tracking error, not a finished chain. It
  # clamps to the last step rather than pricing a karaoke session, because
  # under-valuing it would quietly stop the bot taking outings the badge says
  # are on offer.
  ok("an over-run depth clamps instead of collapsing",
     "uncertain" in seen[5][3] and seen[5][0] > 20, seen[5][3])
  ok("energy is nowhere near the old flat 20",
     min(s[0] for s in seen[:5]) > 20, f"min={min(s[0] for s in seen[:5]):.1f}")

  # A named branching step pins the card and overrides the counter.
  O.reset()
  O.advance()
  O.advance()
  O.advance()
  O.advance()
  ok("counter alone leaves the card unknown", O.steps_remaining() is None)
  ok("a chain event names the card", O.note_event("Memories of Cinema") == ("tazuna-hayakawa", 3))
  ok("the name overrides the counter", O.steps_remaining() == 2, str(O.steps_remaining()))
  _, label = O.next_outing()
  ok("prediction follows the identified card", "tazuna-hayakawa step 4" in label, label)
  ok("an unrelated name is ignored", O.note_event("Third Place in the Yayoi Sho") is None)

def test_panel():
  """The Recreation panel states the position outright, so it wins."""
  O.reset()
  ok("nothing measured at the start of a career", O.measured() is False)

  ok("the panel names the card and the step",
     O.set_position("Riko Kashimoto", 1) == ("riko-kashimoto", 1))
  ok("measured is set", O.measured() is True)
  ok("steps remaining follows the panel", O.steps_remaining() == 4, str(O.steps_remaining()))
  _, label = O.next_outing()
  ok("prediction uses the named card", "riko-kashimoto step 2" in label, label)

  # The name is OCR'd, so it has to survive the usual mangling.
  ok("an OCR-mangled name still matches",
     O.set_position("Rlko Kashlmoto", 3) == ("riko-kashimoto", 3))

  # A measured position overrides a counter that drifted - an outing that was
  # opened and backed out of still moved the counter.
  O.reset()
  O.advance()
  O.advance()
  O.set_position("Tazuna Hayakawa", 0)
  ok("the panel overrides a drifted counter", O.steps_remaining() == 5, str(O.steps_remaining()))
  _, label = O.next_outing()
  ok("a corrected position predicts step 1", "tazuna-hayakawa step 1" in label, label)

  # An unreadable card name still leaves the step count worth having.
  O.reset()
  ok("an unknown card name is not guessed at",
     O.set_position("Some Unknown Friend", 2) is None)
  _, label = O.next_outing()
  ok("but its step count is kept", "step 3" in label, label)

  # Nonsense from a failed read must not move anything.
  O.reset()
  ok("a negative step count is ignored", O.set_position("Riko Kashimoto", -1) is None)
  ok("and nothing was measured", O.measured() is False)

# Exactly what read_boxes returned for the Log entry of one real Riko step-5
# outing, mangling and all. Kept verbatim: the parser has to cope with what the
# OCR actually produces, not with tidied-up text.
RIKO_STEP5_LOG = [
  "Energy recovered by 30_",
  "Mood remains Great:",
  "Stamina went up by 12.",
  "Guts went up by 12.",
  "Gained 3 hint levells) for Rushing Galel",
  "Friendship with Riko Kashimoto is maxed",
  "out",
]

def test_readback():
  """The Log says what an outing actually did; the prediction has to match it."""
  actual = O.parse_log_effects(RIKO_STEP5_LOG)
  ok("the log parses at all", actual is not None)
  close("energy read from the log", actual["energy"], 30.0)
  close("stamina read from the log", actual["stats"]["sta"], 12.0)
  close("guts read from the log", actual["stats"]["guts"], 12.0)
  close("hint levels read through the OCR mangling", actual["hints"], 3.0)
  close("\"Mood remains Great\" is no change", actual["mood"], 0.0)

  # The two Riko cards give different numbers for the same step (+24 and +30),
  # and the step itself has a random roll, so the prediction is a mean with a
  # spread. A readback is judged against the spread; against the mean alone it
  # would report a mismatch on a perfectly normal outcome.
  O.reset()
  O.set_position("Riko Kashimoto", 4)
  effects, label = O.next_outing()
  lo, hi = effects["range"]["energy"]
  ok("the energy spread covers both card versions", (lo, hi) == (24.0, 30.0), f"{lo}-{hi}")
  lo, hi = effects["range"]["hints"]
  ok("the hint spread covers both halves of the roll", (lo, hi) == (1.0, 3.0), f"{lo}-{hi}")

  # The comparison is the energy bar and nothing else. Picking the right block
  # out of the Log proved undependable - it has come back with dialogue and
  # with an unrelated goal event - so the Log is recorded, not judged.
  O.expect_readback(effects, label, energy_before=50.0, energy_headroom=50.0)
  ok("a readback is pending", O.pending_readback() is True)
  confirmed = O.confirm_outing(RIKO_STEP5_LOG, energy_after=77.0)
  ok("a bar move inside the spread confirms", confirmed is not None)
  ok("and the pending readback is cleared", O.pending_readback() is False)

  # A genuinely wrong outcome still has to be caught.
  O.reset()
  O.set_position("Riko Kashimoto", 4)
  O.expect_readback(*O.next_outing(), energy_before=50.0, energy_headroom=50.0)
  wrong = O.confirm_outing(["Energy recovered by 3."], energy_after=52.0)
  close("a wrong outcome is still measured", wrong["energy"], 2.0)

  # An unreadable bar says nothing rather than inventing a delta. The
  # Recreation panel covers the energy bar, so check_energy_level can return
  # -1 exactly when the outing starts; treating that as a number once turned a
  # 30-energy step into a claimed 66.
  O.reset()
  O.set_position("Riko Kashimoto", 4)
  O.expect_readback(*O.next_outing(), energy_before=-1, energy_headroom=0)
  ok("an unreadable bar reading is refused",
     O.confirm_outing(RIKO_STEP5_LOG, energy_after=65.0) is None)

  # ...and so does no reading at all.
  O.reset()
  O.set_position("Riko Kashimoto", 4)
  O.expect_readback(*O.next_outing())
  ok("no bar reading means no verdict", O.confirm_outing(RIKO_STEP5_LOG) is None)

  # Only the newest block counts: the Log keeps a scrollback and summing it all
  # would add several turns of results together.
  older = ["Speed went up by 43.", "Friendship with Silence Suzuka went up by 7.",
           "", "Trained on the track.", "", "", "",
           "Energy recovered by 35.", "Mood remains Great."]
  newest = O.parse_log_effects(older)
  close("only the newest block is taken", newest["energy"], 35.0)
  ok("older entries are not summed in", "spd" not in newest["stats"], str(newest["stats"]))

  # Nothing to parse must not look like a zero-value outing.
  ok("an unreadable log returns nothing",
     O.parse_log_effects(["Now Loading...", "Team Showdown"]) is None)

def test_energy():
  # Worth more when scarce than when nearly full.
  ok("energy is worth more when scarce",
     L.energy_points(10, 100) > L.energy_points(90, 100),
     f"{L.energy_points(10, 100):.3f} vs {L.energy_points(90, 100):.3f}")
  # Spill is worth nothing.
  close("spill is not counted", L.energy_value(50, 90, 100),
        10 * L.energy_points(90, 100))
  # A cost is paid in full, not clipped.
  close("a cost is not clipped", L.energy_value(-25, 90, 100),
        -25 * L.energy_points(90, 100))
  # Mood cannot go past GREAT.
  close("mood clips at GREAT", L.mood_value(2, GREAT, NORMAL), 0.0)
  ok("mood is worth more below target",
     L.mood_value(1, NORMAL, GOOD) > L.mood_value(1, GREAT - 1, NORMAL))

def decide(**kw):
  args = dict(value=2.0, resting=False, energy_level=60, max_energy=100,
              mood_index=GOOD, mood_target=NORMAL, outing_available=True,
              debuffed=False)
  args.update(kw)
  return L.should_recreate(args["value"], args["resting"], args["energy_level"],
                           args["max_energy"], args["mood_index"], args["mood_target"],
                           args["outing_available"], args["debuffed"])

def test_decision():
  L.set_stat_headroom({"spd": 900, "sta": 400, "pwr": 800, "guts": 400, "wit": 900})

  O.reset()
  ok("no badge, no outing", decide(outing_available=False) is None)
  ok("unreadable training gains keep the training", decide(value=None) is None)
  ok("a full tank and a fair training beats an outing",
     decide(energy_level=98, value=2.0) is None)
  ok("a strong training beats an outing", decide(value=8.0) is None)

  # Resting at low energy: a rest returns more than an outing does.
  ok("a rest beats an outing on an empty tank",
     decide(resting=True, value=None, energy_level=15) is None)

  # Step 5 carries a hint level and skill points; a mediocre training should lose.
  O.reset()
  for _ in range(4):
    O.advance()
  step5 = decide(value=1.5, energy_level=55)
  ok("the last chain step beats a mediocre training", step5 is not None, str(step5))

  # ...and the same turn against a strong training should not.
  ok("even the last step loses to a strong training",
     decide(value=9.0, energy_level=55) is None)

  # A step that clears a condition, while a condition is showing.
  O.reset()
  O.advance()          # next is step 2, which heals
  healed = decide(value=2.5, debuffed=True, energy_level=70)
  ok("a healing step is taken while debuffed", healed is not None, str(healed))
  ok("the same step is not taken when nothing is wrong",
     decide(value=2.5, debuffed=False, energy_level=70) is None)

  # A spent chain cannot reach this code at all: the badge goes away with the
  # last step, and no badge means should_recreate returns before pricing
  # anything. That is the only thing keeping an outing off the board once the
  # chain is done.
  O.reset()
  for _ in range(8):
    O.advance()
  ok("a spent chain is stopped by the badge, not by the price",
     decide(value=2.0, energy_level=60, outing_available=False) is None)
  ok("and an over-run depth still prices as a real step when the badge is up",
     decide(value=0.2, energy_level=45) is not None)

def test_unlock():
  """The choice that hands over a friend card's whole outing chain.

  Both option lists below are the exact lines easyocr read off the panel in
  career 5 ("Ivl" for "Lvl" and all), and the scores they used to get are in
  the log beside them: #1=94, #2=159. The bot took #2 in six careers running,
  so Light Hello's chain was never unlocked and a whole Grand Concert career
  went by without a single outing.
  """
  import core.event_effects as EE

  unlock = EE.unlock_value("Light Hello")
  ok("unlocking Light Hello's chain is worth something", unlock > 0,
     f"scored {unlock:.0f}")
  # Priced on the mood/stats/hints the chain pays, never its energy: counting
  # that would let an unlock outbid every other option on any panel.
  chain_energy = sum(s["energy"] for s in O.chain_steps("Light Hello"))
  ok("and is not priced on the chain's energy", unlock < chain_energy * 2.0,
     f"unlock {unlock:.0f} vs {chain_energy * 2.0:.0f} if energy counted")

  keeps_chain = ["Friendship with Light Hello +5", "Energy +24", "Mood +1",
                 "Speed +9", "Guts +9", "Unlock recreation with Light Hello"]
  loses_chain = ["Friendship with Light Hello -5", "Wit +40", "Skill Pts +40",
                 "No Hint Lvls", "Maverick hint Ivl +5"]
  pick, detail = EE.best_choice([keeps_chain, loses_chain])
  ok("the option unlocking recreation wins the panel", pick == 1, detail)

  # An OCR'd name that matches no friend still has to unlock: which card it is
  # changes the price, never whether the chain is worth having.
  ok("an unreadable card name still scores the unlock",
     EE.unlock_value("Lghi Helo") > 0)
  ok("and a line with no name at all still scores",
     EE.score_line("Unlock recreation")[1] is True)

def main():
  for test in (test_parse, test_chain, test_panel, test_readback, test_energy,
               test_decision, test_unlock):
    print(f"--- {test.__name__}")
    test()
  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0

if __name__ == "__main__":
  sys.exit(main())
