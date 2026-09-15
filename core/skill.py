import re

import utils.control as control
import Levenshtein
from rapidfuzz import fuzz, process

import utils.constants as constants

from utils.log import info, warning, error, debug
from utils.screenshot import enhanced_screenshot
from core.ocr import extract_text, extract_number
from core.recognizer import is_btn_active
import core.masterdb as masterdb
import core.skill_score as skill_score
import core.skill_tiers as skill_tiers
import core.state as state
import core.menu_scan as menu_scan

# The Grand Concert's scenario gold skill, by name: "I Wanna Win with You".
# Its white base ("On the Way to Our Dream") is not forced - buying the gold
# upgrades it anyway, and the screen price already includes the pair.
GOLD_SKILL_MATCH = lambda name: "wanna win" in (name or "").lower()

# The discount on a skill comes from its hint level, so the hint level IS the
# signal: at max hint the price is as low as it will ever go. Levels 1-3 take
# 10% off each and 4-5 take 5% each, so max hint is 40% off; Fast Learner takes
# another 10% off everything on top.
#
# Mid-career the bot buys only at max hint. Hints keep arriving, so a skill
# taken at level 2 costs a fifth more than the same skill taken later, and a
# point spent early cannot be spent again. Everything else waits for the
# end-of-career pass, where the optimizer spends what is left.
MAX_HINT_LEVEL = 5
MAX_HINT_DISCOUNT = 0.40
# The printed price is rounded, and Fast Learner discounts further, so the
# fallback compares with slack and in the generous direction.
DISCOUNT_SLACK = 3
# A career skill costs 40-360; anything outside that is a misread.
SKILL_COST_RANGE = (30, 500)
# A career ends with at most a few thousand points.
SKILL_PTS_RANGE = (0, 9999)
# How many times to sweep the list buying the plan. Two is usually enough;
# the third is for a row that misreads twice.
BUY_SWEEPS = 3

# The drag calibration for this screen lives in core/menu_scan.SKILL_BUY,
# together with the measurements behind every number.

def read_skill_cost(box):
  """Skill point cost printed on one row, or None when it will not read."""
  x, y, w, h = box
  dx, dy, width, height = constants.SKILL_COST_OFFSET
  value = extract_number(enhanced_screenshot((x + dx, y + dy, width, height)),
                         value_range=SKILL_COST_RANGE)
  return None if value is None or value < 0 else value

HINT_LEVEL_RE = re.compile(r"lvl\s*([1-5])\b", re.I)
HINT_DISCOUNT_RE = re.compile(r"(\d{1,2})\s*%")

def read_hint(box):
  """The hint badge on one row as {"level", "discount"}, or None.

  The badge is two lines - "Hint Lvl 2" over "20% OFF!" - so extract_number is
  no use here: it would see both 2 and 20 and have no way to tell which is the
  level. Read as text and pick the two numbers apart by what surrounds them.

  Absent is not zero. A skill with no hint shows no badge at all and reads as
  an empty string, and a badge that will not read is not evidence of anything;
  both return None so the caller falls back to the price.
  """
  x, y, w, h = box
  dx, dy, width, height = constants.SKILL_HINT_OFFSET
  text = extract_text(enhanced_screenshot((x + dx, y + dy, width, height))) or ""
  if not text.strip():
    return None

  level = HINT_LEVEL_RE.search(text)
  discount = HINT_DISCOUNT_RE.search(text)
  found = {
    "level": int(level.group(1)) if level else None,
    "discount": int(discount.group(1)) if discount else None,
  }
  if found["level"] is None and found["discount"] is None:
    return None
  debug(f"Hint badge {text!r} -> {found}")
  return found

def plausible_cost(record, shown_cost):
  """The price to plan with: the screen's, when it reads at all.

  This used to reject any price above the database's `need_skill_point`, on the
  reasoning that a hint only makes a skill cheaper so nothing can exceed its
  undiscounted cost. **The game disagrees.** Photographed on a live buy screen,
  "Professor of Curvature" is listed at 306 with a Hint Lvl 3 badge while the
  database says 180; "On Your Left!" at 342 against 180. The OCR was right and
  the rule was wrong.

  base * (1 - discount) does hold for most skills - Extra Tank, Ramp Up, Tether,
  Up-Tempo and half a dozen others match to the point - so the database is a
  good reference and a bad ceiling.

  Rejecting those prices was worse than useless: the planner fell back to the
  database's 180 for a skill that costs 306, understating the spend and letting
  a plan overrun the budget. The screen is what will actually be charged, so the
  screen wins, and only a value outside SKILL_COST_RANGE is treated as a misread.
  """
  if not shown_cost or shown_cost <= 0:
    return None
  low, high = SKILL_COST_RANGE
  if not low <= shown_cost <= high:
    debug(f"Ignoring a skill price of {shown_cost}: outside {SKILL_COST_RANGE}.")
    return None

  base = record.get("cost") if record else None
  if base and shown_cost > base:
    # Worth saying, because it means the reference is off for this scenario -
    # but the number on screen is still the one being charged.
    debug(f"{record['name']!r} is listed at {shown_cost}, above the database's"
          f" {base}. Planning with the screen price.")
  return shown_cost

def at_max_discount(record, shown_cost, hint=None):
  """True when this skill is as cheap as it will ever be.

  The hint decides it, so that is checked first. The badge states the same fact
  twice - a level and a percentage - and either will do, because level 5 and
  40% off are the same thing. Whichever reads is used.

  When neither reads, the price is compared against the database's undiscounted
  cost instead: the same conclusion by arithmetic rather than by reading a
  number the game already worked out.
  """
  if hint:
    if hint.get("level") is not None:
      return hint["level"] >= MAX_HINT_LEVEL
    if hint.get("discount") is not None:
      return hint["discount"] >= MAX_HINT_DISCOUNT * 100

  base = record.get("cost") if record else None
  if not base or not shown_cost:
    return False
  shown_cost = plausible_cost(record, shown_cost)
  if not shown_cost:
    return False
  return shown_cost <= round(base * (1 - MAX_HINT_DISCOUNT)) + DISCOUNT_SLACK

def uma_aptitudes():
  """(style, distance) this Uma races, from config. Either may be None."""
  return (getattr(state, "SKILL_RUN_STYLE", None),
          getattr(state, "SKILL_DISTANCE", None) or None)

def usable_here(record):
  """True when the skill can fire for this Uma at all.

  Three things have to hold. It must do something useful (not a debuff), it
  must be able to fire for this Uma, and it must be rated A tier or better.

  The aptitude test is the one the old configured list got wrong: it listed
  Speed Star, which is running_style==2, on a Front runner - 180 points that
  could never pay out.

  The tier test is what replaced that list. skill_tiers is the drive now, so
  "usable" means "worth having", not merely "able to fire".
  """
  if not record:
    return False
  if not skill_score.beneficial(record):
    return False
  if not skill_tiers.worth_buying(record["name"]):
    return False
  style, distance = uma_aptitudes()
  return skill_score.applicable(record, style=style, distance=distance)

# Which calibration this screen scrolls with. Everything about *how* the list
# is dragged and walked now lives in core/menu_scan; only the skill-specific
# reading of a row is left here.
LIST = menu_scan.SKILL_BUY

def buy_buttons():
  """y of every buy button on screen, top to bottom."""
  return menu_scan.anchor_ys(LIST)

def scroll_skills(up, distance=None):
  menu_scan.scroll(LIST, up, distance)

def advance_one_screen():
  return menu_scan.advance_one_screen(LIST)

def list_frame():
  return menu_scan.frame(LIST)

def wait_for_list(limit=3.0, quiet=0.5):
  menu_scan.wait_for_list(LIST, limit=limit, quiet=quiet)

def scroll_skills_to_top(limit=None):
  menu_scan.scroll_to_top(LIST)

def scan_rows(passes=None):
  """Walk the skill list, yielding (box, text, record, cost, hint) per row.

  The walking is menu_scan's; what is added here is reading a skill out of the
  row - the name crop, the master.mdb match, the price and the hint badge.
  """
  for box in menu_scan.rows(LIST, passes=passes):
    x, y, w, h = box
    nx, ny, nw, nh = constants.SKILL_NAME_OFFSET
    text = extract_text(enhanced_screenshot((x + nx, y + ny, nw, nh)))
    canonical = canonical_skill(text)
    record = None
    if canonical:
      record = next((r for r in masterdb.skills()
                     if base_name(r["name"]) == base_name(canonical)), None)
    yield box, text, record, read_skill_cost(box), read_hint(box)

def buy_skill(match_any=False):
  """Buy skills off the screen.

  Two different jobs behind one flag, because the right answer differs:

  - **Mid-career** (match_any False): buy only what this Uma can use, only at
    full hint discount, and only what the end-of-career optimizer would pick
    out of those with the points in hand. Everything else is left for later,
    because hints keep coming and a point spent early cannot be spent again.
  - **Career end** (match_any True): unspent points are destroyed, so the
    optimizer picks the best affordable set and it buys that.
  """
  if match_any:
    return buy_planned()

  # Sweep, and remember what was already taken, for the same two reasons
  # buy_planned does.
  #
  # advance_one_screen deliberately leaves the last visible row on screen, so
  # every row is now seen at least twice per scan at different heights. That is
  # what stopped rows being missed, but it also means a single scan offers the
  # same skill twice - so a click has to be recorded against the skill, not the
  # row, or the second sighting clicks it again.
  #
  # And a row can be missed on a pass for reasons unrelated to the decision:
  # its name misreads, or it lands under the panel header and reads as nothing.
  # A second scan is cheaper than trying to make one pass perfect. Mid-career
  # that matters more than it looks: these are the skills already at full hint
  # discount, and skipping one leaves points unspent that a later hint level
  # cannot make any cheaper.
  # Read first, decide, then buy. "At full hint discount" says the price will
  # not improve; it says nothing about whether the skill is worth buying, and
  # on its own it spent points on whatever happened to be discounted. The
  # optimizer is the same judge that spends the rest at career end, so ask it
  # here too: of the skills that are already as cheap as they will ever be,
  # which would it take with the points in hand?
  #
  # Passing one over costs nothing. Max hint is max hint, so it will still be
  # this price at the end, when it can be weighed against everything on offer
  # instead of against only what happens to be discounted today.
  style, distance = uma_aptitudes()
  offered = {}
  for box, text, record, cost, hint in scan_rows():
    if not usable_here(record):
      continue
    if not at_max_discount(record, cost, hint):
      debug(f"{text!r} is not at max hint (hint {hint}, {cost} of"
            f" {record['cost']}); leaving it for the end of the career.")
      continue
    # The price on screen beats the database: it includes the hint discount.
    price = plausible_cost(record, cost) or record["cost"]
    offered.setdefault(base_name(record["name"]), dict(record, cost=price))

  if not offered:
    return False

  budget = check_skill_pts_for_plan()
  chosen = []
  if budget > 0:
    chosen = skill_score.plan(list(offered.values()), budget,
                              style=style, distance=distance)
  if not chosen:
    info(f"{len(offered)} skill(s) at full discount, but the optimizer would not"
         f" spend {budget} points on any of them yet; leaving them for the end.")
    return False

  wanted = {base_name(c["name"]) for c in chosen}
  info(f"Mid-career skill buy: {len(chosen)} of {len(offered)} full-discount"
       f" skills for {sum(c['cost'] for c in chosen)} of {budget} points: "
       + ", ".join(f"{c['name']} ({c['cost']})" for c in chosen))

  # Sweep, and remember what was already taken, for the same two reasons
  # buy_planned does.
  #
  # advance_one_screen deliberately leaves the last visible row on screen, so
  # every row is now seen at least twice per scan at different heights. That is
  # what stopped rows being missed, but it also means a single scan offers the
  # same skill twice - so a click has to be recorded against the skill, not the
  # row, or the second sighting clicks it again.
  #
  # And a row can be missed on a pass for reasons unrelated to the decision:
  # its name misreads, or it lands under the panel header and reads as nothing.
  # A second scan is cheaper than trying to make one pass perfect.
  bought = set()
  found = False
  for attempt in range(BUY_SWEEPS):
    if state.stop_event.is_set():
      break
    bought_this_sweep = 0
    for box, text, record, cost, hint in scan_rows():
      x, y, w, h = box
      if not record:
        continue
      name = base_name(record["name"])
      if name not in wanted or name in bought:
        continue
      if not is_btn_active((x, y, w, h)):
        info(f"{record['name']} is at full discount but not affordable yet.")
        continue
      info(f"Buy {record['name']} at {cost} (base {record['cost']}), a full hint discount.")
      control.click(x=x + 5, y=y + 5, duration=0.15)
      bought.add(name)
      bought_this_sweep += 1
      found = True
    if not bought_this_sweep:
      # Nothing was taken, so an identical sweep will not take anything either.
      break
  return found

def buy_planned():
  """Spend what is left at career end, chosen purely by the optimizer.

  **No tier floor here, deliberately.** The floor is a mid-career rule: while a
  career is running there is a reason to be picky, because a point spent now
  cannot be spent on something better later. At the end there is no later - the
  points are destroyed - so the only question is which affordable set is worth
  the most.

  The tier list is the wrong instrument for that anyway. It ranks skills by race
  performance, and Team Trials pays for **activation** whatever the skill does.
  Checked against the reference optimizer on a real screen, the floor rejected
  six of its picks - Hesitant Pace Chasers, Hesitant Front Runners, Subdued
  Front Runners, Frenzied Pace Chasers, Tail Held High - all cheap, reliable
  proccers that no race-performance list ranks. Removing it was worth
  56.7 -> 60.4 expected SV on the same budget.

  Two filters remain, and neither is about taste: the skill must not be a debuff
  on us, and it must be able to fire for this Uma. A skill that cannot proc is
  worth nothing at any price.

  Scans once to read what is offered and what it costs, plans, then sweeps to
  buy. Falls back to taking anything affordable if no plan can be made, since
  points left over are lost outright.
  """
  style, distance = uma_aptitudes()
  offered = {}
  for box, text, record, cost, hint in scan_rows():
    if not record or not skill_score.beneficial(record):
      continue
    if not skill_score.applicable(record, style=style, distance=distance):
      continue
    # The price on screen beats the database: it includes the hint discount.
    price = plausible_cost(record, cost) or record["cost"]
    offered.setdefault(base_name(record["name"]), dict(record, cost=price))

  budget = check_skill_pts_for_plan()
  # What the plan is measured against at the end. `budget` itself shrinks as
  # forced skills are taken off the top, so the summary would otherwise compare
  # the full spend against the optimizer's leftover and look overdrawn.
  total_budget = budget
  chosen = []
  # The Grand Concert gold skill is expensive for what it does (0.35 speed for
  # a 1.2s base, 380 points in career 3), so the optimizer passes it over. It
  # is the whole point of learning 18 songs, though, so it can be forced.
  forced = []
  if state.ALWAYS_BUY_GOLD_SKILL:
    forced = [c for name, c in offered.items() if GOLD_SKILL_MATCH(name) and c["cost"] <= budget]
    for card in forced:
      info(f"Buying {card['name']} first: grand_concert.always_buy_gold_skill is on ({card['cost']} points).")
      budget -= card["cost"]
      offered.pop(base_name(card["name"]), None)
  if offered and budget > 0:
    chosen = skill_score.plan(list(offered.values()), budget,
                              style=style, distance=distance)
    info(f"Optimizer picked {len(chosen)} of {len(offered)} offered skills,"
         f" {sum(c['cost'] for c in chosen)} of {budget} points,"
         f" {sum(skill_score.expected_sv(c) for c in chosen):.1f} expected SV.")

  chosen = forced + chosen
  if not chosen:
    warning("No skill plan could be made; falling back to buying whatever is affordable, because points left over at career end are lost.")
    return buy_anything_affordable()

  wanted = {base_name(c["name"]) for c in chosen}
  spend = sum(c["cost"] for c in chosen)
  info(f"Skill plan buys {len(chosen)} skills for {spend} of {total_budget} points: "
       + ", ".join(f"{c['name']} ({c['cost']})" for c in chosen))

  # Sweep more than once. A row can be missed for reasons that have nothing
  # to do with the plan: its name misreads on that pass, or selecting earlier
  # skills re-flows the list under the scan - the two scans of one run reached
  # the bottom after 9 and 13 passes respectively. Retrying is cheaper and
  # more honest than trying to make a single pass perfect.
  found = False
  for attempt in range(BUY_SWEEPS):
    if not wanted or state.stop_event.is_set():
      break
    bought_this_sweep = 0
    for box, text, record, cost, hint in scan_rows():
      if not record or base_name(record["name"]) not in wanted:
        continue
      x, y, w, h = box
      if not is_btn_active((x, y, w, h)):
        continue
      info(f"Buy {record['name']}")
      control.click(x=x + 5, y=y + 5, duration=0.15)
      wanted.discard(base_name(record["name"]))
      bought_this_sweep += 1
      found = True
    if not bought_this_sweep:
      # Nothing moved, so another identical sweep will not help either.
      break
    if wanted:
      debug(f"Still want {sorted(wanted)} after sweep {attempt + 1};"
            " scanning again.")
  if wanted:
    warning(f"Could not buy {sorted(wanted)} - not found on the screen.")
  return found

def buy_anything_affordable():
  """The old end-of-career behaviour, kept as the fallback."""
  bought = set()
  found = False
  for box, text, record, cost, hint in scan_rows():
    x, y, w, h = box
    if record and not skill_score.beneficial(record):
      continue
    # Rows repeat within a scan now - see buy_skill. An unrecognised row has no
    # name to key on, so it is guarded by position instead, which is the best
    # available and no worse than before.
    name = base_name(record["name"]) if record else f"@{y}"
    if name in bought:
      continue
    if not is_btn_active((x, y, w, h)):
      continue
    info(f"Buy {record['name'] if record else text}")
    control.click(x=x + 5, y=y + 5, duration=0.15)
    bought.add(name)
    found = True
  return found

def check_skill_pts_for_plan():
  """Skill points available to spend, or 0 when it cannot be read.

  Reads the buy screen's own counter, not the lobby's. core.state.check_skill_pts
  uses SKILL_PTS_REGION, which is where the lobby prints it; on this screen that
  crop lands on nothing and reads "v 2 DFFi 0". The budget came back 0, so no
  plan could ever be made and the end-of-career pass fell through to buying
  whatever was affordable - which is how a career ended up with Lone Wolf and
  Triple 7s.
  """
  try:
    points = extract_number(enhanced_screenshot(constants.SKILL_BUY_PTS_REGION),
                            value_range=SKILL_PTS_RANGE)
  except Exception as e:
    debug(f"Could not read skill points for the plan: {e}")
    return 0
  if points is None or points < 0:
    warning("Could not read the skill points on the buy screen; the optimizer"
            " cannot plan without a budget.")
    return 0
  debug(f"Skill points available to plan with: {points}")
  return points

# The skill name on this row OCRs badly enough that comparing it straight to a
# 14-entry config list almost never clears 0.8: "Professor of Curvature" reads
# as "rtotessoi 0i Cunvatule", "Hesitant Front Runners" as "Nesttam rtont
# nunnels". Measured over a career's worth of rows, one in fifteen matched.
#
# Matching against every real skill name instead and taking the closest fixes
# that, because the mangling is spread over a long string and the alternatives
# are hundreds of distinct names rather than 14. Same idea as canonicalising an
# event name before looking it up.

# master.mdb is the game's own data, so when it is the source the correct answer
# is always somewhere in this list. That changes what a bad score means: it is
# never "this skill is not in our list", it is "the OCR is wrong". The floor is
# there to catch a read that is not a skill name at all - an empty box, or the
# "Lvl 4" badge caught on its own - rather than to decide whether a skill exists.
#
# 60 because the lowest score a correct reading produced was 63.6. Nothing in
# either sample is currently rejected by it, so it is a backstop and not a
# filter that is doing daily work.
CANONICAL_MIN_SCORE = 60

# The game ships genuinely near-identical pairs - "risk-taker"/"risk-maker"
# score 90 against each other, "ignition"/"reignition" 88.9 - and a read that is
# nearly as much like one as the other is not evidence for either. Buying the
# wrong skill spends points that cannot be got back, so an ambiguous read is
# refused rather than guessed. It costs nothing measurable: across the 17 rows
# logged from a career and the 14 read live off the Skills panel, every correct
# match won by at least 6.5 points and by a median of 22.
#
# This is NOT protection against "a skill that is missing from the list" - with
# master.mdb there is no such thing. That was the original justification and it
# was wrong.
CANONICAL_MIN_MARGIN = 5

# The rank glyph is a trailing token, and OCR renders it as @, U, o or 0 about
# as often as it gets the circle right - so it cannot be used to tell the ○ and
# ◎ versions apart, and stripping it makes both match a config entry written
# with either. Anchored on whitespace so real names ending in a letter
# ("Up-Tempo", "Passing Pro", "Trick (Front)") are left alone: checked against
# all 383 names, this rewrites none of them.
RANK_SUFFIX = re.compile(r"\s+[○◎×@UuOo0()]{1,2}$")

_skill_names = None

def skill_names():
  """Every real skill name, from the game's own master.mdb. Loaded once.

  **The database is the only source.** It is what the game itself displays from
  and it is repatched on update, so every skill the buy screen can show is in
  it by construction. That is the property the matching leans on: a read that
  matches nothing here is a failed read, not an unknown skill.

  data/skills.json used to be a fallback and no longer is. It carried 383 names
  against the database's 980, and the very first real screen tested turned up a
  skill it was missing ("Louder! Tracen Cheer!"). A source that is sometimes
  incomplete cannot support the reasoning above, and silently degrading to one
  would be worse than not matching at all.

  Returns [] when the database cannot be read - on an emulator, where the game
  runs inside the emulator and writes no LocalLow copy on this machine, or on a
  non-default install that needs UMA_MASTER_MDB set. Canonicalisation switches
  itself off there and is_skill_match falls back to comparing the config list
  directly, which is what it did before any of this existed.
  """
  global _skill_names, _by_base
  if _skill_names is not None:
    return _skill_names
  _by_base = None

  _skill_names = masterdb.text_data(masterdb.SKILL_NAMES)
  if _skill_names:
    debug(f"Loaded {len(_skill_names)} skill names from master.mdb.")
  else:
    warning("No master.mdb, so skill names cannot be canonicalised;"
            " the configured list will only match a clean read.")
  return _skill_names

def base_name(name):
  """A skill name without its rank glyph, for comparing across ○ and ◎."""
  return RANK_SUFFIX.sub("", name.strip()).strip().lower()

_by_base = None

def distinct_bases():
  """{base name: the name to report for it}, in list order.

  Folded by base so the two ranks of one skill are a single candidate. Without
  that the runner-up is usually the same skill's other rank, the margin below is
  always 0, and the rule it exists for never fires.
  """
  global _by_base
  # Load the names first: skill_names() drops this cache on its own first
  # call, which would otherwise clear the dict midway through filling it.
  names = skill_names()
  if _by_base is None:
    _by_base = {}
    for name in names:
      _by_base.setdefault(base_name(name), name)
  return _by_base

def canonical_skill(text):
  """Closest real skill name to an OCR'd row, or None when nothing is close.

  fuzz.ratio deliberately, not WRatio - WRatio's partial matching sent
  "oprng Runner U" to "Front Runner Straightaways" instead of "Spring Runner".

  Refuses on a close second as well as on a low score: a read that is nearly as
  much like one skill as another is not evidence for either, and buying the
  wrong skill is worse than buying nothing.
  """
  by_base = distinct_bases()
  if not text.strip() or not by_base:
    return None

  keys = list(by_base)
  hits = process.extract(base_name(text), keys, scorer=fuzz.ratio, limit=2)
  if not hits or hits[0][1] < CANONICAL_MIN_SCORE:
    # Worth saying out loud when the names came from the game's own database:
    # the skill on screen is definitely in that list, so failing to find it is a
    # failed read, not an unknown skill. That makes this line the cheapest
    # signal there is that the OCR needs looking at.
    best = f"{hits[0][0]!r} at {hits[0][1]:.0f}" if hits else "nothing"
    debug(f"{text!r} matches no real skill name (closest {best}); reading it wrong.")
    return None

  runner_up = hits[1][1] if len(hits) > 1 else 0
  if hits[0][1] - runner_up < CANONICAL_MIN_MARGIN:
    debug(f"Read {text!r} is {hits[0][1]:.0f} like {hits[0][0]!r} but")
    debug(f" {runner_up:.0f} like {hits[1][0]!r}; too close to call.")
    return None

  return by_base[hits[0][0]]
