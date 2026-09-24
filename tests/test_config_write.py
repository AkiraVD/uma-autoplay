"""Who is allowed to write config.json, and what must never end up inside it.

Run with `python tests/test_config_write.py` from the repo root. Needs neither
the game nor a server - it drives server/utils.py against a throwaway file and
reads the rest off the source.

Both halves of a real revert are covered. On 2026-09-24 a Maruzensky config
kept coming back over a Mihono Bourbon one, and it took two mistakes:

  - `web/src/App.tsx` imported `config.json`, so Vite inlined one machine's
    real settings into the bundle. A page starting from that snapshot posts it
    back as if it were the current config.
  - `POST /config` writes the whole document, so whichever tab was touched last
    won outright - a phone left open on yesterday's settings put them all back.

The page now starts from the template and quotes the version it read.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join(ROOT, "tests", "logs"))

import server.utils as U  # noqa: E402

failures = []


def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)


def test_version():
  """The fingerprint has to change on a write and hold still otherwise."""
  original = U.CONFIG_PATH
  with tempfile.TemporaryDirectory() as d:
    U.CONFIG_PATH = Path(d) / "config.json"
    try:
      ok("a missing config has a version anyway", U.config_version() == "0")
      U.save_config({"trainee": "A"})
      first = U.config_version()
      ok("a written config has a real version", first != "0", first)
      ok("reading it again does not move it", U.config_version() == first)
      ok("and the round trip keeps the contents",
         U.load_config() == {"trainee": "A"})
      U.save_config({"trainee": "B"})
      ok("a second write moves it", U.config_version() != first)
    finally:
      U.CONFIG_PATH = original


def test_the_route_refuses_a_stale_write():
  src = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  route = src[src.index('@app.post("/config")'):src.index('@app.get("/configs")')]
  ok("the write is gated on the version the page read",
     "x_config_version != current" in route)
  ok("and a stale one is refused rather than applied",
     "status_code=409" in route and route.index("409") < route.index("save_config"))
  ok("the version goes out with the config it describes",
     'response.headers["X-Config-Version"]' in route)
  ok("a GET hands one out too",
     'response.headers["X-Config-Version"]'
     in src[src.index('@app.get("/config")'):src.index('@app.post("/config")')])
  # The header is read off the response, which a browser hides cross-origin -
  # and `npm run dev` runs on another origin.
  ok("and the browser is allowed to read it",
     'expose_headers=["X-Config-Version"]' in src)


def test_the_page_bakes_in_no_config():
  """The regression that started it: config.json compiled into the bundle."""
  app = open(os.path.join("web", "src", "App.tsx"), encoding="utf-8").read()
  ok("App.tsx does not import the live config",
     'from "../../config.json"' not in app)
  ok("it starts from the template instead",
     'from "../../config.template.json"' in app)

  hook = open(os.path.join("web", "src", "hooks", "useConfig.ts"), encoding="utf-8").read()
  ok("every write quotes the version it read", '"X-Config-Version"' in hook)
  ok("and a refused write re-reads rather than retrying",
     "409" in hook and hook.index("409") < hook.index("applied.current = body"))

  # The built bundle is committed and served by the bot, so a stale dist would
  # put the snapshot back however the source reads.
  dist = Path("web") / "dist" / "assets"
  bundles = sorted(dist.glob("index-*.js"))
  ok("the built bundle exists", bool(bundles), str(dist))
  config = json.load(open("config.json", encoding="utf-8")) if os.path.exists("config.json") else {}
  trainee = (config.get("trainee") or "").strip()
  if trainee and bundles:
    baked = [b.name for b in bundles if trainee in b.read_text(encoding="utf-8", errors="replace")]
    ok("and carries no trainee from this machine's config", not baked, str(baked))


def test_a_running_career_picks_up_a_change():
  """An applied edit used to wait for the next bot start to mean anything."""
  import core.state as state
  ok("the flag exists and starts clear",
     hasattr(state, "config_dirty") and not state.config_dirty.is_set())

  src = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  route = src[src.index('@app.post("/config")'):src.index('@app.get("/configs")')]
  ok("a write raises it",
     "state.config_dirty.set()" in route
     and route.index("save_config(new_config)") < route.index("config_dirty.set()"))

  body = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  loop = body[body.index("while state.is_bot_running"):]
  ok("the loop takes it before reading the frame",
     loop.index("config_dirty.is_set()") < loop.index("screen = ImageGrab.grab()"))
  ok("and clears it before reloading, so a write during the reload is not lost",
     loop.index("config_dirty.clear()") < loop.index("state.reload_config()"))
  ok("a bad config leaves the run on the one it has",
     "Carrying on with the one already loaded" in loop)

  start = open("main.py", encoding="utf-8").read()
  ok("a bot start has nothing left to pick up",
     start.index("state.reload_config()") < start.index("state.config_dirty.clear()"))


def main():
  for test in (test_version, test_the_route_refuses_a_stale_write,
               test_the_page_bakes_in_no_config,
               test_a_running_career_picks_up_a_change):
    print(f"--- {test.__name__}")
    test()
  print("")
  print("FAILED: " + ", ".join(failures) if failures else "all checks passed")
  return 1 if failures else 0


if __name__ == "__main__":
  sys.exit(main())
