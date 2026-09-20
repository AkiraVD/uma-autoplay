"""Trackblazer epithets: what they pay, and which races earn them.

An epithet ("race title", `nickname` in master.mdb) is a one-time award for
meeting a condition during a career. Trackblazer has 40 of them, and they are
the scenario's stat engine outside training: +5, +10 or +15 to **two** random
stats, or a skill hint.

**Where each fact comes from, because the sources disagree.**

- *Names and conditions* come from master.mdb: `text_data` category 130 is the
  name, 131 the condition, joined by index, with `nickname.scenario_id = 4`
  selecting Trackblazer. This is the game's own English and it tracks patches.
- *Prices* are not in the mdb. They come from the gametora-derived table in
  daftuyda's Trackblazer scheduler, used with the author's permission
  (2026-09-20); gametora is the upstream, so that is who the credit is owed to.
  **Only the price** is taken from there: its condition text drops racecourses
  (`Kanto Conqueror` loses Kawasaki and Funabashi, `Tohoku Top Dog` loses
  Morioka) and misspells `Umamusume` as "Uma Musume", so matching on it would
  silently find nothing.
- The two figures quoted around the web are the same fact in different units:
  +5/+10/+15 is *per stat*, 10/20/30 is the *total across both*. `VALUE` below
  is per stat.

**Conditions are matched by a hand-written rule per epithet, not by parsing the
prose.** There are only 40, the prose has at least six shapes, and a regex that
looked right would fail silently on the ones it misread - the expensive kind of
bug here, because a schedule that misses an epithet still looks like a
schedule. `check()` re-reads the mdb text at load and warns when it no longer
matches the rule's assumption, so a patch that rewords a condition is noisy
rather than quietly wrong.

**What is deliberately not modelled**, rather than modelled badly:

- the four career milestones (`Leading the Charge`, `Moneymaker`,
  `Product Power`, `Climax King`) - they are career-wide outcomes, not
  scheduling choices, and no source prices them either;
- the five chained epithets (`Legendary`, `Phenomenal`, `Incredible`,
  `Goddess`, `Heroine`) - they need another epithet first, which is a solver
  concern, not a race filter;
- "any 2 of these races", "twice in a row", and year-qualified wins such as
  "Japan Cup (Classic Year)". These carry a rule of `None` and are reported by
  `unmodelled()` so a caller can say so instead of quietly scoring zero.

Pure data and arithmetic: nothing here reads the screen or imports core.state,
and races arrive as plain dicts so this is testable without a game.
"""
import re
import sqlite3

import core.masterdb as masterdb
from utils.log import debug, warning

TEXT_NAME = 130
TEXT_CONDITION = 131
TRACKBLAZER_SCENARIO = 4

# Per-stat award. The epithet grants this to each of two random stats, so the
# total is twice the number. Three epithets pay a skill hint instead; they are
# in HINTS and their VALUE is 0.
VALUE = {
  "Kanto Conqueror": 5, "West Japan Whiz": 5, "Tohoku Top Dog": 5,
  "Hokkaido Hotshot": 5, "Kokura Constable": 5, "Dirty Work": 5,
  "Pro Racer": 5, "Junior Jewel": 5, "Globe-Trotter": 5, "Dirt Dancer": 5,
  "Umatastic": 5, "Turf Tussler": 5, "Kicking Up Dust": 5,

  "Spring Champion": 10, "Fall Champion": 10, "Shield Bearer": 10,
  "Stunning": 10, "Standard Distance Leader": 10,
  "Non-Standard Distance Leader": 10, "Playing Dirty": 10,
  "Dirt G1 Star": 10, "Dirt G1 Achiever": 10, "Heroine": 10, "Lady": 10,
  "Eat My Dust": 10, "Sprint Go-Getter": 10, "Dirt Sprinter": 10,

  "Incredible": 15, "Phenomenal": 15, "Breakneck Miler": 15, "Goddess": 15,
  "Dirt G1 Powerhouse": 15, "Sprint Speedster": 15,
}

HINTS = {
  "Legendary": "Homestretch Haste",
  "Mile a Minute": "Mile Straightaways",
  "Dirt G1 Dominator": "Top Pick",
}

# No source prices these, so a planner must not pretend to score them.
MILESTONES = ("Leading the Charge", "Moneymaker", "Product Power", "Climax King")

# Needing another epithet first is a solver ordering problem, not a race filter.
CHAINED = {
  "Legendary": ("Spring Champion", "Fall Champion"),
  "Incredible": ("Stunning",),
  "Phenomenal": ("Stunning",),
  "Heroine": ("Lady",),
  "Goddess": ("Lady",),
}

# Audited against every career race name rather than written from memory, which
# is how the first attempt missed two of the graded eight: Copa Republica
# Argentina and Saudi Arabia Royal Cup. "Japan" already covers "Japanese Oaks"
# and "Tokyo Yushun Japanese Derby", so no demonym entry is needed. Re-audited
# over the OP pool (master_data.get_plan_races), which added Brazil Cup.
#
# "Nippon" is left out on purpose. Radio Nippon Sho and Zen-Nippon Junior
# Yushun carry Japan's name in Japanese and the condition says "a country's
# name", so they may well count - but nothing here can confirm it, and the two
# errors are not symmetric. Omitting a race that qualifies only makes the
# planner choose another; counting one the game does not builds a schedule
# around an epithet that never fires, which fails silently. Confirm in game
# before adding it.
COUNTRIES = ("Japan", "American", "New Zealand", "Saudi Arabia", "Argentina",
             "Brazil")

# "Standard distance" is a multiple of 400m (1200/1600/2000/2400); everything
# else - 1000, 1400, 1700, 1800, 1900, 2100, 2200, 2500, 3000, 3400 - is not.
STANDARD_STEP = 400

GRADED = ("G1", "G2", "G3")
OPEN_OR_BETTER = ("G1", "G2", "G3", "OP")

# (kind, argument, how many wins). A rule of None means "not modelled"; see the
# module docstring. `check` below asserts each rule still matches the mdb text.
RULES = {
  "Junior Jewel":                 ("name_has", "Junior Stakes", 3),
  "Umatastic":                    ("name_has", "Umamusume Stakes", 3),
  "Globe-Trotter":                ("name_country", None, 3),

  "Hokkaido Hotshot":             ("graded_at", ("Sapporo", "Hakodate"), 3),
  "Tohoku Top Dog":               ("graded_at", ("Fukushima", "Niigata", "Morioka"), 3),
  "Kanto Conqueror":              ("graded_at", ("Tokyo", "Nakayama", "Oi",
                                                 "Kawasaki", "Funabashi"), 3),
  "West Japan Whiz":              ("graded_at", ("Chukyo", "Hanshin", "Kyoto"), 3),
  "Kokura Constable":             ("graded_at", ("Kokura",), 2),

  "Dirty Work":                   ("surface", "Dirt", 5),
  "Playing Dirty":                ("surface", "Dirt", 10),
  "Eat My Dust":                  ("surface", "Dirt", 15),
  "Dirt G1 Achiever":             ("surface_grade", ("Dirt", "G1"), 3),
  "Dirt G1 Star":                 ("surface_grade", ("Dirt", "G1"), 4),
  "Dirt G1 Powerhouse":           ("surface_grade", ("Dirt", "G1"), 5),
  "Dirt G1 Dominator":            ("surface_grade", ("Dirt", "G1"), 9),

  "Standard Distance Leader":     ("standard", True, 10),
  "Non-Standard Distance Leader": ("standard", False, 10),
  "Pro Racer":                    ("min_grade", OPEN_OR_BETTER, 10),

  "Turf Tussler":                 ("spread", ("Turf", ("Sprint", "Mile", "Medium", "Long")), 4),
  "Dirt Dancer":                  ("spread", ("Dirt", ("Sprint", "Mile", "Medium")), 3),

  "Stunning":        ("all_of", ("Satsuki Sho", "Tokyo Yushun Japanese Derby",
                                 "Kikuka Sho"), 3),
  "Lady":            ("all_of", ("Oka Sho", "Japanese Oaks", "Shuka Sho"), 3),
  "Shield Bearer":   ("all_of", ("Tenno Sho Spring", "Tenno Sho Autumn"), 2),
  "Spring Champion": ("all_of", ("Osaka Hai", "Tenno Sho Spring",
                                 "Takarazuka Kinen"), 3),
  "Fall Champion":   ("all_of", ("Tenno Sho Autumn", "Japan Cup",
                                 "Arima Kinen"), 3),
  "Sprint Go-Getter": ("all_of", ("Takamatsunomiya Kinen", "Sprinters Stakes"), 2),
  "Sprint Speedster": ("all_of", ("Takamatsunomiya Kinen", "Sprinters Stakes",
                                  "Yasuda Kinen", "Mile Championship"), 4),
  "Breakneck Miler":  ("all_of", ("NHK Mile Cup", "Yasuda Kinen",
                                  "Mile Championship"), 3),
  "Kicking Up Dust":  ("all_of", ("Unicorn Stakes", "Leopard Stakes",
                                  "Japan Dirt Derby"), 3),

  # Not modelled: "any 2 of", "twice in a row", year-qualified wins, and the
  # career milestones. See unmodelled().
  "Mile a Minute": None, "Dirt Sprinter": None,
  "Legendary": None, "Phenomenal": None, "Incredible": None,
  "Goddess": None, "Heroine": None,
  "Leading the Charge": None, "Moneymaker": None,
  "Product Power": None, "Climax King": None,
}

_cache = None


def _clean(text):
  return re.sub(r"\s+", " ", (text or "").replace("\\n", " ")
                .replace("(Trackblazer only)", "")).strip()


def load(force=False):
  """Every Trackblazer epithet: name, condition, rank, price and rule.

  Returns a dict keyed by name. Falls back to the rule table alone if the mdb
  cannot be read, so a planner still works offline - the conditions are then
  absent but the prices and rules are not.
  """
  global _cache
  if _cache is not None and not force:
    return _cache

  rows = {}
  try:
    # local_copy() hands back a PATH, not a connection - same idiom as
    # masterdb.text_data(), which opens it read-only through a file: URI.
    path = masterdb.local_copy()
    if not path:
      raise OSError("no local copy of master.mdb")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as con:
      names = dict(con.execute(
        'select "index", text from text_data where category=?', (TEXT_NAME,)))
      conds = dict(con.execute(
        'select "index", text from text_data where category=?', (TEXT_CONDITION,)))
      ranks = dict(con.execute(
        "select id, rank from nickname where scenario_id=?", (TRACKBLAZER_SCENARIO,)))
    for eid, rank in ranks.items():
      name = names.get(eid)
      if not name:
        continue
      rows[name] = {
        "name": name, "id": eid, "rank": rank,
        "condition": _clean(conds.get(eid)),
        "value": VALUE.get(name, 0), "hint": HINTS.get(name),
        "rule": RULES.get(name),
      }
    debug("Epithets: %d Trackblazer entries from master.mdb." % len(rows))
  except Exception as exc:                      # mdb missing, locked, moved
    warning("Epithets: master.mdb unreadable (%s); using the rule table only." % exc)
    for name, rule in RULES.items():
      rows[name] = {"name": name, "id": None, "rank": None, "condition": "",
                    "value": VALUE.get(name, 0), "hint": HINTS.get(name),
                    "rule": rule}

  _cache = rows
  return rows


def unmodelled():
  """Names whose condition this module cannot check, with why."""
  out = {}
  for name in load():
    if name in MILESTONES:
      out[name] = "career milestone, not a scheduling choice"
    elif name in CHAINED:
      out[name] = "needs %s first" % " + ".join(CHAINED[name])
    elif RULES.get(name) is None:
      out[name] = "condition shape not modelled"
  return out


def _is_standard(meters):
  return meters % STANDARD_STEP == 0


def matches(rule, race):
  """Does one race count toward `rule`? `race` is a dict from the race table."""
  if not rule:
    return False
  kind, arg, _need = rule
  name = race.get("name", "")
  grade = race.get("grade", "")
  terrain = race.get("terrain", "")
  meters = (race.get("distance") or {}).get("meters", 0)

  if kind == "name_has":
    return arg in name
  if kind == "name_country":
    return any(c in name for c in COUNTRIES)
  if kind == "graded_at":
    return grade in GRADED and race.get("racetrack") in arg
  if kind == "surface":
    return terrain == arg
  if kind == "surface_grade":
    return terrain == arg[0] and grade == arg[1]
  if kind == "standard":
    return _is_standard(meters) is bool(arg)
  if kind == "min_grade":
    return grade in arg
  if kind == "spread":
    return terrain == arg[0] and (race.get("distance") or {}).get("type") in arg[1]
  if kind == "all_of":
    return name in arg
  return False


def candidates(name, races):
  """Every race in `races` that counts toward the epithet `name`."""
  rule = load().get(name, {}).get("rule")
  return [r for r in races if matches(rule, r)] if rule else []


def satisfied(name, won):
  """Is the epithet earned by winning `won` (an iterable of race dicts)?

  `spread` needs one win in each distance bucket, not just the count, so it is
  checked separately. Everything else is a count of qualifying wins, and
  `all_of` additionally needs every named race present.
  """
  ep = load().get(name)
  rule = ep and ep.get("rule")
  if not rule:
    return False
  kind, arg, need = rule
  hits = [r for r in won if matches(rule, r)]

  if kind == "spread":
    seen = {(r.get("distance") or {}).get("type") for r in hits}
    return all(d in seen for d in arg[1])
  if kind == "all_of":
    return all(any(r.get("name") == want for r in hits) for want in arg)
  return len(hits) >= need


def value_of(name):
  """Per-stat award, or 0 for a hint epithet. Total across both stats is 2x."""
  return load().get(name, {}).get("value", 0)


def check():
  """Warn where the mdb condition no longer looks like the rule assumes.

  Cheap sanity net for a patch that rewords a condition: it compares the
  racecourses and race names a rule names against the mdb text. Returns a list
  of complaints, empty when everything lines up.
  """
  problems = []
  for name, ep in load().items():
    rule, text = ep.get("rule"), ep.get("condition")
    if not rule or not text:
      continue
    kind, arg, need = rule
    if kind == "graded_at":
      missing = [t for t in arg if t not in text and not (t == "Oi" and "Oi" in text)]
      if missing:
        problems.append("%s: rule names %s, mdb text does not" % (name, missing))
    elif kind == "all_of":
      # The condition abbreviates race names - "Japanese Derby" for the table's
      # "Tokyo Yushun Japanese Derby", "Mile Ch." for "Mile Championship" - so
      # match on any shared word of four letters or more. Comparing the first
      # word instead reported Stunning as broken when its rule was correct.
      lowered = text.lower()
      for want in arg:
        words = [w for w in re.findall(r"[A-Za-z]+", want) if len(w) >= 4]
        if words and not any(w.lower() in lowered for w in words):
          problems.append("%s: rule names %r, mdb text does not" % (name, want))
    elif kind in ("name_has",) and arg not in text:
      problems.append("%s: rule looks for %r, mdb text does not mention it" % (name, arg))
    digits = re.findall(r"\b(\d+)\b", text)
    if kind not in ("all_of", "spread") and digits and str(need) not in digits:
      problems.append("%s: rule needs %d, mdb text says %s" % (name, need, digits))
  return problems
