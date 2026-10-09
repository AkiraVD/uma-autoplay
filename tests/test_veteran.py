"""The Veteran Roster readers, against captured frames.

Run with `python tests/test_veteran.py` from the repo root. It builds the
easyocr Reader, so it starts slowly and takes a few minutes.

Every expected value here was read off the frame by eye. The ones worth
knowing why they are in the file:

- `rudolf_splus_skills` is the "+" case. The rank badge's plus is inferred
  from how wide the ink is, not read, so a frame with one and frames without
  have to stay on opposite sides of the threshold.
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
    ok(f"{name}: rank {rank}", read["rank"] == rank, read["rank"])
    ok(f"{name}: rating {rating}", read["rating"] == rating, read["rating"])
    ok(f"{name}: epithet", read["epithet"] == epithet, read["epithet"])
    ok(f"{name}: no memo", read["memo"] == "", read["memo"])


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


def check_memo():
  # The field is read before OK is pressed, so an empty one has to read empty
  # rather than picking up the dialog's own wording.
  ok("memo dialog: the empty field reads empty",
     V.read_memo_field(frame("memo_dialog")) == "",
     V.read_memo_field(frame("memo_dialog")))
  ok("memo: O and 0 are the same character",
     V.same_memo("VOO1", "V001") and not V.same_memo("V002", "V001"))


def main():
  check_headers()
  check_stats()
  check_sparks()
  check_skills()
  check_roster()
  check_memo()
  print()
  if failures:
    print(f"{len(failures)} FAILED: {failures}")
    return 1
  print("all ok")
  return 0


if __name__ == "__main__":
  sys.exit(main())
