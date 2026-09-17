from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import os
import re
import sys
import time

from server.utils import load_config, save_config
from server import configs, master_data, images, tools
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
  return data

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
  job, problem = tools.start(name, (body or {}).get("at"))
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