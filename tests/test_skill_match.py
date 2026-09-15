"""Skill-name matching against the OCR the game actually produces.

Run with `python tests/test_skill_match.py` from the repo root. No easyocr and
no screenshots: the OCR strings below were copied verbatim out of a career's
log, so this pins the matcher against real damage rather than invented damage.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import core.skill as K            # noqa: E402
import core.masterdb as masterdb  # noqa: E402

failures = []

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

# Every one of these was logged by buy_skill during a real career.
OBSERVED = {
  "Sprint Comers @": "Sprint Corners",
  "Mediumn 3tralgmtaways U": "Medium Straightaways",
  "3traigmtaway Auept": "Straightaway Adept",
  "Rusning Gale:": "Rushing Gale!",
  "rtotessoi 0i Cunvatule": "Professor of Curvature",
  "Nesttam rtont nunnels": "Hesitant Front Runners",
  "Dudauea rtontumners": "Subdued Front Runners",
  "oprng Runner U": "Spring Runner",
  "Sumny Days U": "Sunny Days",
  "Outei Bweii": "Outer Swell",
  "Ramp UP": "Ramp Up",
  "Frepared t0 F aSS": "Prepared to Pass",
  "Up- Tempo": "Up-Tempo",
  "Gap Cioser": "Gap Closer",
  "NimDle Navigator": "Nimble Navigator",
  "Comer Adept U": "Corner Adept",
  "Fiustelea race Clasels": "Flustered Pace Chasers",
}

def test_data_loads():
  names = K.skill_names()
  ok("the skill list loads", len(names) > 300, str(len(names)))

def test_master_db_is_the_only_source():
  """master.mdb is complete and repatches with the game, so it is the source.

  Skipped rather than failed when the game is not installed here; the
  no-database path is tested separately below.
  """
  names = masterdb.text_data(masterdb.SKILL_NAMES)
  if not names:
    print("skip  master.mdb not present on this machine")
    return
  ok("master.mdb carries more names than the JSON", len(names) > 900, str(len(names)))
  ok("and skill_names uses it", len(K.skill_names()) == len(names))

  # The read that the JSON could not resolve, because it is not in it.
  scenario = K.canonical_skill("Louder! Tracen Cheer!")
  ok("a scenario skill missing from the JSON now resolves",
     scenario is not None and K.base_name(scenario) == K.base_name("Louder! Tracen Cheer!"),
     str(scenario))

def test_without_the_database_it_does_not_guess():
  """No master.mdb means no canonicalisation - deliberately, not by accident.

  data/skills.json was a fallback and was removed: it was 597 names short, and
  the first real screen tested contained one it lacked. The whole reason a poor
  match can be read as "the OCR is wrong" is that the database is complete, and
  a sometimes-incomplete source cannot carry that. So an absent database turns
  matching back into the plain comparison it was before, rather than quietly
  matching against a worse list.
  """
  saved_names, saved_env = K._skill_names, os.environ.get("UMA_MASTER_MDB")
  try:
    K._skill_names = None
    masterdb.reset()
    os.environ["UMA_MASTER_MDB"] = os.path.join("tests", "no-such-master.mdb")
    ok("no names are loaded without the database", K.skill_names() == [])
    ok("and nothing is canonicalised", K.canonical_skill("Gap Cioser") is None)

    # There is no second chance any more: the configured skill_list that the old
    # direct comparison ran against is gone, so without the database a row
    # simply cannot be identified at all.
    ok("not even a clean read resolves", K.canonical_skill("Gap Closer") is None)
  finally:
    if saved_env is None:
      os.environ.pop("UMA_MASTER_MDB", None)
    else:
      os.environ["UMA_MASTER_MDB"] = saved_env
    K._skill_names = saved_names
    K._by_base = None
    masterdb.reset()

def test_canonicalises_real_ocr():
  wrong = []
  for ocr, want in OBSERVED.items():
    got = K.canonical_skill(ocr)
    if got is None or K.base_name(got) != K.base_name(want):
      wrong.append((ocr, got, want))
  ok(f"all {len(OBSERVED)} logged reads canonicalise", not wrong, str(wrong))

def test_rank_glyph_handling():
  ok("the rank glyph is stripped", K.base_name("Sprint Corners ○") == "sprint corners")
  ok("both ranks reduce to one name",
     K.base_name("Sprint Corners ○") == K.base_name("Sprint Corners ◎"))

  # Names ending in a letter must survive: a naive trailing strip eats these.
  for name in ["Up-Tempo", "Passing Pro", "Swinging Maestro", "Trick (Front)",
               "I Can See Right Through You"]:
    ok(f"{name!r} is left alone", K.base_name(name) == name.lower(), K.base_name(name))

  # And nothing in the real list is rewritten by the strip except its rank.
  import re
  damaged = [n for n in K.skill_names()
             if K.base_name(n) != re.sub(r"\s*[○◎×]\s*$", "", n).lower()]
  ok("no real name is damaged by the strip", not damaged, str(damaged[:5]))

def test_a_close_second_is_refused():
  """The game ships near-identical pairs, so a top score is not enough.

  "risk-taker"/"risk-maker" score 90 against each other, and holding out every
  name in turn shows a missing skill matches its nearest neighbour at a median
  of 62.7 - straight through a floor of 60.

  Worth keeping in proportion: with master.mdb supplying 980 names, a skill
  genuinely absent from the list is now rare, so the margin is cheap insurance
  rather than a fix for something that was going wrong. It costs none of the
  real reads, which is the only reason it is here.
  """
  # Exact names still resolve: the twin sits far enough back.
  for name in ["Risk-Taker", "Risk-Maker", "Reignition", "Ignition"]:
    got = K.canonical_skill(name)
    if not any(K.base_name(n) == K.base_name(name) for n in K.skill_names()):
      continue
    ok(f"{name!r} still resolves exactly",
       got is not None and K.base_name(got) == K.base_name(name), str(got))

  # Deliberately not asserted here: that some invented string gets refused.
  # Truncations and UI text were tried and both pass the margin - "Risk-Ma"
  # scores 82 against Risk-Maker with 12 points of daylight, because a
  # truncation is closest to the thing it truncates. The margin guards against
  # a name with no right answer in the list, not against text that is not a
  # skill name at all, and the OCR box is anchored to a buy button so the
  # latter cannot appear there anyway.

  ok("the margin is what does it, not the floor",
     K.CANONICAL_MIN_MARGIN > 0 and K.CANONICAL_MIN_SCORE == 60)

def test_bases_are_folded_once():
  """Both ranks of a skill must collapse to one candidate.

  Otherwise the runner-up is the same skill's other rank, the margin is always
  0, and every match is refused.
  """
  bases = K.distinct_bases()
  ok("the fold loses the rank duplicates", len(bases) < len(K.skill_names()),
     f"{len(bases)} of {len(K.skill_names())}")
  ok("and a folded skill still resolves", K.canonical_skill("Corner Recovery") is not None)

def test_canonicalisation_is_what_survives():
  """is_skill_match is gone; canonical_skill is what the scan still uses.

  The configured skill_list was removed - core/skill_tiers.py drives buying now
  - so the fuzzy comparison against that list has no caller. What still matters
  is turning a mangled row into a real skill name, which is what the tier lookup
  and the aptitude test are both keyed on.
  """
  ok("is_skill_match is gone", not hasattr(K, "is_skill_match"))

  for ocr, want in [("Sprint Comers @", "Sprint Corners"),
                    ("rtotessoi 0i Cunvatule", "Professor of Curvature"),
                    ("Sprint Corners ◎", "Sprint Corners")]:
    got = K.canonical_skill(ocr)
    ok(f"{ocr!r} canonicalises", got is not None and K.base_name(got) == K.base_name(want),
       str(got))

def test_clean_reads_still_work():
  # Without the database nothing can be canonicalised, which is deliberate:
  # the "a bad score means bad OCR" reasoning needs a complete name list.
  saved = K._skill_names
  try:
    K._skill_names = []
    K._by_base = None
    ok("no canonicalisation without skill data", K.canonical_skill("Gap Closer") is None)
  finally:
    K._skill_names = saved
    K._by_base = None

def test_nothing_is_matched_from_nothing():
  ok("empty text canonicalises to nothing", K.canonical_skill("") is None)
  ok("whitespace canonicalises to nothing", K.canonical_skill("   ") is None)

for test in [test_data_loads, test_master_db_is_the_only_source,
             test_without_the_database_it_does_not_guess,
             test_canonicalises_real_ocr, test_rank_glyph_handling,
             test_a_close_second_is_refused, test_bases_are_folded_once,
             test_canonicalisation_is_what_survives, test_clean_reads_still_work,
             test_nothing_is_matched_from_nothing]:
  print(f"\n-- {test.__name__}")
  test()

print()
if failures:
  print(f"{len(failures)} FAILED: {failures}")
  sys.exit(1)
print("all checks passed")
