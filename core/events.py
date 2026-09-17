from rapidfuzz import fuzz
import re

import pyautogui
import utils.control as control

import core.state as state
import utils.constants as constants
from core.ocr import extract_text
from core.event_outcomes import best_option
from core.event_effects import best_choice
from core.state import read_choice_effects
from utils.log import debug, info, warning, error
from utils.screenshot import enhanced_screenshot
from utils.tools import sleep, get_secs

def note_unread_event(event_name):
  """Record that a choice-shaped screen offered no effects to read.

  Usually means it was not really a choice at all: dialogue-only events still
  match event_choice_1.png, and the game shows no Effects button for them
  because there is nothing to show. Harmless - the click just advances the
  dialogue - so this is a debug line rather than a warning.

  It stays because the same silence would cover a real multi-option event whose
  panel failed to read, and that one would be picked blind. The name is enough
  to go and capture the screen deliberately if a pattern shows up.
  """
  debug(f"No effects to read for {event_name!r}; falling back to the tables.")

def read_effects_panel(event_name=""):
  """Effect lines per option from the on-screen Choices panel, or [].

  The panel is the only source that is right by construction - it is the game
  stating what each option does, so it covers scenario events, patched events
  and anything the outcome tables have never seen.

  Options > Career > "Always display choice effects" opens it automatically,
  which is the case worth optimising for because it costs no clicks and so
  cannot leave a modal open that the main loop has no branch for. When it is
  off, the Effects button on the event bubble opens the same panel and this
  closes it again afterwards.
  """
  choices = read_choice_effects()
  if choices:
    return choices

  button = pyautogui.locateCenterOnScreen(
    "assets/buttons/effects_btn.png", confidence=0.8, minSearchTime=get_secs(1),
    region=constants.GAME_SCREEN_REGION)
  if not button:
    note_unread_event(event_name)
    return []

  debug("Choices panel is not open; using the Effects button.")
  control.moveTo(button[0], button[1], duration=0.2)
  control.click()
  sleep(1)
  choices = read_choice_effects()

  # Close it whether or not the read worked. Leaving it open would hide the
  # choice list behind a modal the dispatch has no branch for, which is the
  # failure this whole feature is meant to avoid.
  x, y = constants.CHOICES_CLOSE_MOUSE_POS
  control.moveTo(x, y, duration=0.2)
  control.click()
  sleep(0.5)
  return choices

# Grand Concert, Senior Early November, only with 16+ songs learned: "Closer
# Together" (JP あなたと私をつなげるライブ). Five lyric lines, each a skill hint.
# Every line is one skill pair, white and gold, sharing a group_id in
# master.mdb (checked 2026-09-16):
#   Full Tilt        / Full Speed!        (group 20228)
#   Focus            / Concentration      (group 20043)
#   Rosy Outlook     / Trackblazer        (group 20071)
#   All I've Got     / Come What May      (group 20170)
#   Go with the Flow / Lane Legerdemain   (group 20050)
# The Choices panel names the white one, so the gold is the upgrade a career
# can earn. What decides that, and whether the deck changes which lines are
# offered at all, is NOT in master.mdb: no support card teaches any of these
# skills, the trainees that can learn them are many (Focus alone has seven),
# and the option text lives in the story asset bundles. The pick is therefore
# the config's (grand_concert.lyrics_option), and the Choices panel is logged
# so the list can be compared against the deck later.
# The English name is not certain, so the event is also known by its options
# naming several of these skills.
LYRICS_EVENT_NAME = "closer together"
LYRICS_SKILLS = ("full speed", "full tilt", "concentration", "focus", "trackblazer",
                 "rosy outlook", "come what may", "all i've got", "lane legerdemain")

def is_lyrics_event(event_name, panel):
  if event_name and fuzz.ratio(event_name.strip().lower(), LYRICS_EVENT_NAME) >= 80:
    return True
  text = " ".join(" ".join(option) for option in (panel or [])).lower()
  return sum(1 for skill in LYRICS_SKILLS if skill in text) >= 3

def event_choice(event_name):
  threshold = 0.8
  choice = 0

  # Deliberately ahead of the name match: the panel needs no name, so it works
  # on an event whose title will not OCR at all. The config still wins over it
  # below, because a chain event is picked to continue the chain rather than
  # for the best immediate effects, and the panel only shows the immediate
  # effects.
  panel = read_effects_panel(event_name)

  if state.GRAND_CONCERT_SEEN and is_lyrics_event(event_name, panel):
    info(f"'Closer Together': taking lyric line {state.LYRICS_OPTION} (grand_concert.lyrics_option).")
    # Which lines this event offers, and which of them carry a hint, is not in
    # master.mdb: the option text lives in the story asset bundles, and no
    # support card teaches the five lyric skills (checked 2026-09-16). The
    # panel is logged, so a later comparison against the deck has something to
    # work from.
    debug(f"'Closer Together' panel: {panel}")
    return state.LYRICS_OPTION

  if not event_name:
    if panel:
      scored, reason = best_choice(panel)
      if scored:
        info(f"Unnamed event, scored its Choices panel: {reason}")
        return scored
    return choice

  best_event_name, similarity = find_best_match(event_name, state.EVENT_CHOICES)
  debug(f"Best event name match: {best_event_name}, similarity: {similarity}")

  if similarity >= threshold:
    events = next(
      (e for e in state.EVENT_CHOICES if e["event_name"] == best_event_name),
      None,  # fallback
    )
    debug(
      f"Event found: {event_name} has {similarity * 100:.2f}% similarity with {events['event_name']}"
    )
    debug(f"event name: {events['event_name']}, chosen: {events['chosen']}")
    choice = events["chosen"]
    return choice
  else:
    debug(
      f"No event found, {event_name} has {similarity * 100:.2f}% similarity with {best_event_name}"
    )
    # Nothing configured for this event. The panel comes first because it is
    # the game's own statement of the outcomes, where the tables are a guess
    # keyed on a name that had to survive OCR.
    if panel:
      scored, reason = best_choice(panel)
      if scored:
        info(f"Scored the Choices panel for {event_name}: {reason}")
        return scored
      debug(f"Choices panel gave nothing for {event_name} ({reason}).")

    # Otherwise fall back to scoring its outcomes from the tables.
    scored_choice, reason = best_option(event_name)
    if scored_choice:
      info(f"Scored outcomes for {event_name}: {reason}")
      return scored_choice
    debug(f"No outcome data for {event_name} either ({reason}), taking top choice.")
    return choice

def get_event_name():
  img = enhanced_screenshot(constants.EVENT_NAME_REGION)
  text = extract_text(img)
  debug(f"Event name: {text}")
  return text

def find_best_match(text: str, event_list: list[dict]) -> tuple[str, float]:
  """Find the best matching skill and similarity score"""
  if not text or not event_list:
    return "", 0.0

  best_match = ""
  best_similarity = 0.0

  for event in event_list:
    event_name = event["event_name"]
    clean_text = re.sub(
      r"\s*\((?!Year 2\))[^\)]*\)", "", event_name
    ).strip()  # remove parentheses
    clean_text = re.sub(r"[^\x00-\x7F]", "", clean_text)  # remove non-ASCII
    similarity = fuzz.token_sort_ratio(clean_text.lower(), text.lower()) / 100
    if similarity > best_similarity:
      best_similarity = similarity
      best_match = event_name

  return best_match, best_similarity