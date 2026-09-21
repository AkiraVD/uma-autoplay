"""What each game mode does differently, in one table.

Every mode plays the same career. They differ in a handful of screens, button
positions and assets, and those differences used to sit inline as
`X if state.GRAND_CONCERT_SEEN else Y`, scattered over ten places in
core/execute.py, core/state.py and core/events.py.

That shape has a failure mode worth naming, because it already cost a career.
A mode with no case of its own does not get an error - it silently inherits
URA's value. Trackblazer had no case anywhere, so its Twinkle Star Climax race
day fell through to URA's button position (690,905) and blind-clicked into the
Shop, three laps in a row, without starting a single race. Nothing logged a
warning, because nothing knew a case was missing.

Here a mode names its values explicitly. Inheritance still happens - a mode
starts from URA and overrides what differs - but it happens once, visibly, in
one table that can be read top to bottom.

**Data only.** Nothing here reads the screen or clicks; callers do that. Keep
it that way, so a mode's differences stay reviewable without tracing the loop.
"""
import core.state as state
import utils.constants as constants

# URA Finale is the base every other mode starts from: it is the career the
# game shipped with, and the one whose positions the shared code grew around.
URA = {
  "key": "ura",
  "name": "URA Finale",
  # The race-day lobby's big pink race button. The template is heavily animated
  # (see the note on FINALE_RACE_MOUSE_POS), so the position is the fallback
  # that actually runs most of the time.
  "race_day_asset": "assets/buttons/ura_finale_race_btn.png",
  "race_day_pos": constants.FINALE_RACE_MOUSE_POS,
  "career_complete_skills_pos": constants.CAREER_COMPLETE_SKILLS_MOUSE_POS,
  # Where the calendar box's turns-left digits sit. Modes draw that box at
  # different digit sizes and heights, so the crop is per mode.
  "turn_digits_region": constants.TURN_DIGITS_REGION,
}

# Unity Cup ends in the URA Finale and keeps its race-day layout, so it differs
# only in things handled elsewhere (Spirit gauges, the pre-infirmary burst peek).
UNITY = {**URA, "key": "unity", "name": "Unity Cup"}

# Grand Concert also ends in the URA Finale, but its lobby carries a fourth
# Lessons button, which shifts the race button left and moves the
# career-complete Skills button.
GRAND_CONCERT = {
  **URA,
  "key": "grand_concert",
  "name": "Grand Concert",
  "race_day_pos": constants.GC_FINALE_RACE_MOUSE_POS,
  "career_complete_skills_pos": constants.GC_CAREER_COMPLETE_SKILLS_MOUSE_POS,
}

# Trackblazer had a table here too - it ends in the Twinkle Star Climax rather
# than the URA Finale, so it needed its own race-day asset, button position and
# turn-digits crop. It was parked on 2026-09-21 and the table moved with the
# rest of its screen code to core/parked/trackblazer_mode.py, which keeps the
# measured values rather than losing them to git history. Nothing here reads it.
#
# The failure this module exists to prevent applies to *removing* a mode as
# much as adding one: a Trackblazer career started now has no case of its own
# and will silently inherit URA's, exactly as Trackblazer itself once did. That
# is why state.saw_scenario() warns loudly when it sees a parked mode's screen
# instead of quietly carrying on.
BY_KEY = {m["key"]: m for m in (URA, UNITY, GRAND_CONCERT)}


def current():
  """The mode the bot believes it is in, as one of the tables above.

  Read through the flags rather than state.SCENARIO, because "auto" decides the
  mode from what it has seen on screen. The flags are read at call time, never
  captured, for the reason core/state.py's docstring gives.
  """
  if state.GRAND_CONCERT_SEEN:
    return GRAND_CONCERT
  if state.UNITY_SEEN:
    return UNITY
  return URA


def get(field):
  """One field for the current mode. Raises if no mode defines it.

  Deliberately not a .get() with a default: a missing field is a mode that was
  never given a case, which is the bug this module exists to make loud.
  """
  mode = current()
  if field not in mode:
    raise KeyError(f"{mode['name']} has no '{field}'; add it to core/scenarios.py")
  return mode[field]
