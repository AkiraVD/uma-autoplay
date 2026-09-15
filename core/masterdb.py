"""Read the game's own master.mdb, which is a plain SQLite database.

The game ships every name it displays in here and repatches it on update, so it
is the one source that cannot go stale - unlike the hand-maintained files in
data/, which are a snapshot of whatever the game looked like when someone wrote
them down.

Read-only and local: no network, no injection, nothing written back. The file is
copied before it is opened, because opening the live one can leave -wal/-shm
beside it and take locks on a database the game is using.

Everything here fails soft. A missing or unreadable database returns nothing and
the caller falls back to data/, so a different install path loses the extra
coverage rather than the feature.
"""
import os
import re
import shutil
import sqlite3
import tempfile

from utils.log import debug, info, warning

# Where the game keeps master.mdb. UMA_MASTER_MDB overrides all of it.
STEAM_APP_ID = "3224770"
GAME_FOLDER = "UmamusumePrettyDerby"
LOCALLOW = ("AppData", "LocalLow", "Cygames", "Umamusume", "master", "master.mdb")
STEAM_ROOTS = [
  "~/.local/share/Steam",
  "~/.steam/steam",
  "~/.var/app/com.valvesoftware.Steam/.local/share/Steam",   # Flatpak
]

# text_data categories. The whole table is (category, index, text), so a
# category is just "which list of strings".
SKILL_NAMES = 47
SKILL_DESCRIPTIONS = 48
EVENT_NAMES = 181
RACE_NAMES = 28

_cache = {}
_copy_of = {}
_skills = None

def steam_libraries():
  """Every Steam library folder here, from each client's libraryfolders.vdf."""
  found = []
  for root in STEAM_ROOTS:
    root = os.path.expanduser(root)
    paths = [root]
    try:
      with open(os.path.join(root, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as f:
        paths += re.findall(r'"path"\s+"([^"]+)"', f.read())
    except OSError:
      pass
    for path in paths:
      real = os.path.realpath(path)
      if os.path.isdir(real) and real not in found:
        found.append(real)
  return found

def candidate_paths():
  """Where master.mdb can be, in the order they are tried.

  The Windows client keeps it under LocalLow. The Linux Steam client (Proton)
  keeps it inside the game's own folder, in UmamusumePrettyDerby_Data/Persistent;
  the Proton prefix's LocalLow is tried after that in case a version moves it.
  """
  paths = [os.path.join(os.path.expanduser("~"), *LOCALLOW)]
  for library in steam_libraries():
    apps = os.path.join(library, "steamapps")
    paths.append(os.path.join(apps, "common", GAME_FOLDER, f"{GAME_FOLDER}_Data",
                              "Persistent", "master", "master.mdb"))
    paths.append(os.path.join(apps, "compatdata", STEAM_APP_ID, "pfx", "drive_c",
                              "users", "steamuser", *LOCALLOW))
  return paths

def master_path():
  """UMA_MASTER_MDB if set, else the first candidate that exists, else the first
  candidate, so a "not found" message still names a sensible place."""
  override = os.environ.get("UMA_MASTER_MDB")
  if override:
    return override
  paths = candidate_paths()
  return next((p for p in paths if os.path.isfile(p)), paths[0])

def local_copy():
  """Path to our own copy, refreshed when the game has repatched the original.

  Returns None when there is nothing to copy. Copying is keyed on mtime and
  size so a patch is picked up but an unchanged database is not copied twice.
  """
  source = master_path()
  try:
    stat = os.stat(source)
  except OSError as e:
    debug(f"No master.mdb at {source}: {e}")
    return None

  stamp = (stat.st_mtime, stat.st_size)
  target = os.path.join(tempfile.gettempdir(), "uma-auto-master.mdb")
  if _copy_of.get(target) == stamp and os.path.exists(target):
    return target

  try:
    shutil.copy2(source, target)
  except OSError as e:
    warning(f"Couldn't copy master.mdb: {e}")
    return None

  _copy_of[target] = stamp
  debug(f"Copied master.mdb ({stat.st_size} bytes) to {target}.")
  return target

def text_data(category):
  """Every string in one text_data category, deduplicated, or [].

  Cached per category: the copy is 16MB and the queries are only ever run to
  build a lookup table once.
  """
  if category in _cache:
    return _cache[category]

  path = local_copy()
  if not path:
    _cache[category] = []
    return []

  try:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
      rows = con.execute(
        "select text from text_data where category = ?", (category,)).fetchall()
  except sqlite3.Error as e:
    warning(f"Couldn't read text_data category {category} from master.mdb: {e}")
    _cache[category] = []
    return []

  # Ordered, not just a set, so the result is stable between runs - a fuzzy
  # match that ties should not pick a different name on the next start.
  seen, names = set(), []
  for (text,) in rows:
    text = (text or "").strip()
    if text and text not in seen:
      seen.add(text)
      names.append(text)

  _cache[category] = names
  return names

# What a skill actually is, assembled from the three tables that describe one:
#   text_data 47/48   the name and the description shown on screen
#   skill_data        rarity, and when the skill fires
#   single_mode_skill_need_point   what it costs in a career
#
# The condition is the part that decides whether a skill is worth buying at all.
# "is_finalcorner==1&corner==0&hp_per>=30&order<=2" only ever pays out if the
# trainee is in the top two with stamina left, which is a different proposition
# from "all_corner_random==1". Clauses are &-joined and mean AND; "@" separates
# whole alternative sets and means OR. 716 of 718 skills have one.
#
# precondition_1 is a separate gate that has to have been true earlier in the
# race (44 skills), and condition_2 is a second effect block (42 skills). Both
# are carried through rather than flattened, because a caller deciding what to
# buy needs to tell them apart.
SKILL_QUERY = """
select
  n."index"            as id,
  n.text               as name,
  d.text               as description,
  s.rarity             as rarity,
  s.group_id           as group_id,
  s.group_rate         as group_rate,
  s.grade_value        as grade_value,
  s.disable_singlemode as disable_singlemode,
  s.float_ability_time_1 as ability_time,
  p.need_skill_point   as cost,
  s.precondition_1     as precondition,
  s.condition_1        as condition,
  s.precondition_2     as precondition_2,
  s.condition_2        as condition_2
from text_data n
left join text_data d
  on d.category = 48 and d."index" = n."index"
left join skill_data s
  on s.id = n."index"
left join single_mode_skill_need_point p
  on p.id = n."index"
where n.category = 47
"""

def skills():
  """Every named skill, as a list of dicts. [] when the database is unreadable.

  Includes skills with no cost and no skill_data row - the name list is wider
  than either (980 names, 718 with mechanics, 577 purchasable in a career), and
  a caller matching an OCR'd name needs the whole list. `cost is None` is the
  test for "cannot be bought in a career".
  """
  global _skills
  if _skills is not None:
    return _skills

  path = local_copy()
  if not path:
    _skills = []
    return _skills

  try:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
      con.row_factory = sqlite3.Row
      rows = con.execute(SKILL_QUERY).fetchall()
  except sqlite3.Error as e:
    warning(f"Couldn't read the skill tables from master.mdb: {e}")
    _skills = []
    return _skills

  seen = set()
  _skills = []
  for row in rows:
    record = dict(row)
    name = (record.get("name") or "").strip()
    if not name or name in seen:
      continue
    seen.add(name)
    record["name"] = name
    _skills.append(record)

  info(f"Loaded {len(_skills)} skills from master.mdb.")
  return _skills

def reset():
  """Drop the caches, so a test can point UMA_MASTER_MDB somewhere else."""
  global _skills
  _cache.clear()
  _copy_of.clear()
  _skills = None
