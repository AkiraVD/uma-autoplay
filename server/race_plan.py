"""Pick a Trackblazer race schedule, turn by turn.

Modelled on daftuyda's Trackblazer scheduler (race.daftuyda.moe), used with the
author's permission (2026-09-20), but written here from scratch and fed from the
game's own master.mdb rather than a hand-collected JSON file. The output is the
shape `config.race_schedule` already takes - `{"name", "year", "date"}` - so a
plan drops straight into the config the bot reads, and can be typed into the
game's own agenda by hand.

**Two of the upstream tool's columns are deliberately absent, because the data
does not exist here.** It scores each race on the stats and skill points it
pays, numbers gametora collected by hand. master.mdb has no such table: its
`single_mode_reward_set` is a *prize* list (money and items, keyed by finishing
position), and `single_mode_hint_gain` is keyed by support card, not by race.
Checked 2026-09-20. Inventing those numbers would make the ranking look
authoritative while being a guess, so races are not scored at all.

**Nothing here scores a race**, and that is a smaller loss than it sounds. An
epithet pays **once**, when its last qualifying race is won, so scoring every
qualifying race with the epithet's value counts it three or nine times and
steers the schedule toward whichever epithet has the most candidates. And
Trackblazer races a great deal by its nature, so which race fills a given turn
barely moves the outcome. Fan counts are ignored for the same reason, plus one
more: any error in them is roughly proportional across every race, so it
cancels out of a ranking entirely.

So the solver commits to a target set, reserves exactly the races those targets
need, and fills any turns left over in calendar order. Result Pts and shop
coins are still *reported* from `core.trackblazer`, because Trackblazer's year
targets are denominated in Result Pts - but they decide nothing.

**Everything is passed in.** The race pool defaults to
`master_data.get_plan_races()`, which admits OP races, so this is testable
without the game.
"""
import core.epithets as epithets
import core.trackblazer as trackblazer
import server.master_data as master_data
import utils.constants as constants

YEARS = ("Junior Year", "Classic Year", "Senior Year")

# The career's 59 raceable turns. Junior year opens at Late Jul, because the
# trainee debuts mid-year; Classic and Senior each run the full 24.
JUNIOR_FIRST = "Late Jul"

# A plan assumes the trainee wins what it schedules. That is the point of
# planning - an agenda entered in advance is a statement of intent - but it
# means every number here is a ceiling, not a forecast.
ASSUMED_PLACE = 1

# Racing back to back costs energy the schedule cannot see. The game allows it;
# this is a planning guard, not a rule, and 3 matches the usual advice. 0 means
# no limit, matching the upstream tool's own input.
#
# It only thins **filler**. A race an epithet depends on is never dropped, and
# neither is a turn the user pinned, so an epithet-dense plan legitimately
# exceeds this. Breaking those would cost the epithets the schedule exists to
# win. `totals()` reports the longest run that actually survived.
MAX_CONSECUTIVE = 3

# Aptitude letters, best first. `min_aptitude` names the worst letter still
# considered runnable.
APTITUDE_ORDER = ("s", "a", "b", "c", "d", "e", "f", "g")
DEFAULT_FLOOR = "b"

GRADED_ONLY = ("G1", "G2", "G3")


def _turn_index(date):
  try:
    return constants.DATE_ARRAY.index(date)
  except (AttributeError, ValueError):
    return 99


def _sort_key(race):
  return (YEARS.index(race["year"]) if race["year"] in YEARS else 9,
          _turn_index(race["date"]))


def _turn(race):
  return (race["year"], race["date"])


def key_of(year, date):
  """The wire form of a turn: 'Classic Year|Early Apr'.

  The UI addresses turns by string - a lock, a skip, a shared link - and a
  tuple does not survive JSON. One spelling, defined once, used both ways.
  """
  return "%s|%s" % (year, date)


def parse_key(text):
  year, _, date = (text or "").partition("|")
  return (year, date)


def career_turns():
  """Every turn a race can be entered on, in order. 59 of them."""
  out = [("Junior Year", d)
         for d in constants.DATE_ARRAY[constants.DATE_ARRAY.index(JUNIOR_FIRST):]]
  for year in ("Classic Year", "Senior Year"):
    out.extend((year, d) for d in constants.DATE_ARRAY)
  return out


def pool(races=None):
  """Flatten the race table into a list, each race carrying its own name/year."""
  if races is not None:
    return list(races)
  out = []
  for year, entries in master_data.get_plan_races()["races"].items():
    for name, detail in entries.items():
      race = dict(detail)
      race["name"] = name
      race["year"] = year
      out.append(race)
  return out


def _floor(min_aptitude):
  try:
    idx = APTITUDE_ORDER.index((min_aptitude or DEFAULT_FLOOR).lower())
  except ValueError:
    idx = APTITUDE_ORDER.index(DEFAULT_FLOOR)
  return set(APTITUDE_ORDER[:idx + 1])


def runnable(race, aptitudes=None, include_op=True, min_aptitude=DEFAULT_FLOOR):
  """Can this trainee run this race, and does the caller want it?

  `aptitudes` is the shape `state.APTITUDES` uses - `surface_turf`,
  `distance_mile` and so on - and a race is runnable when both its surface and
  its distance sit at or above the floor. With no aptitudes given, everything
  is runnable: a planner was asked for a schedule, not an opinion about the
  trainee.
  """
  if not include_op and race.get("grade") not in GRADED_ONLY:
    return False
  if not aptitudes:
    return True
  allowed = _floor(min_aptitude)
  surface = aptitudes.get("surface_%s" % (race.get("terrain") or "").lower())
  distance = aptitudes.get("distance_%s" % ((race.get("distance") or {}).get("type") or "").lower())
  return (surface or "").lower() in allowed and (distance or "").lower() in allowed


def _cost(name, candidates, taken, blocked):
  """The extra races still needed for this epithet, or None if it cannot fit.

  Returns a list - possibly empty, meaning the schedule already earns it for
  free. None means unreachable with the turns left, which is the honest answer
  when a target cannot be met; silently dropping it would be worse.

  **Races already scheduled count.** Several epithets are strictly nested -
  winning 15 dirt races satisfies `Eat My Dust`, `Playing Dirty` *and*
  `Dirty Work` - and an earlier version charged each of them the full price
  from free turns only. Three nested dirt targets billed 30 turns instead of
  15, the targets between them reserved all 59 turns of the career, and every
  later epithet came back "not enough free turns" while being charged for
  races that were already on the schedule.
  """
  rule = epithets.load().get(name, {}).get("rule")
  if not rule:
    return None
  kind, arg, need = rule
  have = [r for r in taken.values() if epithets.matches(rule, r)]
  free = [r for r in candidates
          if _turn(r) not in taken and _turn(r) not in blocked]

  if kind == "spread":
    covered = {(r.get("distance") or {}).get("type") for r in have}
    picked, used = [], set()
    for bucket in arg[1]:
      if bucket in covered:
        continue
      for r in free:
        if (r.get("distance") or {}).get("type") == bucket and _turn(r) not in used:
          picked.append(r)
          used.add(_turn(r))
          break
      else:
        return None
    return picked

  if kind == "all_of":
    held = {r["name"] for r in have}
    picked, used = [], set()
    for want in arg:
      if want in held:
        continue
      for r in free:
        if r["name"] == want and _turn(r) not in used:
          picked.append(r)
          used.add(_turn(r))
          break
      else:
        return None
    return picked

  shortfall = need - len(have)
  if shortfall <= 0:
    return []
  picked, used = [], set()
  for r in sorted(free, key=_sort_key):
    if _turn(r) in used:
      continue
    picked.append(r)
    used.add(_turn(r))
    if len(picked) >= shortfall:
      return picked
  return None


def _why_missed(rule, candidates, taken):
  """Say what actually blocked an epithet, not merely that something did.

  "Not enough free turns" hides two very different situations behind the same
  words. `Lady` and `Stunning` want the *same three* Classic turns - the Triple
  Tiara against the Triple Crown, Oka Sho against Satsuki Sho and so on - so
  earning one forecloses the other, and the chains that hang off them
  (Heroine/Goddess against Incredible/Phenomenal) go with it. That is a choice
  to put in front of the user, not a failure. Everything else is an ordinary
  trade against whichever race took the turn, and naming it lets the caller
  judge whether the swap is worth making.

  Only scarce targets are explained. A count rule with 133 candidates would
  list noise, so it keeps the short answer.
  """
  if not candidates:
    return "no qualifying race in the pool"
  wanted = {_turn(r) for r in candidates}
  if len(wanted) <= rule[2] * 3:
    blockers = []
    for race in sorted(candidates, key=_sort_key):
      holder = taken.get(_turn(race))
      if holder and holder["name"] != race["name"]:
        blockers.append("%s (%s) taken by %s" % (race["name"], race["date"], holder["name"]))
    if blockers:
      return "; ".join(blockers[:3])
  return "not enough free turns"


def _ordered_targets(table, everything):
  """Every modelled epithet, scarcest first.

  Scarcity first, value second. Ordering by value alone loses the tight ones:
  `Lady` and `Kicking Up Dust` have exactly three candidate races on three
  turns and no slack at all, while `Standard Distance Leader` will take any 10
  of 133. Value order spent those scarce turns on flexible targets and then
  reported the scarce ones unreachable; scheduling them first earns three of
  the four back.
  """
  names = [n for n in table if table[n]["rule"] and epithets.value_of(n)]

  def slack(name):
    rule = table[name]["rule"]
    turns = {_turn(r) for r in everything if epithets.matches(rule, r)}
    return len(turns) - rule[2]

  names.sort(key=lambda n: (slack(n), -epithets.value_of(n)))
  return names


def plan(targets=None, aptitudes=None, races=None,
         max_consecutive=MAX_CONSECUTIVE, fill=True, include_op=True,
         min_aptitude=DEFAULT_FLOOR, locks=None, skip=None):
  """Build a schedule.

  `targets` is the epithets to chase, scarcest-first when omitted. `locks` pins
  a race to a turn (`{"Classic Year|Early Apr": "Osaka Hai"}`) and `skip` keeps
  turns empty - both are the user overriding the solver, so neither is ever
  thinned away or reassigned.

  Returns the schedule, the per-turn grid the UI drives, which epithets it
  earns, which it could not fit and why, and the totals.
  """
  everything = [r for r in pool(races)
                if runnable(r, aptitudes, include_op, min_aptitude)]
  by_turn = {}
  for race in everything:
    by_turn.setdefault(_turn(race), []).append(race)

  table = epithets.load()
  taken = {}          # (year, date) -> race
  reserved = set()    # turns the user pinned or an epithet depends on
  blocked = set()     # turns the user wants left empty

  for text in (skip or []):
    blocked.add(parse_key(text) if isinstance(text, str) else tuple(text))

  for text, name in (locks or {}).items():
    turn = parse_key(text) if isinstance(text, str) else tuple(text)
    if turn in blocked:
      continue
    for race in by_turn.get(turn, []):
      if race["name"] == name:
        taken[turn] = race
        reserved.add(turn)
        break

  if targets is None:
    targets = _ordered_targets(table, everything)

  earned, missed = [], {}
  for name in targets:
    if not table.get(name, {}).get("rule"):
      missed[name] = epithets.unmodelled().get(name, "no rule")
      continue
    candidates = [r for r in everything if epithets.matches(table[name]["rule"], r)]
    picked = _cost(name, candidates, taken, blocked)
    if picked is None:
      missed[name] = _why_missed(table[name]["rule"], candidates, taken)
      continue
    for r in picked:
      taken[_turn(r)] = r
      reserved.add(_turn(r))
    earned.append(name)

  if fill:
    for race in sorted(everything, key=_sort_key):
      turn = _turn(race)
      if turn not in taken and turn not in blocked:
        taken[turn] = race

  schedule = _thin_runs(sorted(taken.values(), key=_sort_key),
                        max_consecutive, reserved)
  placed = {_turn(r): r for r in schedule}

  return {
    "schedule": [_entry(r) for r in schedule],
    "turns": _grid(by_turn, placed, reserved, blocked),
    "epithets": [{"name": n, "value": epithets.value_of(n),
                  "total": epithets.value_of(n) * 2,
                  "hint": table[n].get("hint")} for n in earned],
    "progress": progress(schedule, earned),
    "missed": missed,
    "totals": totals(schedule, earned),
  }


def _entry(race):
  return {"name": race["name"], "year": race["year"], "date": race["date"],
          "grade": race.get("grade"), "racetrack": race.get("racetrack"),
          "terrain": race.get("terrain"), "distance": race.get("distance"),
          "has_image": race.get("has_image", False)}


def _grid(by_turn, placed, reserved, blocked):
  """Every career turn with what it could hold and what it did.

  The UI needs the empty turns too - that is where "no race" and a manual pick
  are chosen - so this walks the calendar rather than the schedule.
  """
  out = []
  for turn in career_turns():
    race = placed.get(turn)
    out.append({
      "key": key_of(*turn),
      "year": turn[0],
      "date": turn[1],
      "picked": race["name"] if race else None,
      "pinned": turn in reserved,
      "skipped": turn in blocked,
      "options": [_entry(r) for r in sorted(by_turn.get(turn, []),
                                            key=lambda r: r["name"])],
    })
  return out


def _thin_runs(schedule, limit, reserved=()):
  """Break any run of more than `limit` races on consecutive turns.

  Racing back to back costs energy a schedule cannot see, so a run of five
  reads well and plays badly. The LAST race in an over-long run goes first -
  races are not scored, so there is no cheapest one, and dropping the latest
  keeps the earlier entries in line with the earliest-first ordering used
  everywhere else here. A turn an epithet depends on, or one the user pinned,
  is never dropped: losing that would cost the epithet the run was built
  around.

  Returns a new list; the input is not modified.
  """
  if not limit or limit < 1:
    return list(schedule)
  out = list(schedule)
  while True:
    run = []
    for race in out + [None]:
      prev = run[-1] if run else None
      adjacent = (prev is not None and race is not None
                  and race["year"] == prev["year"]
                  and _turn_index(race["date"]) == _turn_index(prev["date"]) + 1)
      if adjacent:
        run.append(race)
        continue
      if len(run) > limit:
        droppable = [r for r in run if _turn(r) not in reserved]
        if droppable:
          out.remove(max(droppable, key=_sort_key))
          break                      # list changed; rescan from the top
      run = [race] if race is not None else []
    else:
      return out


def longest_run(schedule):
  """The longest stretch of consecutive raced turns the schedule actually has."""
  best = run = 0
  prev = None
  for race in sorted(schedule, key=_sort_key):
    adjacent = (prev is not None and race["year"] == prev["year"]
                and _turn_index(race["date"]) == _turn_index(prev["date"]) + 1)
    run = run + 1 if adjacent else 1
    best = max(best, run)
    prev = race
  return best


def progress(schedule, earned=()):
  """How far the schedule gets toward every modelled epithet.

  Reported for all of them, not just the earned ones, because "8 of 9 dirt G1
  wins" is the most useful thing the page can say: it names the one swap that
  would buy another epithet.
  """
  out = []
  for name, ep in epithets.load().items():
    rule = ep.get("rule")
    if not rule:
      continue
    hits = [r for r in schedule if epithets.matches(rule, r)]
    kind, arg, need = rule
    if kind == "spread":
      have = len({(r.get("distance") or {}).get("type") for r in hits} & set(arg[1]))
      need = len(arg[1])
    elif kind == "all_of":
      have = len({r["name"] for r in hits} & set(arg))
      need = len(arg)
    else:
      have = len(hits)
    out.append({"name": name, "have": min(have, need), "need": need,
                "earned": name in earned, "value": epithets.value_of(name),
                "hint": ep.get("hint"), "condition": ep.get("condition")})
  out.sort(key=lambda e: (e["earned"], e["have"] - e["need"]), reverse=True)
  return out


def catalogue():
  """Every epithet, for the target picker. Unmodelled ones say why.

  Having a rule is what makes an epithet selectable, not having a price.
  `Dirt G1 Dominator` pays a skill hint rather than stats, so its `VALUE` is 0,
  but nine dirt G1 wins is an ordinary schedulable condition and asking for it
  is a reasonable thing to want. It stays out of the *automatic* target order
  in `_ordered_targets` for the opposite reason: a hint cannot be compared
  against +10 to two stats, so the solver should not silently trade one for the
  other. Choose it deliberately or not at all.
  """
  why = epithets.unmodelled()
  out = []
  for name, ep in epithets.load().items():
    out.append({"name": name, "value": ep.get("value", 0),
                "hint": ep.get("hint"), "condition": ep.get("condition"),
                "rank": ep.get("rank"),
                "selectable": bool(ep.get("rule")),
                "why": why.get(name)})
  out.sort(key=lambda e: (not e["selectable"], -e["value"], e["name"]))
  return {"epithets": out}


def totals(schedule, earned):
  """Reported, never scored.

  Points and coins stay because Trackblazer's year targets are denominated in
  Result Pts, so a caller wants to see them - but nothing ranks or chooses by
  them. There is no stat, skill-point or fan column: master.mdb does not carry
  per-race stat or SP gains, and a made-up number would look authoritative.
  """
  points = sum(trackblazer.points_for(r.get("grade", ""), ASSUMED_PLACE) for r in schedule)
  coins = sum(trackblazer.coins_for(ASSUMED_PLACE) for r in schedule)
  stats = sum(epithets.value_of(n) * 2 for n in earned)
  return {
    "races": len(schedule),
    "epithets": len(earned),
    "epithet_stats": stats,
    "points": points,
    "coins": coins,
    "longest_run": longest_run(schedule),
  }
