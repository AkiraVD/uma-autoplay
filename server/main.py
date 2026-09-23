from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import os
import re
import sys
import time

from server.utils import load_config, save_config
from server import configs, master_data, images, race_lists, race_plan, tools
import core.state as state

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import logserver

app = FastAPI()

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.get("/config")
def get_config():
  return load_config()

@app.post("/config")
def update_config(new_config: dict):
  save_config(new_config)
  return {"status": "success", "data": new_config}

# Saved presets, all in uma_configs/ beside config.json; see server/configs.py.
# These have to stay above the "/{path:path}" fallback at the bottom of the
# file, or a GET would be answered with the page instead of the list.

@app.get("/configs")
def list_saved_configs():
  return configs.listing()

@app.get("/configs/{name}")
def read_saved_config(name: str):
  path = configs.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="CFG-E01 that name can't be used as a filename.")
  if not path.exists():
    raise HTTPException(status_code=404, detail=f"CFG-E02 no saved config called '{name}'.")
  try:
    return configs.read(path)
  except Exception as e:
    raise HTTPException(status_code=422, detail=f"CFG-E03 '{name}' isn't readable JSON ({e}).")

@app.post("/configs/{name}")
def write_saved_config(name: str, body: dict = Body(...)):
  path = configs.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="CFG-E01 that name can't be used as a filename.")
  configs.write(path, body)
  return {"status": "success", "name": path.stem}

@app.delete("/configs/{name}")
def delete_saved_config(name: str):
  path = configs.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="CFG-E01 that name can't be used as a filename.")
  if not path.exists():
    raise HTTPException(status_code=404, detail=f"CFG-E02 no saved config called '{name}'.")
  configs.delete(path)
  return {"status": "success", "name": path.stem}

# Saved race lists, all in uma_race_lists/ beside config.json; see
# server/race_lists.py. Same placement rule as the preset routes above: these
# have to stay over the "/{path:path}" fallback or a GET is answered with the
# page instead of the list.

@app.get("/race_lists")
def list_saved_race_lists():
  return race_lists.listing()

@app.get("/race_lists/{name}")
def read_saved_race_list(name: str):
  path = race_lists.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="RLIST-E01 that name can't be used as a filename.")
  if not path.exists():
    raise HTTPException(status_code=404, detail=f"RLIST-E02 no saved race list called '{name}'.")
  try:
    return race_lists.read(path)
  except Exception as e:
    raise HTTPException(status_code=422, detail=f"RLIST-E03 '{name}' isn't readable JSON ({e}).")

@app.post("/race_lists/{name}")
def write_saved_race_list(name: str, body: dict = Body(...)):
  path = race_lists.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="RLIST-E01 that name can't be used as a filename.")
  data = race_lists.normalise(body)
  if data is None:
    raise HTTPException(status_code=400, detail="RLIST-E04 a race list has to be an object.")
  if not data["races"]:
    raise HTTPException(status_code=400, detail="RLIST-E05 that list holds no race with a name, year and date.")
  race_lists.write(path, data)
  return {"status": "success", "name": path.stem, "races": len(data["races"])}

@app.delete("/race_lists/{name}")
def delete_saved_race_list(name: str):
  path = race_lists.path_for(name)
  if path is None:
    raise HTTPException(status_code=400, detail="RLIST-E01 that name can't be used as a filename.")
  if not path.exists():
    raise HTTPException(status_code=404, detail=f"RLIST-E02 no saved race list called '{name}'.")
  race_lists.delete(path)
  return {"status": "success", "name": path.stem}

@app.get("/data/races")
def race_data():
  """Career races for the Race Schedule picker; see server/master_data.py."""
  return master_data.get_races()

@app.get("/data/trainees")
def trainee_data():
  """Trainee cards for the Trainee picker; see server/master_data.py."""
  return master_data.get_trainees()

@app.get("/data/events")
def event_data():
  """Events and their choices for the Event pickers; see server/master_data.py."""
  return master_data.get_events()

@app.get("/data/epithets")
def epithet_data():
  """Every Trackblazer epithet, for the planner's target picker."""
  return race_plan.catalogue()

@app.post("/data/race_plan")
def race_plan_data(options: dict = Body(default={})):
  """A Trackblazer schedule chosen to earn epithets; see server/race_plan.py.

  POST because it takes options - aptitudes, targets, pinned turns - rather
  than because it changes anything; nothing is written. Like every route here
  it has to sit above the /{path:path} fallback, or the catch-all answers with
  index.html and the caller gets HTML where it expected JSON.
  """
  return race_plan.plan(
    targets=options.get("targets"),
    aptitudes=options.get("aptitudes"),
    fill=bool(options.get("fill", True)),
    include_op=bool(options.get("include_op", True)),
    min_aptitude=options.get("min_aptitude", race_plan.DEFAULT_FLOOR),
    locks=options.get("locks"),
    skip=options.get("skip"),
    race_bonus=options.get("race_bonus", 0.0),
    max_consecutive=options.get("max_consecutive", race_plan.MAX_CONSECUTIVE),
  )

RACE_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "races")

@app.get("/data/race_image/{name}")
def race_image(name: str):
  """The bot's own race picture, for the races that have one.

  These are the template-matching crops in `assets/races/` - about 140x70, and
  the only race artwork available offline. The game's own thumbnails live in
  its encrypted asset bundles, and GameTora (where server/images.py gets
  character and support art) does not host race art. So 30 of the planner's 402
  races have a picture and the rest do not; the picker draws its own tile for
  those rather than a broken image.

  The name reaches the filesystem, so it is matched against a whitelist and the
  resolved path has to sit inside the folder - the same discipline the
  `/{path:path}` fallback and server/configs.py use.
  """
  if not re.fullmatch(r"[A-Za-z0-9 '.\-()]{1,80}", name):
    raise HTTPException(status_code=404)
  path = os.path.realpath(os.path.join(RACE_ASSETS, f"{name}.png"))
  if not path.startswith(os.path.realpath(RACE_ASSETS) + os.sep) or not os.path.isfile(path):
    raise HTTPException(status_code=404)
  return FileResponse(path, media_type="image/png",
                      headers={"Cache-Control": "public, max-age=604800"})

@app.get("/data/images/{kind}/{item_id}.png")
def image(kind: str, item_id: str):
  """Character or support card picture, cached on disk; see server/images.py."""
  path = images.image_path(kind, item_id)
  if path is None:
    raise HTTPException(status_code=404)
  return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})

@app.get("/logs/data")
def log_data():
  """The log viewer's snapshot, for the config page's Live Log view.

  Same data as tools/logserver.py serves on its own port, but on this one, so
  a single address (a Tailscale proxy of port 8000, say) carries both pages.
  The bot's state comes from this process rather than a supervisor file.
  """
  data = logserver.snapshot("")
  # The page scrolls, so it can carry more than the phone view's 40 lines.
  data["recent"] = logserver.tail(logserver.LOG)[-150:]
  try:
    since = int(time.time() - os.path.getmtime(logserver.LOG))
  except OSError:
    since = None
  data["status"] = {"state": "running" if state.is_bot_running else "stopped",
                    "secs_since_log": since}
  # Which career of the run this is, for the Live Log header. `limit` is 0 when
  # career_start is set to run without one, and `started` counts only the
  # careers the bot began itself - a career already in progress when the bot
  # started is not one of them.
  data["careers"] = {"started": state.CAREERS_STARTED,
                     "limit": state.CAREER_START_MAX,
                     "enabled": state.CAREER_START_ENABLED}
  return data

@app.get("/telegram")
def telegram_get():
  """The Telegram settings, from telegram.json rather than the config.

  The token comes back so the page can show and edit it. That is the same
  exposure config.json already had over this port, and the port is the one the
  config page itself is served on.
  """
  return state.telegram_settings()

@app.post("/telegram")
def telegram_save(body: dict = Body(...)):
  """Write telegram.json and apply it to the running bot immediately.

  No Apply, and no restart: these settings are not part of the config, so
  nothing else has to be saved for them to take effect.
  """
  try:
    return state.save_telegram(body)
  except OSError as e:
    raise HTTPException(500, f"Could not write {state.TELEGRAM_FILE}: {e}")

@app.post("/telegram/test")
def telegram_test(body: dict = Body(default={})):
  """Send one message with the settings in the body, and say what happened.

  Takes the token and chat id from the request rather than the saved config, so
  the button works before Apply - which is the moment someone is most likely to
  have them wrong.

  They are passed to send_now rather than assigned to `state` around the call.
  The first version did assign, and two overlapping requests then read each
  other's credentials: a test posting no token at all reported success while a
  browser test was in flight beside it.
  """
  import core.notify as notify
  reason = notify.send_now(
    "Uma Autoplay: test message. If you can read this, the bot can reach you.",
    token=(body.get("token") or "").strip() or state.TELEGRAM_TOKEN,
    chat_id=str(body.get("chat_id") or "").strip() or state.TELEGRAM_CHAT_ID)
  return {"ok": reason is None, "reason": reason}

@app.get("/career/count")
def career_count():
  """The careers counted since the last reset, for the config page's button.

  Read from the ledger rather than from state, so it is right even when the bot
  has never been started in this process.
  """
  import core.career_start as career_start
  rows = career_start.started_careers()
  return {"started": len(rows),
          "limit": state.CAREER_START_MAX,
          "careers": rows[-5:]}

@app.post("/career/reset")
def career_reset():
  """Forget the careers counted so far, so a limit starts over.

  Clears both the ledger and the running bot's count - they are read from the
  same file at bot start but the bot may be mid-run, and a reset that the
  running bot ignored until its next restart would be the opposite of useful.
  """
  import core.career_start as career_start
  if not career_start.reset_count():
    raise HTTPException(500, "Could not write the career ledger")
  state.CAREERS_STARTED = 0
  return {"started": 0}

# main.py hands over its start/stop function at startup. The server cannot import
# main.py, which imports this module.
set_bot_running = None

def _bot_state():
  alive = bool(state.bot_thread and state.bot_thread.is_alive())
  if state.is_bot_running and alive:
    return "running"
  return "stopping" if alive else "stopped"

@app.get("/bot/status")
def bot_status():
  """Whether the bot is running, for the config page's Start/Stop button."""
  return {"state": _bot_state()}

@app.post("/bot/{action}")
def bot_action(action: str):
  """Start or stop the bot, the same as pressing Pause."""
  if action not in ("start", "stop"):
    raise HTTPException(status_code=404)
  if set_bot_running is None:
    raise HTTPException(status_code=503, detail="BOT-E12 bot controls aren't available: the server was started without main.py.")
  if set_bot_running(action == "start") == "stopping" and action == "start":
    raise HTTPException(status_code=409, detail="BOT-E13 the bot is still finishing its last step; try again in a moment.")
  return {"state": _bot_state()}

@app.get("/tools/status")
def tools_status():
  """The Tools tab's poll: whether the bot is running, and the current or last job."""
  return tools.status()

@app.post("/tools/run/{name}")
def tools_run(name: str, body: dict = Body(default={})):
  """Start one of server/tools.py's whitelisted commands."""
  job, problem = tools.start(name, (body or {}).get("at"), (body or {}).get("text"))
  if problem:
    raise HTTPException(status_code=problem[0], detail=problem[1])
  return job

@app.get("/tools/shots/{filename}")
def tools_shot(filename: str):
  """A PNG a tool saved under shots/, by bare file name only."""
  if not re.fullmatch(r"[\w.-]+\.png", filename):
    raise HTTPException(status_code=404)
  path = os.path.join(tools.SHOTS, filename)
  if not os.path.isfile(path):
    raise HTTPException(status_code=404)
  return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

@app.get("/tools/screen.jpg")
def tools_screen():
  """The game screen right now, for picking a Click at X,Y point; see server/tools.py."""
  try:
    data, size = tools.screen_jpeg()
  except Exception as e:
    raise HTTPException(status_code=503, detail=f"TOOL-E12 couldn't capture the screen ({e}).")
  return Response(content=data, media_type="image/jpeg",
                  headers={"Cache-Control": "no-store", "X-Screen-Size": f"{size[0]}x{size[1]}"})

PATH = "web/dist"

@app.get("/")
async def root_index():
  return FileResponse(os.path.join(PATH, "index.html"), headers={
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
  })

@app.get("/{path:path}")
async def fallback(path: str):
  file_path = os.path.join(PATH, path)
  headers = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
  }

  # "..%2F" survives routing, so without this any file on the drive could be read.
  inside_dist = os.path.realpath(file_path).startswith(os.path.realpath(PATH) + os.sep)
  if inside_dist and os.path.isfile(file_path):
    media_type = "application/javascript" if file_path.endswith((".js", ".mjs")) else None
    return FileResponse(file_path, media_type=media_type, headers=headers)

  return FileResponse(os.path.join(PATH, "index.html"), headers=headers)