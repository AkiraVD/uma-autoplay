import pyautogui
import utils.control as control
from utils.tools import get_secs

def ura():
  race_btn = pyautogui.locateCenterOnScreen("assets/ura/ura_race_btn.png", confidence=0.8, minSearchTime=get_secs(5))
  if race_btn:
    control.click(race_btn)