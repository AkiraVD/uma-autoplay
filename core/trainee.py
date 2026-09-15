"""The trainee's own numbers, from the game's master.mdb.

Writing a config for a new trainee meant looking her up on a guide and typing
the answers in - and a guide got Meisho Doto's Arima Kinen condition wrong,
which is the sort of error that only shows up when a career ends on it. Her
aptitudes, growth rates and intended running style are all in master.mdb, so
`trainee` in the config names her and this reads them.

What it is **not**: the career goal list. "Place top 3 in Nikkei Shinshun Hai"
is composed at runtime from a race and a condition, and is not in text_data in
any form I could find - category 290 looks like it but holds epithet objectives
("Attain at least 600 Stamina"). So `race_schedule` stays a human decision.

This only warns. A config that disagrees with the trainee is usually a mistake
worth catching before a career is spent on it, but running an unusual style on
purpose is the user's call, not the bot's.

  python -m core.trainee "Kitasan Black"
"""
import os
import sqlite3
import sys
from pathlib import Path

from utils.log import info, warning
import core.masterdb as masterdb

MDB_PATH = Path(masterdb.master_path())

# Category 4 is the trainee card's full "[Title] Name" - what Trainee Select
# shows - and category 6 is just the character. **Match on 4.** A character can
# have several cards with different growth: Meisho Doto's base is sta +20% /
# guts +10% while [Dot-o'-Lantern] is pwr +15% / wit +15%, and matching on the
# character name silently returned the base one's numbers.
CAT_CARD_NAME = 4
CAT_CHARA_NAME = 6

GRADE = {1: "G", 2: "F", 3: "E", 4: "D", 5: "C", 6: "B", 7: "A", 8: "S"}
# card_data.running_style, matching core.skill_score.RUNNING_STYLES.
STYLE = {1: "front", 2: "pace", 3: "late", 4: "end"}

APTITUDE_COLUMNS = [
  ("turf", "proper_ground_turf"), ("dirt", "proper_ground_dirt"),
  ("sprint", "proper_distance_short"), ("mile", "proper_distance_mile"),
  ("medium", "proper_distance_middle"), ("long", "proper_distance_long"),
  ("front", "proper_running_style_nige"), ("pace", "proper_running_style_senko"),
  ("late", "proper_running_style_sashi"), ("end", "proper_running_style_oikomi"),
]

GROWTH_COLUMNS = [("spd", "talent_speed"), ("sta", "talent_stamina"),
                  ("pwr", "talent_pow"), ("guts", "talent_guts"), ("wit", "talent_wiz")]

# Below this an aptitude is a real handicap rather than a preference.
USABLE_GRADE = 6  # B

def _connect():
  if not MDB_PATH.exists():
    return None
  try:
    return sqlite3.connect(f"file:{MDB_PATH.as_posix()}?mode=ro", uri=True)
  except sqlite3.Error:
    return None

def find(needle):
  """[(card_id, "[Title] Name")] for trainee cards matching `needle`.

  Matched against the full title, so "[Dot-o'-Lantern] Meisho Doto" and plain
  "Meisho Doto" are distinguishable - a bare character name matches every
  variant she has, and the caller decides rather than this picking one.
  """
  con = _connect()
  if not con:
    return []
  like = f"%{needle.lower()}%"
  rows = con.execute(
    'SELECT c.id, t.text FROM card_data c JOIN text_data t '
    ' ON t.category=? AND t."index"=c.id '
    'WHERE lower(t.text) LIKE ? ORDER BY c.id', (CAT_CARD_NAME, like)).fetchall()
  con.close()
  return rows

def _build(card_id, chara_id, name, style_id, rarity, growth_values, apt_values):
  return {
    "id": card_id, "chara_id": chara_id, "name": name,
    "style": STYLE.get(style_id, str(style_id)),
    "rarity": rarity,
    "growth": {key: value for (key, _), value in zip(GROWTH_COLUMNS, growth_values) if value},
    "aptitude": {key: value for (key, _), value in zip(APTITUDE_COLUMNS, apt_values)},
  }

def catalog():
  """Every trainee card, newest first, each the same shape as `profile`.

  The config page's Trainee picker is built from this, so `trainee` in the
  config is chosen from the game's own titles rather than typed - the name has
  to match category 4 exactly for `profile` to find her.
  """
  con = _connect()
  if not con:
    return []
  growth_cols = ",".join(f"c.{col}" for _, col in GROWTH_COLUMNS)
  apt_cols = ",".join(f"r.{col}" for _, col in APTITUDE_COLUMNS)
  # One row per card at its highest rarity: card_rarity_data holds a row per
  # star level and the aptitudes we want are the maxed ones.
  rows = con.execute(
    f'SELECT c.id, c.chara_id, t.text, c.running_style, c.default_rarity, {growth_cols}, {apt_cols} '
    'FROM card_data c '
    'JOIN text_data t ON t.category=? AND t."index"=c.id '
    'JOIN card_rarity_data r ON r.card_id=c.id '
    ' AND r.rarity=(SELECT MAX(rarity) FROM card_rarity_data WHERE card_id=c.id) '
    'ORDER BY c.id DESC', (CAT_CARD_NAME,)).fetchall()
  con.close()
  split = 5 + len(GROWTH_COLUMNS)
  return [_build(r[0], r[1], r[2], r[3], r[4], r[5:split], r[split:]) for r in rows]

def profile(needle):
  """Aptitudes, growth and intended style for one trainee, or None.

  Ambiguity is reported rather than resolved: picking the first of several
  variants is how the base Meisho Doto's growth got read for the Halloween one.
  """
  hits = find(needle)
  if not hits:
    return None
  if len(hits) > 1:
    warning(f"{needle!r} matches {len(hits)} trainee cards "
            f"({', '.join(name for _, name in hits)}); using the newest. Name the "
            "full title in config.trainee to be sure.")
    hits = [max(hits, key=lambda h: h[0])]
  card_id, name = hits[0]
  con = _connect()
  if not con:
    return None

  growth_cols = ",".join(col for _, col in GROWTH_COLUMNS)
  row = con.execute(f"SELECT running_style, default_rarity, chara_id, {growth_cols} "
                    "FROM card_data WHERE id=?", (card_id,)).fetchone()
  apt_cols = ",".join(col for _, col in APTITUDE_COLUMNS)
  apt = con.execute(f"SELECT {apt_cols} FROM card_rarity_data WHERE card_id=? "
                    "ORDER BY rarity DESC LIMIT 1", (card_id,)).fetchone()
  con.close()
  if not row or not apt:
    return None

  return _build(card_id, row[2], name, row[0], row[1], row[3:], apt)

def grade(profile_data, key):
  return GRADE.get((profile_data.get("aptitude") or {}).get(key), "?")

def describe(profile_data):
  apt = profile_data["aptitude"]
  distance = " ".join(f"{k}:{GRADE.get(apt[k],'?')}" for k in ("sprint", "mile", "medium", "long"))
  style = " ".join(f"{k}:{GRADE.get(apt[k],'?')}" for k in ("front", "pace", "late", "end"))
  growth = ", ".join(f"{k} +{v}%" for k, v in profile_data["growth"].items()) or "none"
  return (f"{profile_data['name']} ({profile_data['rarity']}*): "
          f"turf:{GRADE.get(apt['turf'],'?')} dirt:{GRADE.get(apt['dirt'],'?')} | "
          f"{distance} | {style} | growth {growth} | game style {profile_data['style']}")

def warnings_for(profile_data, position, run_style, distances):
  """Config settings that disagree with the trainee. Advisory only."""
  notes = []
  apt = profile_data.get("aptitude") or {}
  for label, value in (("preferred_position", position), ("skill.skill_run_style", run_style)):
    if value and apt.get(value, 0) < USABLE_GRADE:
      best = max(("front", "pace", "late", "end"), key=lambda k: apt.get(k, 0))
      notes.append(f"{label} is {value}, but {profile_data['name']}'s {value} aptitude is "
                   f"{GRADE.get(apt.get(value), '?')}; her best is {best} "
                   f"({GRADE.get(apt.get(best), '?')}).")
  for dist in (distances or []):
    if apt.get(dist, 0) < USABLE_GRADE:
      notes.append(f"skill.skill_distance includes {dist}, but her {dist} aptitude is "
                   f"{GRADE.get(apt.get(dist), '?')} - those skills may never fire.")
  return notes

def check(name, position=None, run_style=None, distances=None):
  """Log the trainee's profile and anything the config disagrees with."""
  if not name:
    return None
  data = profile(name)
  if not data:
    warning(f"config.trainee is {name!r}, but no such trainee is in master.mdb; skipping the check.")
    return None
  info(f"Trainee: {describe(data)}")
  for note in warnings_for(data, position, run_style, distances):
    warning(note)
  return data

if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.exit('usage: python -m core.trainee "<name>"')
  found = profile(sys.argv[1])
  if not found:
    matches = find(sys.argv[1])
    sys.exit(f"no trainee matched {sys.argv[1]!r}" +
             (f"; did you mean {[m[1] for m in matches[:5]]}?" if matches else ""))
  print(describe(found))
