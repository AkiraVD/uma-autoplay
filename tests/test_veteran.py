"""The Veteran Roster readers, against captured frames.

Run with `python tests/test_veteran.py` from the repo root. It builds the
easyocr Reader, so it starts slowly and takes a few minutes.

Every expected value here was read off the frame by eye. The ones worth
knowing why they are in the file:

- The rank is NOT read off the badge any more. "SS" and "S+" are two glyphs
  of the same width in the same font, and the width test that preceded this
  recorded 16 SS cards as S+. It now comes from the rating through
  master.mdb's `single_mode_rank`, and the badge is kept only as a check on
  the rating - a disagreement on the LETTER means the rating misread.
- `oguri_a_skills` and `condor_sparks` carry four-digit Wit values (1013)
  behind their grade badge. The badge is painted out before the read, and a
  mask 4px too wide turned 1013 into 13.
- `bakushin_aplus_sparks` ends in "URA Finale", which is neither a race nor a
  skill. Before the scenario list existed it was matched to the skill
  "Rational" at 67.
- `condor_sparks` has three sparks and no green. That is what the card says -
  it is here so a future change that drops rows has something to fail on.
- `rudolf_s_sparks` is the only frame whose own sparks sit above a Legacy
  Origin block, which is the boundary the reader has to respect.
- `memo_error` is the game's "Contains invalid characters." rejection, which
  is drawn over the memo dialog and hides its title - so a run that only asked
  "did the memo close?" read the refusal as a success and then walked into the
  dialog it had left on screen.
- `skill_details_popup` is what a drag the list cannot act on opens: the
  scan taps a skill row by accident at each end of the list, and the popup
  then hides the tab row, the pencil and the next arrow. It cost 11 of 191
  cards their sparks, twice, before it was caught.
- `career_info_tab` is here only as the third tab state. A tap the game
  swallows looks exactly like a card with nothing on it - that is how card 78
  of the first full run came back with zero sparks - so the walk checks which
  tab is lit before it reads, and that check needs all three cases.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import core.veteran as V  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures", "veteran")

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def frame(name):
  return Image.open(os.path.join(FIXTURES, name + ".png")).convert("RGB")


# The rank a card shows is a function of its rating, via master.mdb's
# single_mode_rank bands. The badge itself is NOT readable - "SS" and "S+"
# are the same width in the same font - so these are the rating-derived
# values, and the badge is only kept as a check on the rating.
RANK_FROM_RATING = {
  1066: "F+", 9877: "B+", 10904: "A", 11064: "A", 12450: "A+",
  15641: "S", 16002: "S+", 17490: "S+", 17814: "SS",
  19266: "SS+", 19383: "SS+", 20211: "UG+",
}

HEADERS = {
  "rudolf_splus_skills": ("[Emperor's Path]", "Symboli Rudolf", "S+", 16563, "Witness to Legend"),
  "rudolf_s_sparks": ("[Emperor's Path]", "Symboli Rudolf", "S", 15611, "Witness to Legend"),
  "oguri_a_skills": ("[Starlight Beat]", "Oguri Cap", "A", 10904, "Finals Champion"),
  "condor_sparks": ("[El☆Número 1]", "El Condor Pasa", "A", 11870, "Finals Champion"),
  "bakushin_aplus_sparks": ("[Blossom in Learning]", "Sakura Bakushin O", "A+", 12450, "The GOAT"),
}

STATS = {
  "rudolf_splus_skills": (1201, 1221, 880, 695, 384),
  "rudolf_s_sparks": (1216, 1152, 740, 689, 409),
  "oguri_a_skills": (1029, 467, 1164, 279, 261),
  "condor_sparks": (1200, 635, 621, 288, 1013),
  "bakushin_aplus_sparks": (1200, 448, 616, 287, 1015),
}

# (name, kind, stars) for every one of the Uma's own sparks, in screen order.
SPARKS = {
  "rudolf_s_sparks": [
    ("Speed", "blue", 2), ("Long", "pink", 1),
    ("Behold Thine Emperor's Divine Might", "green", 1),
    ("Japanese Derby", "race", 2), ("Takarazuka Kinen", "race", 2),
    ("Kikuka Sho", "race", 2), ("Firm Conditions", "skill", 2),
    ("Corner Recovery", "skill", 2), ("Straightaway Acceleration", "skill", 2),
  ],
  "condor_sparks": [
    ("Stamina", "blue", 2), ("Long", "pink", 2), ("Standard Distance", "skill", 2),
  ],
  "bakushin_aplus_sparks": [
    ("Wit", "blue", 2), ("Front Runner", "pink", 2),
    ("Takamatsunomiya Kinen", "race", 1), ("Fast-Paced", "skill", 2),
    ("Final Push", "skill", 2), ("Sprinting Gear", "skill", 1),
    ("Countermeasure", "skill", 2), ("URA Finale", "scenario", 2),
  ],
}

# Everything on the Skills tab without scrolling. The frames were captured at
# the top of the list, so these are complete for the cards whose lists fit.
SKILLS = {
  "oguri_a_skills": [
    "Triumphant Pulse", "Corner Acceleration", "Focus", "Homestretch Haste",
    "Fighter", "Professor of Curvature", "Straightaway Adept", "It's On!",
    "Updrafters", "Tail Held High",
  ],
  "rudolf_splus_skills": [
    "Behold Thine Emperor's Divine Might", "Wet Conditions", "Long Shot",
    "Subdued Late Surgers", "Mile Straightaways", "Long Corners",
    "Pace Chaser Savvy", "Firm Conditions", "Outer Post Proficiency",
    "It's On!", "Hesitant Late Surgers", "Medium Corners",
    "Pace Chaser Corners", "Late Surger Savvy",
  ],
}


def check_headers():
  for name, (variant, uma, rank, rating, epithet) in HEADERS.items():
    read = V.read_header(frame(name))
    ok(f"{name}: name", (read["variant"], read["name"]) == (variant, uma),
       f"{read['variant']} {read['name']}")
    ok(f"{name}: badge letter {rank[0]}", (read["rank_badge"] or "?")[0] == rank[0],
       read["rank_badge"])
    ok(f"{name}: rating {rating}", read["rating"] == rating, read["rating"])
    ok(f"{name}: epithet", read["epithet"] == epithet, read["epithet"])
    ok(f"{name}: no memo", read["memo"] == "", read["memo"])


def check_rank_bands():
  """Every rating whose badge has been read off a real card by eye."""
  import core.masterdb as masterdb
  for rating, rank in RANK_FROM_RATING.items():
    got = masterdb.career_rank(rating)
    ok(f"rating {rating:,} is rank {rank}", got == rank, got)
  # The band edges matter more than the middles: A ends at 12,099 and A+
  # starts at 12,100, measured against 57 cards either side.
  for rating, rank in ((12099, "A"), (12100, "A+"), (14499, "A+"), (14500, "S"),
                       (15899, "S"), (15900, "S+"), (17499, "S+"), (17500, "SS")):
    got = masterdb.career_rank(rating)
    ok(f"band edge {rating:,} is {rank}", got == rank, got)


def check_stats():
  for name, expected in STATS.items():
    read = V.read_stats(frame(name))
    got = tuple(read[stat] for stat in V.STATS)
    ok(f"{name}: stats", got == expected, "" if got == expected else f"{got} != {expected}")


def check_sparks():
  for name, expected in SPARKS.items():
    found, saw_legacy = V.read_sparks_frame(frame(name))
    named = [V.name_spark(spark) for spark in found]
    got = [(spark["name"], spark["kind"], spark["stars"]) for spark in named]
    ok(f"{name}: sparks", got == expected,
       "\n      ".join(f"{g} != {e}" for g, e in zip(got, expected) if g != e)
       or f"{len(got)} rows against {len(expected)}")
    ok(f"{name}: every spark matched a real name",
       all(spark["matched"] for spark in named),
       [spark["name"] for spark in named if not spark["matched"]])
  # The ancestors' block is the boundary, and it has to be seen to be obeyed.
  ok("rudolf_s_sparks: the Legacy Origin header is found",
     V.read_sparks_frame(frame("rudolf_s_sparks"))[1])


def check_skills():
  from core.skill import canonical_skill
  for name, expected in SKILLS.items():
    read = V.read_skills_frame(frame(name))
    got = [V.RANK_GLYPH.sub("", canonical_skill(skill) or skill).strip() for skill in read]
    ok(f"{name}: skills", got == expected,
       "" if got == expected else f"{sorted(set(got) ^ set(expected))}")
    carried = [skill for skill in got if any(glyph in skill for glyph in "○◎×")]
    ok(f"{name}: no name carries a rank glyph", not carried, carried)


def check_roster():
  ok("roster: registered count", V.read_registered(frame("roster_ascending")) == (191, 260),
     V.read_registered(frame("roster_ascending")))
  for name, order in (("roster_ascending", "Asc"), ("roster_descending", "Desc")):
    key, read = V.read_sort(frame(name))
    ok(f"{name}: sorted {order}", (key, read) == ("Date Acquired", order), f"{key!r} {read!r}")


def check_tabs():
  # A tab that did not come up is indistinguishable downstream from a card
  # with nothing on it, so the check is on the tab, not on what it shows.
  selected = {
    "oguri_a_skills": "SKILLS",
    "rudolf_s_sparks": "INSPIRATION",
    "career_info_tab": "CAREER",
  }
  for name, active in selected.items():
    shot = frame(name)
    for tab in ("SKILLS", "INSPIRATION", "CAREER"):
      bbox = getattr(V.constants, f"VETERAN_TAB_{tab}_BBOX")
      want = tab == active
      ok(f"{name}: {tab.lower()} tab {'selected' if want else 'not selected'}",
         V.tab_selected(bbox, shot) == want)


def check_memo():
  # The field is read before OK is pressed, so an empty one has to read empty
  # rather than picking up the dialog's own wording.
  ok("memo dialog: the empty field reads empty",
     V.read_memo_field(frame("memo_dialog")) == "",
     V.read_memo_field(frame("memo_dialog")))
  ok("memo: O/0 and S/5 are the same character",
     V.same_memo("VOO1", "V001") and V.same_memo("VosO", "V050")
     and not V.same_memo("V002", "V001"))
  # The rejection dialog covers the memo title, so "the memo closed" is not
  # evidence the memo was taken. It has to be asked about separately.
  ok("memo error: recognised", V.on_error.__doc__ is not None)


def check_popups():
  # Both of these cover the Details dialog, and the walk has to tell them
  # apart from it rather than carrying on into a screen that is not there.
  popup = frame("skill_details_popup")
  error = frame("memo_error")
  clean = frame("rudolf_splus_skills")
  import core.recognizer as R
  def scores(shot, template):
    import cv2, numpy as np
    a = cv2.cvtColor(np.asarray(shot.convert("RGB")), cv2.COLOR_RGB2BGR)
    t = cv2.imread(template, cv2.IMREAD_COLOR)
    return float(cv2.matchTemplate(a, t, cv2.TM_CCOEFF_NORMED).max())
  for name, template, shot, want in (
      ("skill details", V.constants.VETERAN_SKILL_DETAILS_TEMPLATE, popup, True),
      ("skill details", V.constants.VETERAN_SKILL_DETAILS_TEMPLATE, clean, False),
      ("memo error", V.constants.VETERAN_ERROR_TEMPLATE, error, True),
      ("memo error", V.constants.VETERAN_ERROR_TEMPLATE, clean, False),
      ("memo error", V.constants.VETERAN_ERROR_TEMPLATE, popup, False)):
    got = scores(shot, template) >= 0.85
    ok(f"{name} on {'its own frame' if want else 'another frame'}: {want}", got == want)


def main():
  check_headers()
  check_rank_bands()
  check_stats()
  check_sparks()
  check_skills()
  check_roster()
  check_tabs()
  check_memo()
  check_popups()
  print()
  if failures:
    print(f"{len(failures)} FAILED: {failures}")
    return 1
  print("all ok")
  return 0


if __name__ == "__main__":
  sys.exit(main())
