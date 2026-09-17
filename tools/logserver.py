"""Read-only live view of a career run, for watching from a phone.

The game owns the whole screen while the bot runs, and an always-on-top overlay
is not an option: the bot reads pixels right across the display - the big skip
button out at x 1500-1920, the taskbar check at x 0-200 - so anything drawn on
top corrupts the run it is meant to watch. This serves the same information to a
different device instead.

  python tools/logserver.py                    # prints the URL to open
  python tools/logserver.py --port 8181
  python tools/logserver.py --host 127.0.0.1   # local only, no LAN

Nothing here writes: it reads logs/log.txt and the supervisor's status.json and
serves them. It runs as its own process, so it cannot wedge the bot, and it
holds no lock on the log.

The path carries a random token so that exposing the port - through a tunnel,
say - does not put the page at a guessable address.
"""
import argparse
import html
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, "logs", "log.txt")

# Bare messages, no level prefix, so state is matched by phrase.
PATTERNS = {
  "year": r"^Year: (.+)$",
  "mood": r"^Mood: (.+)$",
  "turn": r"^Turn: (.+)$",
  "criteria": r"^Criteria: (.+)$",
  "energy": r"^Remaining energy guestimate = ([\d.]+)$",
  "stats": r"^Current stats: (\{.+\})$",
  "headroom": r"^Stat headroom: (\{.+\})$",
  "action": r"^(Training [A-Z]+\.|Race Day\.|Going out with the friend support\.|"
            r"No friend outing on offer, plain recreation\.|Rest.*|URA Finale)$",
  # "Rainbow training selected" was renamed to "Training selected ... training
  # weight", because the number is mostly support count, hints and measured
  # gains rather than rainbows. The old spelling stays matched so a log written
  # by an older run still parses.
  "reason": r"^(Training selected: .+|Rainbow training selected: .+|Best training: .+|"
            r"Going on a Recreation outing: .+|Falling back to .+|"
            r"No training cleared the weight threshold.*)$",
  "chain": r"^Recreation panel: ([a-z-]+) at step (\d+) of (\d+)",
  "readback": r"^(Outing readback for .+)$",
}

# Lines worth surfacing on their own. The log carries no severity, so these are
# the phrases that have actually mattered while debugging runs.
TROUBLE = re.compile(
  r"Not in the career lobby for|Traceback|position uncertain|Ignoring a Recreation|"
  r"unreadable|Couldn't|Coulnd't|didn't get selected|not found|too high|"
  r"No matching skills|Career complete|plain recreation", re.I)


def tail(path, limit=4000):
  try:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
      try:
        size = os.path.getsize(path)
        if size > 400_000:
          f.seek(size - 400_000)
          f.readline()
      except OSError:
        pass
      return [l.rstrip("\n") for l in f][-limit:]
  except OSError:
    return []


# utils/log.py writes 'HH:MM:SS LEVEL   ' before every message. The state
# patterns are anchored, so the prefix is stripped before matching - but the
# raw line is what gets displayed, because the timestamp is the point.
PREFIX = re.compile(r"^\d{2}:\d{2}:\d{2} +\w+ +")

def bare(line):
  return PREFIX.sub("", line)

def last_match(lines, pattern):
  rx = re.compile(pattern)
  for line in reversed(lines):
    m = rx.match(bare(line))
    if m:
      return m
  return None


# What ends a career, as far as this page is concerned: the bot being started
# (or restarted), and a career finishing inside one bot run.
RUN_MARKERS = (
  re.compile(r"\[BOT\] Starting"),
  re.compile(r"^Career complete\."),
)


def current_run(lines):
  """Just the lines belonging to the career in progress.

  Every field here is "the last line that matched", and logs/log.txt spans every
  run there has ever been. So a career that has only just started - and has not
  logged a Year, Turn or Mood line yet - showed the *previous* career's values:
  the page reported "Finale Underway / Race Day / URA Finale Finals" and last
  run's final stats beside the live log tail, which reads as nonsense.

  Falling back to everything when no marker is found keeps an old log readable
  rather than showing a blank page.
  """
  start = 0
  for i, line in enumerate(lines):
    b = bare(line)
    if any(rx.search(b) for rx in RUN_MARKERS):
      start = i + 1
  return lines[start:]


def snapshot(status_path):
  lines = tail(LOG)
  run = current_run(lines) or lines
  out = {"lines": len(lines), "run_lines": len(run)}
  for key, pattern in PATTERNS.items():
    m = last_match(run, pattern)
    if not m:
      continue
    out[key] = m.group(0) if key in ("action", "reason", "readback") else \
        (list(m.groups()) if len(m.groups()) > 1 else m.group(1))

  # Scoped too: a warning from the career before this one is already over,
  # and surfacing it sends the reader after a fault that no longer exists.
  out["trouble"] = [l for l in run[-400:] if TROUBLE.search(l)][-8:]
  out["recent"] = lines[-40:]

  try:
    with open(status_path, "r", encoding="utf-8") as f:
      out["status"] = json.load(f)
  except (OSError, ValueError):
    out["status"] = None
  return out


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>uma-auto</title><style>
:root{--bg:#f6f6f4;--fg:#1c1c1a;--dim:#6b6b64;--card:#fff;--line:#e2e2dc;--warn:#8a4b00;--warnbg:#fff4e5}
@media (prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e8e4;--dim:#9a9a92;--card:#1f1f24;--line:#2e2e34;--warn:#ffb765;--warnbg:#2a2015}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:14px}
h1{font-size:15px;margin:0 0 10px;color:var(--dim);font-weight:600;display:flex;justify-content:space-between}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
.k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--dim)}
.v{font-size:17px;font-weight:600;margin-top:2px;word-break:break-word}
.big{font-size:20px}
pre{margin:0;white-space:pre-wrap;word-break:break-word;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
.trouble{background:var(--warnbg);border-color:var(--warn)}
.trouble .k{color:var(--warn)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.ts{color:var(--dim)}
.lv{font-weight:700;padding:0 2px}
.lv-DEBUG{color:var(--dim)}
.lv-INFO{color:#2f7fbf}
.lv-WARNING{color:#b8860b}
.lv-ERROR{color:#b23b3b}
@media (prefers-color-scheme:dark){.lv-INFO{color:#6fb6ff}.lv-WARNING{color:#ffb765}.lv-ERROR{color:#ff8a8a}}
.ok{background:#3fa34d}.stale{background:#c9a227}.dead{background:#b23b3b}
</style></head><body><div class="wrap">
<h1><span id="hdr">uma-auto</span><span id="age" style="font-weight:400"></span></h1>
<div id="app"></div></div>
<script>
const E=(s)=>String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
// Escape first, then tint. The other order would let a log line inject markup.
const LINE=(s)=>E(s).replace(
  /^(\\d{2}:\\d{2}:\\d{2}) (DEBUG|INFO|WARNING|ERROR)(\\s+)/,
  (m,t,lv,sp)=>`<span class="ts">${t}</span> <span class="lv lv-${lv}">${lv}</span>${sp}`);
function cell(k,v,big){return v==null?'':`<div><div class="k">${E(k)}</div><div class="v ${big?'big':''}">${E(v)}</div></div>`}
// Every failure carries a code. Plain words like "unreachable" get read as a
// diagnosis - this page reporting that its own fetch failed was mistaken for a
// blocked port, and the hunt went after a firewall that was never in the way.
function fail(code, detail){
  document.getElementById('age').innerHTML =
    `<span class="dot dead"></span>${E(code)}`;
  document.getElementById('app').innerHTML =
    `<div class="card trouble"><div class="k">${E(code)}</div><pre>${E(detail)}</pre>` +
    `<pre>E01 page loaded, data call failed - proxy or server down
E02 server answered but not with data - wrong path or token
E03 server answered with something that is not JSON
E04 no supervisor status - the bot is not running</pre></div>`;
}
async function tick(){
  // Absolute, not relative: the page lives at /<token> with no trailing slash,
  // so a relative 'data' resolves to /data and 404s.
  const base = location.pathname.endsWith('/')
    ? location.pathname.slice(0, -1) : location.pathname;
  let d;
  try {
    const r = await fetch(base + '/data', {cache:'no-store'});
    if (!r.ok) { fail('DASH-E02', 'data endpoint returned HTTP ' + r.status); return; }
    try { d = await r.json(); }
    catch (e) { fail('DASH-E03', 'data was not valid JSON'); return; }
  } catch (e) { fail('DASH-E01', 'could not reach the data endpoint'); return; }
  const s=d.status||{};
  const secs=s.secs_since_log;
  const cls = s.state!=='running' ? 'dead' : (secs>120?'stale':'ok');
  document.getElementById('age').innerHTML=
    `<span class="dot ${cls}"></span>${E(s.state||'DASH-E04 bot not running')}`+
    (s.mins_running!=null?` · ${E(s.mins_running)}m`:'');
  let h='';
  h+=`<div class="card"><div class="grid">
      ${cell('Year',d.year,1)}${cell('Turn',d.turn)}${cell('Mood',d.mood)}
      ${cell('Energy',d.energy!=null?Math.round(d.energy)+'%':null)}</div></div>`;
  if(d.criteria) h+=`<div class="card">${cell('Goal',d.criteria)}</div>`;
  if(d.action||d.reason) h+=`<div class="card">${cell('Last action',d.action)}
      ${d.reason?`<div style="margin-top:8px"><div class="k">Why</div><pre>${E(d.reason)}</pre></div>`:''}</div>`;
  if(d.chain) h+=`<div class="card">${cell('Friend chain',
      Array.isArray(d.chain)?`${d.chain[0]} — step ${d.chain[1]} of ${d.chain[2]}`:d.chain)}
      ${d.readback?`<div style="margin-top:8px"><div class="k">Readback</div><pre>${E(d.readback)}</pre></div>`:''}</div>`;
  if(d.stats) h+=`<div class="card"><div class="k">Stats</div><pre>${E(d.stats)}</pre>
      ${d.headroom?`<div class="k" style="margin-top:8px">Headroom</div><pre>${E(d.headroom)}</pre>`:''}</div>`;
  if(d.trouble&&d.trouble.length) h+=`<div class="card trouble"><div class="k">Recent trouble</div>
      <pre>${d.trouble.map(LINE).join('\\n')}</pre></div>`;
  h+=`<div class="card"><div class="k">Log</div><pre>${d.recent.map(LINE).join('\\n')}</pre></div>`;
  document.getElementById('app').innerHTML=h;
}
tick(); setInterval(tick,3000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
  token = ""
  status_path = ""

  def _send(self, code, body, ctype):
    raw = body.encode("utf-8")
    self.send_response(code)
    self.send_header("Content-Type", ctype)
    self.send_header("Content-Length", str(len(raw)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(raw)

  def do_GET(self):
    path = self.path.split("?")[0].strip("/")
    if path == "ping":
      # No token and no JavaScript on purpose: it exists to prove the network
      # path works. A blank result then means the connection failed, not that
      # a fetch inside the page did.
      fresh = "?"
      try:
        fresh = f"{int(time.time() - os.path.getmtime(LOG))}s ago"
      except OSError:
        pass
      lines = [
        "DASH-OK  uma-auto dashboard is reachable.",
        f"server time : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"log updated : {fresh}",
        f"dashboard   : /{self.token}",
      ]
      body = chr(10).join(lines) + chr(10)
      self._send(200, body, "text/plain; charset=utf-8")
      return
    if path == self.token:
      self._send(200, PAGE, "text/html; charset=utf-8")
    elif path == f"{self.token}/data":
      self._send(200, json.dumps(snapshot(self.status_path)), "application/json")
    else:
      self._send(404, "not found", "text/plain; charset=utf-8")

  def log_message(self, *args):
    pass   # one line per poll per viewer is noise


def lan_ip():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip
  except OSError:
    return "127.0.0.1"


def resolve_token(explicit=None):
  """The URL path, kept stable across restarts.

  The token exists so that exposing this port - through a tunnel, say - does not
  put the page at a guessable address. Generating a fresh one on every start
  would satisfy that and break the link every time the bot restarts, so it is
  generated once and remembered. UMA_LOG_TOKEN overrides, matching UMA_LOG_DIR.
  """
  if explicit:
    return explicit
  env = os.environ.get("UMA_LOG_TOKEN")
  if env:
    return env
  path = os.path.join(os.path.dirname(LOG), "logserver_token.txt")
  try:
    if os.path.exists(path):
      saved = open(path, encoding="utf-8").read().strip()
      if saved:
        return saved
  except OSError:
    pass
  token = secrets.token_urlsafe(9)
  try:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
      f.write(token)
  except OSError:
    pass
  return token


def serve_in_background(port=8181, host="0.0.0.0", token=None, status=""):
  """Start the viewer on a daemon thread; return (url, error).

  Runs in the bot's own process so there is one thing to launch instead of two.
  That is safe because this only ever reads logs/log.txt and the supervisor's
  status file - it holds no lock and writes nothing, so it cannot wedge the run
  it is watching - and it sits on its own thread and its own port.

  A port already in use returns an error rather than raising: the viewer is a
  convenience and must not stop the bot from starting.
  """
  Handler.token = resolve_token(token)
  Handler.status_path = status or ""
  try:
    server = ThreadingHTTPServer((host, port), Handler)
  except OSError as e:
    return None, str(e)
  threading.Thread(target=server.serve_forever, daemon=True).start()
  where = "127.0.0.1" if host == "127.0.0.1" else lan_ip()
  return f"http://{where}:{port}/{Handler.token}", None


def main():
  ap = argparse.ArgumentParser(description="read-only live view of a career run")
  ap.add_argument("--port", type=int, default=8181)
  ap.add_argument("--host", default="0.0.0.0")
  ap.add_argument("--token", default=None, help="URL path; random if omitted")
  ap.add_argument("--status", default=None, help="supervisor status.json")
  args = ap.parse_args()

  Handler.token = resolve_token(args.token)
  Handler.status_path = args.status or ""

  server = ThreadingHTTPServer((args.host, args.port), Handler)
  where = "127.0.0.1" if args.host == "127.0.0.1" else lan_ip()
  print(f"http://{where}:{args.port}/{Handler.token}", flush=True)
  print(f"reading {LOG}", flush=True)
  try:
    server.serve_forever()
  except KeyboardInterrupt:
    pass
  return 0


if __name__ == "__main__":
  sys.exit(main())
