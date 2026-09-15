"""The Choices panel reader and scorer, against captured frames.

Run with `python tests/test_choices_panel.py` from the repo root. Imports the
real core.state, so it builds an easyocr Reader and is slow to start - the
panel is OCR'd and there is no honest way to stub that.

Fixtures in tests/fixtures/choices/:
  two_options_simple.png    "The King Knows No Exhaustion": Energy/Mood vs Power
  two_options_branched.png  an injury event whose options split into Branch 1/2
  event_no_panel.png        an event with the Log showing instead of the panel
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
# Keep the live career's log out of this, the same as the other suites.
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.state as S                    # noqa: E402
import core.event_effects as EF           # noqa: E402

FIXTURES = os.path.join("tests", "fixtures", "choices")
SIMPLE = os.path.join(FIXTURES, "two_options_simple.png")
BRANCHED = os.path.join(FIXTURES, "two_options_branched.png")
NO_PANEL = os.path.join(FIXTURES, "event_no_panel.png")

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def test_reads_a_simple_panel():
  choices = S.read_choice_effects(Image.open(SIMPLE))
  ok("two options are found", len(choices) == 2, str(len(choices)))
  ok("option 1 reads its two effects", choices[0] == ["Energy +5", "Mood +1"],
     repr(choices[0]))
  ok("option 2 reads its one effect", choices[1] == ["Power +10"], repr(choices[1]))

def test_reads_a_branched_panel():
  choices = S.read_choice_effects(Image.open(BRANCHED))
  ok("two options are found on the branched panel", len(choices) == 2, str(len(choices)))
  ok("both branches of option 1 are read",
     sum(1 for l in choices[0] if l.lower().startswith("branch")) == 2, repr(choices[0]))
  # The minus signs are what the contrast pass exists for: a dropped one turns
  # a penalty into nothing, which is the one error that is not safe.
  ok("the negative amounts keep their signs",
     all("Mood -3" in l or "Mood" not in l for l in choices[0]), repr(choices[0]))
  ok("the condition line is read",
     any("Practice Poor" in l for l in choices[0]), repr(choices[0]))

def test_no_panel_reads_as_nothing():
  # An event showing the Log rather than the panel must read as "no panel", not
  # as an event whose options all do nothing - those lead to opposite actions.
  choices = S.read_choice_effects(Image.open(NO_PANEL))
  ok("a frame without the panel yields no options", choices == [], repr(choices))
  index, reason = EF.best_choice(choices)
  ok("and scores to 0 so the caller falls back", index == 0, f"{index} ({reason})")

def test_branches_are_averaged_not_summed():
  # Two branches each granting +10 is worth +10, not +20 - the game picks one.
  one = EF.score_choice(["Energy +10"])
  two = EF.score_choice(["Branch 1", "Energy +10", "Branch 2", "Energy +10"])
  ok("two identical branches score the same as one", abs(one - two) < 1e-6,
     f"{one} vs {two}")

  # And a penalty in only one branch must be worth half of a certain one.
  certain = EF.score_choice(["Become Practice Poor"])
  half = EF.score_choice(["Branch 1", "Energy +0", "Branch 2", "Become Practice Poor"])
  ok("a penalty in one branch of two costs half", abs(half - certain / 2) < 1e-6,
     f"{half} vs {certain / 2}")

def test_unnamed_attribute_phrasings():
  weight = EF.unknown_stat_weight()
  one = EF.score_choice(["Previously trained attribute -10"])
  ok("a previously trained attribute counts as one stat",
     abs(one - (-10 * weight)) < 1e-6, str(one))

  two = EF.score_choice(["Random 2 attribute(s) -10"])
  ok("random 2 attributes counts as two stats", abs(two - (-20 * weight)) < 1e-6, str(two))
  ok("and is therefore worth twice one attribute", abs(two - 2 * one) < 1e-6)

def test_ocr_damage_is_repaired():
  # Both seen in real reads off this panel.
  ok("a split sign is rejoined",
     EF.score_choice(["Energy + 10"]) == EF.score_choice(["Energy +10"]))
  ok("a mangled attribute(s) still parses",
     EF.score_choice(["Random 2 attributels) - 10"]) == EF.score_choice(["Random 2 attribute(s) -10"]))

def test_scores_pick_the_better_option():
  simple = S.read_choice_effects(Image.open(SIMPLE))
  index, reason = EF.best_choice(simple)
  ok("the simple event picks an option at all", index in (1, 2), f"{index} ({reason})")

  branched = S.read_choice_effects(Image.open(BRANCHED))
  index, reason = EF.best_choice(branched)
  # Option 2 takes Practice Poor for certain and gains no Energy, so it is
  # strictly worse than option 1 whatever the weights are.
  ok("the injury event prefers healing up", index == 1, f"{index} ({reason})")

  scores = [EF.score_choice(lines) for lines in branched]
  ok("both injury options score negative", all(s < 0 for s in scores), str(scores))
  ok("and toughing it out scores worse", scores[1] < scores[0], str(scores))

def test_green_headings_elsewhere_are_not_choices():
  """The gate that stops any green section bar reading as an option.

  Career Profile has four green headings and the Log has one per scenario
  section. Both sit in the same column as the Choices panel, and without the
  title check they read as confident options saying "legacy 1 legacy 2".
  """
  for name in ["career_profile.png", "log_sections.png"]:
    path = os.path.join(FIXTURES, name)
    if not os.path.exists(path):
      continue
    img = Image.open(path)
    ok(f"{name} is not taken for a Choices panel",
       not S.choices_panel_open(img))
    ok(f"{name} yields no options", S.read_choice_effects(img) == [])

    # The headers themselves are still there - the point is that the title gate
    # rejects the frame before they are ever read.
    ok(f"{name} does have green bars that would have parsed",
       len(S.find_choice_headers(img)) > 0, str(len(S.find_choice_headers(img))))

def test_hint_and_cure_phrasings():
  # Seen live: the skill name in front means the subject ends in "lvl", so the
  # generic parser priced a hint at 1 point a level instead of 12.
  one = EF.score_choice(["Medium Corners Hint Lvl +1"])
  ok("a hint level is worth more than a stat point", one == EF.HINT_POINTS, str(one))
  two = EF.score_choice(["Unyielding Spirit Hint Lvl +2"])
  ok("two hint levels are worth twice one", abs(two - 2 * one) < 1e-6, str(two))
  # easyocr reads "Lvl" as "Ivl" about half the time.
  ok("the Ivl misread still scores",
     EF.score_choice(["Outer Swell Hint Ivl +1"]) == one)

  cure = EF.score_choice(["Randomly cures 1 bad condition(s)"])
  ok("a cure is worth something", cure > 0, str(cure))
  ok("and two cures twice as much",
     abs(EF.score_choice(["Randomly cures 2 bad condition(s)"]) - 2 * cure) < 1e-6)

  # A hint level of zero is a real line and really is worth nothing.
  ok("no hint levels scores zero", EF.score_choice(["Hint Lvl 0"]) == 0.0)

def test_an_empty_panel_is_not_a_choice():
  ok("no options at all scores 0", EF.best_choice([])[0] == 0)
  ok("options with no effect lines score 0", EF.best_choice([[], []])[0] == 0)
  ok("a single option needs no scoring", EF.best_choice([["Energy +5"]])[0] == 1)

for test in [test_reads_a_simple_panel, test_reads_a_branched_panel,
             test_no_panel_reads_as_nothing, test_branches_are_averaged_not_summed,
             test_unnamed_attribute_phrasings, test_ocr_damage_is_repaired,
             test_green_headings_elsewhere_are_not_choices,
             test_hint_and_cure_phrasings,
             test_scores_pick_the_better_option, test_an_empty_panel_is_not_a_choice]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
