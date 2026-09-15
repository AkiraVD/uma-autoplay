# tools
import pyautogui
import utils.control as control
import time
import core.state as state
from .log import error, debug

def sleep(seconds=1):
  time.sleep(seconds * state.SLEEP_TIME_MULTIPLIER)

def get_secs(seconds=1):
  return seconds * state.SLEEP_TIME_MULTIPLIER

def drag_scroll(mousePos, to):
  '''to: negative to scroll down, positive to scroll up'''
  if not state.stop_event:
    return
  if not to or not mousePos:
    error("drag_scroll correct variables not supplied.")
  control.moveTo(mousePos, duration=0.1)
  control.mouseDown()
  control.moveRel(0, to, duration=0.25)
  control.mouseUp()
  control.click()

def click_and_hold(img: str = None, confidence: float = 0.8, minSearch:float = 2, text: str = "", duration_ms = 1000):
  # Click and hold for duration in milliseconds.
  if img is None:
    return False

  btn = pyautogui.locateCenterOnScreen(img, confidence=confidence, minSearchTime=minSearch)
  if btn:
    if text:
      debug(text)
    control.moveTo(btn, duration=0.225)
    control.mouseDown(btn)
    time.sleep(duration_ms / 1000)
    control.mouseUp(btn)