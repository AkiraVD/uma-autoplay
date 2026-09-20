"""Pick a Trackblazer race schedule: which race to enter on which turn.

The output is the shape `config.race_schedule` already takes -
`{"name", "year", "date"}` - so a plan can be dropped straight into the config
the bot reads, and typed into the game's own agenda by hand.

**Why this is not a per-race score.** The obvious design gives every race a
number and takes the best one per turn. That is wrong for epithets, because an
epithet pays **once**, when its last qualifying race is won. Scoring each
qualifying race with the epithet's value counts it three or nine times over and
steers the whole schedule toward whichever epithet has the most candidates.
So the solver commits to a target set first, reserves exactly the races those
targets need, and only then fills the turns left over by per-race value.

**What a race is worth on its own** comes from the game's own tables via
`core.trackblazer`: Result Pts by grade and placement, shop coins (flat across
grades - a Pre-OP win pays what a G1 win pays), and fans. Per-race *stat* and
skill-point gain are deliberately absent: they are not in master.mdb, and a
weight invented for them would quietly dominate a score built from real
numbers. `WEIGHTS` says so in the open rather than hiding a zero.

**Everything is passed in.** The race pool defaults to
`master_data.get_plan_races()`, which admits OP races, but any list of race
dicts works, so this is testable without the game.
"""
import core.epithets as epithets
import core.trackblazer as trackblazer
import server.master_data as master_data
import utils.constants as constants

YEARS = ("Junior Year", "Classic Year", "Senior Year")

# A plan assumes the trainee wins what it schedules. That is the point of
# planning - an agenda entered in advance is a statement of intent - but it
# means every number here is a ceiling, not a forecast.
ASSUMED_PLACE = 1

# Per-unit value of each thing a race pays. Points and coins are in the
# scenario's own currencies and fans are raw, so the defaults put them on a
# comparable footing rather than pretending one is worth exactly another.
# `epithet` multiplies the epithet's TOTAL stat gain (per-stat value x 2).
WEIGHTS = {
  "epithet": 1.0,
  "points": 0.20,
  "coins": 0.05,
  "fans": 0.0008,
  # No "stats" or "skill_points" key on purpose: master.mdb carries no per-race
  # stat or SP gain, so there is nothing honest to weight. See the docstring.
}

# Racing back to back costs energy the schedule cannot see. The game allows it;
# this is a planning guard, not a rule, and 3 matches the usual advice.
#
# It only thins **filler**. A race an epithet depends on is never dropped, so an
# epithet-dense plan legitimately exceeds this - measured runs of 10 consecutive
# turns were reserved 10/10. Breaking those would cost the epithets the schedule
# exists to win, which is the wrong trade. `totals()` reports the longest run
# that actually survived, so the caller can see it rather than trust the limit.
MAX_CONSECUTIVE = 3


def _turn_index(date):
  try:
    return constants.DATE_ARRAY.index(date)
  except (AttributeError, ValueError):
    return 99


def _sort_key(race):
  return (YEARS.index(race["year"]) if race["year"] in YEARS else 9,
          _turn_index(race["date"]))


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


def race_value(race, weights=None):
  """What one race pays on its own, ignoring epithets, assuming a win."""
  w = dict(WEIGHTS, **(weights or {}))
  grade = race.get("grade", "")
  fans = (race.get("fans") or {}).get("gained", 0)
  return (w["points"] * trackblazer.points_for(grade, ASSUMED_PLACE)
          + w["coins"] * trackblazer.coins_for(ASSUMED_PLACE)
          + w["fans"] * fans)


def runnable(race, aptitudes=None, min_grade=None):
  """Can this trainee run this race, and does the caller want it?

  `aptitudes` is the shape `state.APTITUDES` uses - `surface_turf`,
  `distance_mile` and so on - and a race is runnable when both its surface and
  its distance sit at or above `floor`. With no aptitudes given, everything is
  runnable: a planner asked for a schedule, not an opinion about the trainee.
  """
  if min_grade and race.get("grade") not in min_grade:
    return False
  if not aptitudes:
    return True
  floor = ("a", "b")
  surface = aptitudes.get("surface_%s" % race.get("terrain", "").lower())
  distance = aptitudes.get("distance_%s" % (race.get("distance") or {}).get("type", "").lower())
  return (surface or "").lower() in floor and (distance or "").lower() in floor


def _turn(race):
  return (race["year"], race["date"])


def _cost(name, candidates, taken):
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
  free = [r for r in candidates if _turn(r) not in taken]

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
  for r in sorted(free, key=lambda x: -race_value(x)):
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
        blockers.append(f"{race['name']} ({race['date']}) taken by {holder['name']}")
    if blockers:
      return "; ".join(blockers[:3])
  return "not enough free turns"


def plan(targets=None, aptitudes=None, weights=None, races=None,
         max_consecutive=MAX_CONSECUTIVE, fill=True):
  """Build a schedule.

  `targets` is the epithets to chase, best-value-first when omitted. Returns
  the schedule, which epithets it earns, which it could not fit and why, and
  the totals - so the caller can show the trade rather than just the answer.
  """
  w = dict(WEIGHTS, **(weights or {}))
  everything = [r for r in pool(races) if runnable(r, aptitudes)]
  table = epithets.load()

  if targets is None:
    targets = [n for n in table
               if table[n]["rule"] and epithets.value_of(n)]

    # Scarcity first, value second. Ordering by value alone loses the tight
    # ones: `Lady` and `Kicking Up Dust` have exactly three candidate races on
    # three turns and no slack at all, while `Standard Distance Leader` will
    # take any 10 of 133. Value order spent those scarce turns on flexible
    # targets and then reported the scarce ones unreachable; scheduling them
    # first earns three of the four back.
    def slack(name):
      rule = table[name]["rule"]
      turns = {_turn(r) for r in everything if epithets.matches(rule, r)}
      return len(turns) - rule[2]

    targets.sort(key=lambda n: (slack(n), -epithets.value_of(n)))

  taken = {}          # (year, date) -> race
  reserved = set()    # turns an epithet depends on; never thinned away
  earned, missed = [], {}

  for name in targets:
    if not table.get(name, {}).get("rule"):
      missed[name] = epithets.unmodelled().get(name, "no rule")
      continue
    candidates = [r for r in everything if epithets.matches(table[name]["rule"], r)]
    picked = _cost(name, candidates, taken)
    if picked is None:
      missed[name] = _why_missed(table[name]["rule"], candidates, taken)
      continue
    for r in picked:
      taken[_turn(r)] = r
      reserved.add(_turn(r))
    earned.append(name)

  if fill:
    for race in sorted(everything, key=lambda r: -race_value(r, w)):
      if _turn(race) not in taken:
        taken[_turn(race)] = race

  schedule = _thin_runs(sorted(taken.values(), key=_sort_key),
                        max_consecutive, reserved)

  return {
    "schedule": [{"name": r["name"], "year": r["year"], "date": r["date"],
                  "grade": r.get("grade"), "racetrack": r.get("racetrack"),
                  "terrain": r.get("terrain"),
                  "distance": r.get("distance"),
                  "has_image": r.get("has_image", False)}
                 for r in schedule],
    "epithets": [{"name": n, "value": epithets.value_of(n),
                  "total": epithets.value_of(n) * 2,
                  "hint": table[n].get("hint")} for n in earned],
    "missed": missed,
    "totals": totals(schedule, earned, w),
  }


def _thin_runs(schedule, limit, reserved=()):
  """Break any run of more than `limit` races on consecutive turns.

  Racing back to back costs energy a schedule cannot see, so a run of five
  reads well and plays badly. The cheapest race in an over-long run goes first,
  and a turn an epithet depends on is never dropped - losing that would cost
  the epithet the run was built around, which is the opposite of the trade.

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
          out.remove(min(droppable, key=race_value))
          break                      # list changed; rescan from the top
      run = [race] if race is not None else []
    else:
      return out


def totals(schedule, earned, weights=None):
  w = dict(WEIGHTS, **(weights or {}))
  points = sum(trackblazer.points_for(r.get("grade", ""), ASSUMED_PLACE) for r in schedule)
  coins = sum(trackblazer.coins_for(ASSUMED_PLACE) for r in schedule)
  fans = sum((r.get("fans") or {}).get("gained", 0) for r in schedule)
  stats = sum(epithets.value_of(n) * 2 for n in earned)
  return {
    "races": len(schedule),
    "epithets": len(earned),
    "epithet_stats": stats,
    "points": points,
    "coins": coins,
    "fans": fans,
    "score": round(w["epithet"] * stats + w["points"] * points
                   + w["coins"] * coins + w["fans"] * fans, 1),
  }
