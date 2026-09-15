"""Race and event lists for the config page, read from the game's master.mdb.

master.mdb is the game's own SQLite master data, rewritten whenever the client
downloads an update, so a race or event added by the game shows up here without
anyone editing a JSON file. It is opened read-only.

What it can and can't give:
- Races: all of it. Name, date, year, track, distance, surface, grade and fans.
  The bot still picks a race by its picture, so each race says whether
  assets/races/<name>.png exists; one without a picture can't be scheduled.
- Events: titles and who owns them (trainee, support card, scenario), as the
  game spells them. Choice outcomes are not in master.mdb (they live in the
  story asset bundles), so those come from data/events, the same files
  core/event_outcomes.py reads.

Without master.mdb (a non-default install without UMA_MASTER_MDB, say) both fall
back to the local files.
"""
import json
import os
import re
import sqlite3
import threading
from pathlib import Path

from utils.log import info, warning
import core.trainee as trainee
import core.masterdb as masterdb

ROOT = Path(__file__).resolve().parent.parent
MDB_PATH = Path(masterdb.master_path())
RACES_JSON = ROOT / "data" / "races.json"
RACE_ASSETS = ROOT / "assets" / "races"
EVENTS_DIR = ROOT / "data" / "events"

# single_mode_program.race_permission. 5 is the URA Finale's own races.
PERMISSION_YEARS = {
  1: ["Junior Year"],
  2: ["Classic Year"],
  3: ["Classic Year", "Senior Year"],
  4: ["Senior Year"],
}
YEAR_ORDER = ["Junior Year", "Classic Year", "Senior Year"]
GRADES = {100: "G1", 200: "G2", 300: "G3"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# text_data categories.
TEXT_RACE_NAME = 28
TEXT_TRACK_NAME = 35
TEXT_CHARA_NAME = 170
TEXT_SUPPORT_NAME = 75
TEXT_STORY_TITLE = 181

SCENARIO_FILES = {
  "ura_finale.json": "URA Finale",
  "grand_live.json": "Grand Live",
  "trackblazer.json": "Trackblazer",
}

_cache = {}
_cache_lock = threading.Lock()


def _cached(key, build):
  """build() once per master.mdb version; the file's mtime is the version."""
  try:
    stamp = MDB_PATH.stat().st_mtime
  except OSError:
    stamp = None
  with _cache_lock:
    hit = _cache.get(key)
    if hit and hit[0] == stamp:
      return hit[1]
  data = build(stamp is not None)
  with _cache_lock:
    _cache[key] = (stamp, data)
  return data


def _connect():
  return sqlite3.connect(f"file:{MDB_PATH.as_posix()}?mode=ro", uri=True)


def _texts(con, category):
  return dict(con.execute('select "index", text from text_data where category=?', (category,)))


def asset_name(name):
  """'Tenno Sho (Autumn)' -> 'Tenno Sho Autumn', the spelling of assets/races/*.png."""
  name = name.replace("’", "'").replace("(", "").replace(")", "")
  return re.sub(r"\s+", " ", name).strip()


def distance_type(meters):
  if meters <= 1400:
    return "Sprint"
  if meters <= 1800:
    return "Mile"
  if meters <= 2400:
    return "Medium"
  return "Long"


def _load_races_json():
  with open(RACES_JSON, "r", encoding="utf-8") as f:
    return json.load(f)


def _race_images():
  return {p.stem for p in RACE_ASSETS.glob("*.png")}


def _races_from_json():
  images = _race_images()
  races = _load_races_json()
  for year in races.values():
    for name, detail in year.items():
      detail.setdefault("grade", "G1")
      detail["has_image"] = name in images
  return {"source": "races.json", "races": races}


def _races_from_mdb():
  local = _load_races_json()
  images = _race_images()
  con = _connect()
  try:
    names = _texts(con, TEXT_RACE_NAME)
    tracks = _texts(con, TEXT_TRACK_NAME)
    first_place_fans = dict(con.execute('select fan_set_id, fan_count from single_mode_fan_count where "order"=1'))
    rows = con.execute("""
      select p.race_instance_id, p.race_permission, p.month, p.half, p.need_fan_count, p.fan_set_id,
             r.grade, cs.race_track_id, cs.distance, cs.ground
      from single_mode_program p
      join race_instance ri on ri.id = p.race_instance_id
      join race r on r.id = ri.race_id
      join race_course_set cs on cs.id = r.course_set
    """).fetchall()
  finally:
    con.close()

  races = {year: {} for year in YEAR_ORDER}
  order = {}
  for instance_id, permission, month, half, need_fans, fan_set, grade, track_id, meters, ground in rows:
    if grade not in GRADES or permission not in PERMISSION_YEARS or not 1 <= month <= 12:
      continue
    raw_name = names.get(instance_id)
    if not raw_name:
      continue
    name = asset_name(raw_name)
    date = f"{'Early' if half == 1 else 'Late'} {MONTHS[month - 1]}"
    for year in PERMISSION_YEARS[permission]:
      # Scenario and character variants repeat a race; the first one is enough.
      if name in races[year]:
        continue
      known = local.get(year, {}).get(name, {})
      races[year][name] = {
        "date": date,
        "racetrack": tracks.get(track_id, ""),
        "terrain": "Dirt" if ground == 2 else "Turf",
        "distance": {"type": distance_type(meters), "meters": meters},
        "sparks": known.get("sparks", []),
        "fans": {"required": need_fans, "gained": first_place_fans.get(fan_set, 0)},
        "grade": GRADES[grade],
        "has_image": name in images,
      }
      order[(year, name)] = (month, half, grade)

  for year in YEAR_ORDER:
    races[year] = dict(sorted(races[year].items(), key=lambda kv: order[(year, kv[0])]))
  return {"source": "master.mdb", "races": races}


def get_races():
  def build(has_mdb):
    if has_mdb:
      try:
        return _races_from_mdb()
      except (sqlite3.Error, OSError) as e:
        warning(f"MDB-RACES-READ: master.mdb unreadable, using data/races.json: {e}")
    return _races_from_json()
  return _cached("races", build)


# ---------------------------------------------------------------- trainees

def get_trainees():
  """Trainee cards for the Trainee picker; the reader is core/trainee.py.

  No local fallback: `trainee` is only worth setting if master.mdb is there to
  read her numbers back, so an empty list is the honest answer.
  """
  def build(has_mdb):
    if has_mdb:
      try:
        cards = trainee.catalog()
        for card in cards:
          card["art"] = _image_url("trainee", f"{card['chara_id']}_{card['id']}")
        return {"source": "master.mdb", "trainees": cards}
      except (sqlite3.Error, OSError) as e:
        warning(f"MDB-TRAINEES-READ: master.mdb unreadable, no trainee list: {e}")
    return {"source": "none", "trainees": []}
  return _cached("trainees", build)


# ---------------------------------------------------------------- events

def _clean_title(title):
  """In-game title as the player sees it: the text carries literal '\\n' breaks and <i> tags."""
  title = title.replace("\\n", " ").replace("\n", " ")
  title = re.sub(r"</?[a-z]+>", "", title)
  return re.sub(r"\s+", " ", title).strip()


def _norm(title):
  """Match key between master.mdb titles and data/events names."""
  title = re.sub(r"^\(?[❯>]+\)?\s*", "", title)  # support chain steps: "(❯❯) ..."
  title = _clean_title(title).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
  return title.lower()


def _strip_owner(key):
  """'new year's resolutions (agnes tachyon)' -> "new year's resolutions"."""
  return re.sub(r"\s*\([^()]*\)$", "", key)


def _add_options(table, key, event_name, options):
  """data/events lists each choice as its own entry under the same name; gather them in order."""
  entry = table.setdefault(key, {}).setdefault(_norm(event_name), {"name": event_name, "options": []})
  for label, outcome in options.items():
    outcome = outcome.replace("\r\n", "\n").strip()
    if (label, outcome) not in entry["options"]:
      entry["options"].append((label, outcome))


def _local_events():
  """{owner key: {normalised title: {name, options}}} from data/events."""
  table = {}
  owners = {}

  def load(name):
    with open(EVENTS_DIR / name, "r", encoding="utf-8") as f:
      return json.load(f)

  for uma in load("uma_data.json"):
    card_id = int(uma["UmaSlug"].split("-")[0])
    owners[("card", card_id)] = uma["UmaName"]
    for event in uma["UmaEvents"]:
      _add_options(table, ("card", card_id), event["EventName"], event["EventOptions"])
  for event in load("support_card.json"):
    support_id = int(event["CardSlug"].split("-")[0])
    _add_options(table, ("support", support_id), event["EventName"], event["EventOptions"])
  for file_name, scenario in SCENARIO_FILES.items():
    if (EVENTS_DIR / file_name).exists():
      for event in load(file_name):
        _add_options(table, ("scenario", scenario), event["EventName"], event["EventOptions"])
  return table, owners


def _find_variants(table, keys, title):
  """(owner key, entry) pairs for a title, from the first owner that has it.

  The game names one "Victory!" event; data/events splits it by grade as
  "Victory! (G1)", "Victory! (G2/G3)", ... with different outcomes, so a title
  with no exact entry takes every suffixed variant.
  """
  wanted = _norm(title)
  for key in keys:
    events = table.get(key, {})
    if wanted in events:
      return [(key, events[wanted])]
    variants = [(key, entry) for name, entry in events.items() if _strip_owner(name) == wanted]
    if variants:
      return variants
  return []


def _image_url(kind, item_id):
  """Where the page asks for a picture; served and cached by server/images.py."""
  return f"/data/images/{kind}/{item_id}.png"


def _choice_rows(event_name, character_name, options):
  rows = []
  for i, (label, outcome) in enumerate(options, 1):
    rows.append({
      "id": f"{event_name}#{i}",
      "event_name": event_name,
      "character_name": character_name,
      "choice_text": label or f"Option {i}",
      "choice_number": str(i),
      "relation": "",
      "relation_type": "",
      "success_type": "-",
      "all_outcomes": outcome,
    })
  return rows


def _add_local(found, table, owner_of):
  """Add data/events entries under titles `found` doesn't cover yet: all of them
  without master.mdb, or those master.mdb spells differently or doesn't have yet."""
  covered = {_norm(title) for title in found}
  for key, events in table.items():
    owner, trainee = owner_of(key)
    for norm_name, entry in events.items():
      if norm_name in covered or _strip_owner(norm_name) in covered or len(entry["options"]) < 2:
        continue
      name = _clean_title(re.sub(r"^\(?[❯>]+\)?\s*", "", entry["name"]))
      record = (owner, trainee, entry["options"])
      if record not in found.setdefault(name, []):
        found[name].append(record)


def _assemble(found, characters, support_cards, scenarios, source):
  """found: {title: [(owner name, trainee?, options)]}.

  Names follow the config's existing convention. An event several trainees
  share is one per trainee, "New Year's Resolutions (Agnes Tachyon)", since
  each has her own outcomes. Support and scenario events with the same outcomes
  are one event listing every owner ("Ah, Friendship" for both Kitasan Black
  cards); with different outcomes, the first owner's name is appended.
  """
  choices = []
  for title, owned in found.items():
    owners = {owner for owner, _, _ in owned}
    trainee = [(o, opts) for o, is_trainee, opts in owned if is_trainee]
    others = [(o, opts) for o, is_trainee, opts in owned if not is_trainee]
    # One per trainee: her outfits can carry slightly different copies of a
    # shared event, and the config can hold only one choice under a name.
    done = set()
    for owner, options in trainee:
      if owner in done:
        continue
      done.add(owner)
      name = title if len(owners) == 1 else f"{title} ({owner})"
      choices.extend(_choice_rows(name, owner, options))
    by_options = {}
    for owner, options in others:
      names = by_options.setdefault(tuple(options), [])
      if owner not in names:
        names.append(owner)
    used = set()
    for options, owner_names in by_options.items():
      name = title if len(owners) == 1 or (len(by_options) == 1 and not trainee) else f"{title} ({owner_names[0]})"
      # Two cards of one character can end up with the same name here.
      base, n = name, 2
      while name in used:
        name, n = f"{base} {n}", n + 1
      used.add(name)
      choices.extend(_choice_rows(name, ", ".join(owner_names), list(options)))

  return {
    "source": source,
    "choiceArraySchema": {"choices": choices},
    "characterArraySchema": {"characters": characters},
    "supportCardArraySchema": {"supportCards": support_cards},
    "scenarios": [{"name": s, "image_url": ""} for s in scenarios],
  }


def _events_from_local():
  table, owners = _local_events()
  # "Oguri Cap (Christmas)" -> "Oguri Cap"; a card's slug stands in for its name.
  chara_of = {key: re.sub(r"\s*\(.*\)$", "", name) for key, name in owners.items()}
  slug_names = {}
  with open(EVENTS_DIR / "support_card.json", "r", encoding="utf-8") as f:
    for event in json.load(f):
      support_id, _, slug = event["CardSlug"].partition("-")
      slug_names[("support", int(support_id))] = slug.replace("-", " ").title()

  def owner_of(key):
    if key[0] == "card":
      return chara_of.get(key, ""), True
    if key[0] == "support":
      return slug_names.get(key, ""), False
    return key[1], False

  found = {}
  _add_local(found, table, owner_of)
  by_chara = {key[1] // 100: name for key, name in sorted(chara_of.items())}
  characters = [{"id": str(c), "name": name, "rarity": "", "image_url": _image_url("chara", c)}
                for c, name in sorted(by_chara.items(), key=lambda kv: kv[1])]
  support_cards = [{"id": str(key[1]), "name": name, "rarity": "", "type": "", "image_url": _image_url("support", key[1])}
                   for key, name in sorted(slug_names.items())]
  return _assemble(found, characters, support_cards, list(SCENARIO_FILES.values()), "data/events")


def _events_from_mdb():
  table, _ = _local_events()
  con = _connect()
  try:
    titles = _texts(con, TEXT_STORY_TITLE)
    chara_names = _texts(con, TEXT_CHARA_NAME)
    support_names = _texts(con, TEXT_SUPPORT_NAME)
    support_rows = con.execute("select id, chara_id, rarity from support_card_data").fetchall()
    stories = con.execute(
      "select story_id, card_id, card_chara_id, support_card_id, support_chara_id from single_mode_story_data"
    ).fetchall()
  finally:
    con.close()

  support_chara = {sid: cid for sid, cid, _ in support_rows}
  support_rarity = {sid: {1: "R", 2: "SR", 3: "SSR"}.get(r, "") for sid, _, r in support_rows}
  cards_of_chara = {}
  for key in table:
    if key[0] == "card":
      cards_of_chara.setdefault(key[1] // 100, []).append(key)
  supports_of_chara = {}
  for key in table:
    if key[0] == "support" and key[1] in support_chara:
      supports_of_chara.setdefault(support_chara[key[1]], []).append(key)
  scenario_keys = [("scenario", s) for s in SCENARIO_FILES.values()]

  found = {}
  chara_ids, support_ids = set(), set()
  for story_id, card_id, card_chara_id, support_id, support_chara_id in stories:
    raw = titles.get(story_id)
    if not raw:
      continue
    title = _clean_title(raw)
    trainee = bool(card_id or card_chara_id)
    if trainee:
      chara_id = card_chara_id or card_id // 100
      keys = ([("card", card_id)] if card_id else []) + cards_of_chara.get(chara_id, [])
      owner = chara_names.get(chara_id, "")
    elif support_id:
      keys = [("support", support_id)]
      owner = support_names.get(support_id, "")
    elif support_chara_id:
      keys = supports_of_chara.get(support_chara_id, [])
      owner = chara_names.get(support_chara_id, "")
    else:
      keys = scenario_keys
      owner = ""
    for key, entry in _find_variants(table, keys, title):
      if len(entry["options"]) < 2:
        continue
      if trainee:
        chara_ids.add(chara_id)
      elif support_id:
        support_ids.add(support_id)
      # A grade variant keeps its data/events name: "Victory! (G1)".
      name = title if _norm(entry["name"]) == _norm(title) else _clean_title(entry["name"])
      record = (owner or key[1], trainee, entry["options"])
      if record not in found.setdefault(name, []):
        found[name].append(record)

  characters = [{"id": str(c), "name": chara_names[c], "rarity": "", "image_url": _image_url("chara", c)}
                for c in sorted(chara_ids) if c in chara_names]
  support_cards = [{"id": str(s), "name": support_names[s], "rarity": support_rarity.get(s, ""), "type": "",
                    "image_url": _image_url("support", s)}
                   for s in sorted(support_ids) if s in support_names]
  def owner_of(key):
    if key[0] == "card":
      return chara_names.get(key[1] // 100, ""), True
    if key[0] == "support":
      return support_names.get(key[1], ""), False
    return key[1], False

  _add_local(found, table, owner_of)
  return _assemble(found, characters, support_cards, list(SCENARIO_FILES.values()), "master.mdb")


def get_events():
  def build(has_mdb):
    if has_mdb:
      try:
        data = _events_from_mdb()
        info(f"Event list from master.mdb: {len(data['choiceArraySchema']['choices'])} choices.")
        return data
      except (sqlite3.Error, OSError, KeyError) as e:
        warning(f"MDB-EVENTS-READ: master.mdb unreadable, using data/events only: {e}")
    return _events_from_local()
  return _cached("events", build)
