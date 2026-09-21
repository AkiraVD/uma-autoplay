"""Trackblazer's mode plumbing, parked on 2026-09-21.

Trackblazer was Global's third permanent scenario (2026-03-12): races replace
the career goals, each year wants a number of Result Pts, and the Umamusume's
own goals are switched off. The bot played it end to end on 2026-09-18,
holding RANK 1 through all three Twinkle Star Climax rounds.

**Why it is parked.** The Climax Store. It is a scrolling shelf with per-item
costs, stock counts and a coin balance, read through `core/menu_scan.py` and
priced by `shop_choice`, and it sits in the facility row where a race day
replaces the whole thing. Every turn of the mode spends screen-reading on it,
and two of the bot's worst loops came from that corner: the agenda-race badge
looping 302 times over 2h22m on 2026-09-20, and the bot going shopping on its
own scheduled-race turn and then reporting "Training button is not found"
because it was standing in the shop.

**What is still live, and must stay that way.** `core/trackblazer.py` and
`core/epithets.py` are not parked. They are data and arithmetic - the points,
coins and stat tables from master.mdb, and the epithet definitions - and
`server/race_plan.py` is built on them, so the Race Plan tab in the config page
still works. Nothing in this file is imported by the bot.

**What is here.** The scenario table and the two `career_lobby()` branches that
were removed from `core/execute.py`, kept as working code rather than as a
comment, so unparking is a re-wiring job and not an archaeology one. The
measured positions live on in `utils/constants.py` (`TB_CLIMAX_RACE_MOUSE_POS`,
`TB_TURN_DIGITS_REGION`, the `SHOP_*` family) and the layouts in
`docs/screen-map.md`.

To unpark: put `SCENARIO_TABLE` back in `core/scenarios.py` and its key back in
`state.SCENARIOS`, merge `TEMPLATES` into `core/execute.py`'s dict, and call
the two functions below from `career_lobby()` at the points their docstrings
name. `docs/TODO.md` has the list of what was left unfinished.
"""
import utils.constants as constants

# Was core/scenarios.py::TRACKBLAZER. Trackblazer ends in the Twinkle Star
# Climax rather than the URA Finale, so it needed its own race-day asset and
# button position, and its turn counter sits lower with taller digits.
# Measured 2026-09-17 by driving all three rounds by hand:
# assets/trackblazer/ts_climax_race_btn.png separates 0.923 worst-positive
# against 0.411 best-negative over five lobby frames, so unlike URA's the
# template match is reliable and the position is only a backstop.
SCENARIO_TABLE = {
  "key": "trackblazer",
  "name": "Trackblazer",
  "race_day_asset": "assets/trackblazer/ts_climax_race_btn.png",
  "race_day_pos": constants.TB_CLIMAX_RACE_MOUSE_POS,
  "turn_digits_region": constants.TB_TURN_DIGITS_REGION,
}

# Was in core/execute.py's templates dict. Merge back in to unpark.
TEMPLATES = {
  # The pink "Scheduled Race" ribbon on the lobby's Races button, which is how
  # a Trackblazer agenda race announces itself. There is no notification popup:
  # check_turn() reports an ordinary number on that turn (measured live at
  # Junior Late Aug, "Turn: 9"), so the race-day branch never fires for it and
  # without this key the turn looks like any other. sep: best negative 0.482.
  "scheduled_race": "assets/trackblazer/scheduled_race_badge.png",
  # Trackblazer's Climax Store button, in the facility grid between Recreation
  # and Races. Cut from the word and its frame rather than the badges: the
  # button carries an "ON SALE!" ribbon, a coin balance and a pink "N turn(s)"
  # tag that all change. It is a presence check, not decoration - the button
  # only exists after the debut race, and a race day replaces the whole
  # facility row, so clicking its position unguarded is a blind click.
  "tb_shop": "assets/trackblazer/shop_btn.png",
}


def open_scheduled_race(box, move_and_click, race_list_opened, warn):
  """The agenda race for this turn: press Races and let the generic race
  handlers take it from there.

  Went in `career_lobby()` immediately below the race-day branch and ABOVE the
  shop visit. That order is the point: the turn is an ordinary numbered one and
  the facility row is intact, so `tb_shop` matches too, and on the live run of
  2026-09-20 the bot went shopping on its own scheduled-race turn and then
  logged "Training button is not found" because it was standing in the shop.

  The caller must guard it to once per turn (`_scheduled_race_turn`). Without
  that the branch looped 302 times across 2h22m on a single turn (2026-09-20),
  because the lobby it returns to is unchanged and the badge still matches.
  That loop was NOT a missed click: opening the race list on a third
  consecutive race raises a "This will put you at 3 consecutive races."
  Warning, whose Cancel the generic handler takes while logging nothing. The
  real fix was a branch for that Warning above the generic cancel - which is
  cross-mode and stayed in `core/execute.py` when this was parked.

  This only presses Races. It deliberately does NOT call do_race(), which
  routes into race_select(False, None) - that clicks an aptitude-match badge,
  and on a scheduled turn the losing card carries one too (measured:
  match_track.png scores 1.000 on *both* cards), so it can deselect the
  scheduled race and enter the wrong one. The agenda has already chosen; the
  list opens with the race selected and a "Scheduled" badge on its card.

  Returns True when the race list opened.
  """
  # Aim below the match's centre: the template spans the "Scheduled Race"
  # ribbon and the Races button under it, and the button label sits nearer
  # y 978 than the centre's y 951. A centring click() cannot be used here.
  x, y, w, h = box
  move_and_click(x + w // 2, y + h - 45)
  if not race_list_opened():
    warn("TB-SCHEDULED: the race list did not open. Leaving this turn to "
         "the normal race logic rather than trying again.")
    return False
  return True


def visit_shop(box, turn, headroom):
  """The Climax Store, if this turn wants it.

  Went in `career_lobby()` BELOW the race-day branch, deliberately: a race day
  replaces the whole facility row, so the button is not there and its position
  belongs to something else entirely.

  Buying costs no turn, so this settled before the turn was planned, the way
  the Grand Concert Lessons visit does. The headroom passed in is the previous
  turn's reading - set_stat_headroom runs inside do_something, which has not
  happened yet - and logic.stat_headroom() documents why that is close enough.

  The visit is noted before it is attempted, not after: a shop that fails to
  open should cost this turn one try, not retry on every pass of the loop until
  the turn changes.

  Returns True when the loop should `continue`.
  """
  import core.parked.shop as shop
  if not shop.should_visit(turn):
    return False
  shop.note_visit(turn)
  if not shop.open_shop(box):
    return False
  shop.visit(headroom)
  shop.leave()
  return True
