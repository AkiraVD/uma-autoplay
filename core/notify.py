"""Telegram messages, so a run that is not being watched can still be followed.

The bot plays for hours on a headless display and the things worth knowing are
rare: a career started, a career finished, the client froze, the game came back.
This sends those four to a Telegram chat.

Three rules shape it:

- **It never blocks the bot.** Sending goes through a queue and one worker
  thread, so a slow or unreachable Telegram costs the career nothing. A single
  worker rather than a thread per message, so the messages arrive in the order
  the run made them.
- **It never raises.** Every failure is a warning in the log and nothing else.
  A notifier that could end a career would be worse than no notifier.
- **It never logs the token.** The log goes to a file, a viewer page and a
  tailnet address; the token is the one thing in the config that is a secret.

`urllib` rather than `requests`, which is not a dependency of this project and
is not worth becoming one for two HTTPS calls.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request

import core.state as state
from utils.log import warning, debug

API = "https://api.telegram.org/bot{token}/{method}"
# Long enough for a slow phone network, short enough that a dead endpoint does
# not keep a worker thread alive across a whole career.
TIMEOUT = 15
# Telegram's own limit is 4096 characters; nothing here comes close, but a
# truncated message is better than a rejected one.
MAX_LEN = 3500

_queue = None
_worker = None
_lock = threading.Lock()
_warned = set()

def configured():
  return bool(state.TELEGRAM_TOKEN and state.TELEGRAM_CHAT_ID)

def _creds(token=None, chat_id=None):
  """The token and chat to use: the ones passed, else the configured ones."""
  return (token if token is not None else state.TELEGRAM_TOKEN,
          chat_id if chat_id is not None else state.TELEGRAM_CHAT_ID)

def _redact(text, token=None):
  """Take the token out of anything on its way to a log or an API response.

  The sendMessage URL has the token in its path, and an exception is free to
  quote whatever it likes - `OSError: cannot connect to https://.../bot<token>/`
  is a real shape. Rather than audit every error string for whether it might
  carry the URL, scrub the token from all of them.
  """
  token = token if token is not None else state.TELEGRAM_TOKEN
  if token and text:
    return str(text).replace(token, "<token>")
  return text

def _warn_once(key, message):
  if key not in _warned:
    _warned.add(key)
    warning(message)

def _post(text, token=None, chat_id=None):
  """One sendMessage call. Returns None on success, or a reason to log.

  The credentials are arguments, defaulting to the configured ones. They used
  to be read from `state` alone, and the config page's test button set `state`
  around the call to try a token before saving it - which meant two overlapping
  requests could read each other's, and one did: a test with no token at all
  reported success because a browser test was in flight beside it.
  """
  token, chat_id = _creds(token, chat_id)
  data = urllib.parse.urlencode({
    "chat_id": chat_id,
    "text": text[:MAX_LEN],
    "disable_web_page_preview": "true",
  }).encode()
  url = API.format(token=token, method="sendMessage")
  try:
    with urllib.request.urlopen(url, data=data, timeout=TIMEOUT) as res:
      body = json.loads(res.read().decode("utf-8", "replace") or "{}")
    if not body.get("ok"):
      # description carries Telegram's own reason: a wrong chat id reads
      # "chat not found", a wrong token never gets this far.
      return _redact(body.get("description"), token) or "Telegram refused the message"
    return None
  except urllib.error.HTTPError as e:
    # The URL contains the token, so report the code and not the URL.
    detail = ""
    try:
      detail = json.loads(e.read().decode("utf-8", "replace")).get("description", "")
    except Exception:
      pass
    return _redact(f"HTTP {e.code}{': ' + detail if detail else ''}", token)
  except Exception as e:
    return _redact(f"{type(e).__name__}: {e}", token)

def _run():
  while True:
    text = _queue.get()
    try:
      reason = _post(text)
      if reason:
        _warn_once(reason, f"Telegram: {reason}. Messages will keep being"
                           " attempted; this is logged once per reason.")
      else:
        debug(f"Telegram: sent {len(text)} chars.")
    except Exception as e:
      # The worker must outlive anything one message can do to it. Without
      # this the thread dies on the first raise and every later notification
      # is lost in silence - which is the one failure a notifier must not
      # have. _post catches its own errors, so getting here means something
      # further out went wrong: the logging call itself, most likely.
      try:
        _warn_once(f"worker:{type(e).__name__}",
                   f"Telegram: {type(e).__name__} while sending; the notifier"
                   " is carrying on.")
      except Exception:
        pass
    finally:
      _queue.task_done()

def _ensure_worker():
  global _queue, _worker
  with _lock:
    if _queue is None:
      _queue = queue.Queue()
    if _worker is None or not _worker.is_alive():
      # Daemon: the bot thread ending should not be held up by a message in
      # flight, and anything queued at that point is no longer interesting.
      _worker = threading.Thread(target=_run, name="telegram", daemon=True)
      _worker.start()

def send(text):
  """Queue a message. True when it was queued, False when it was not.

  False is the ordinary case for an unconfigured or switched-off notifier, not
  an error - every caller ignores the return except the test button.
  """
  if not state.TELEGRAM_ENABLED:
    return False
  if not configured():
    _warn_once("unconfigured",
               "Telegram is on but the token or chat id is empty; not sending.")
    return False
  _ensure_worker()
  _queue.put(text)
  return True

def send_now(text, token=None, chat_id=None):
  """Send on this thread and report the outcome, for the config page's test.

  The queue is the right shape for the bot and the wrong shape for a button
  that has to say whether it worked. Credentials are passed in rather than
  taken from the config, so trying an unsaved token cannot disturb the running
  bot or another request doing the same thing.
  """
  token, chat_id = _creds(token, chat_id)
  if not (token and chat_id):
    return "The token and chat id both have to be set."
  return _post(text, token, chat_id)


# --- Commands ---------------------------------------------------------------
#
# The other direction: the phone asks and the bot answers. Only /health so far,
# because "is it still going?" is the question an unattended run actually
# raises at 2am, and the answer already exists as tools/health.py.
#
# Long polling rather than a webhook: a webhook would need this machine to be
# reachable from the internet, which is the opposite of what running the game
# on a headless display in the corner is for.

# Telegram holds the request open this long when there is nothing to report, so
# an idle listener is one hanging request rather than a poll every few seconds.
POLL_SECONDS = 25
# The health check is a subprocess on purpose: it is what the terminal and the
# Tools tab already run, so the answer on the phone is the same text, and a
# wedged check cannot take the bot's own process with it.
HEALTH_TIMEOUT = 90
# Telegram's caption limit. The health report has run to ~520 characters, so it
# fits and the whole answer arrives as one photo with its text underneath.
CAPTION_LEN = 1024
# Well under Telegram's 10MB for sendPhoto; a 1920x1080 frame is ~1-2MB.
MAX_PHOTO_BYTES = 9 * 1024 * 1024

_listener = None
_offset = None

COMMANDS = {
  "/health": "how the run is doing right now",
  "/help": "this list",
}

def _api(method, token, params=None, timeout=TIMEOUT):
  url = API.format(token=token, method=method)
  if params:
    url += "?" + urllib.parse.urlencode(params)
  with urllib.request.urlopen(url, timeout=timeout) as res:
    return json.loads(res.read().decode("utf-8", "replace") or "{}")

def _health():
  """tools/health.py's own words, and the screenshot it saved.

  Returns (text, photo path or None). The picture is the point of asking from
  a phone: "turn not advancing" tells you something is wrong, and the frame
  tells you what - a dialog nobody handled, a frozen scene, the home screen.
  """
  repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  try:
    done = subprocess.run([sys.executable, os.path.join("tools", "health.py")],
                          cwd=repo, capture_output=True, text=True,
                          timeout=HEALTH_TIMEOUT)
  except subprocess.TimeoutExpired:
    return f"The health check did not finish within {HEALTH_TIMEOUT}s.", None
  except Exception as e:
    return f"Could not run the health check: {type(e).__name__}: {e}", None
  # It exits 1 or 2 for WARN and FAIL, which are results rather than failures.
  out = (done.stdout or "").strip()
  if not out:
    return (done.stderr or "").strip() or "The health check said nothing.", None
  # It prints the frame it saved; take the path from its own output rather than
  # guessing at the newest file in shots/, which the bot is also writing to.
  shot = None
  for line in out.splitlines():
    if "screenshot:" in line:
      candidate = line.split("screenshot:", 1)[1].strip()
      if os.path.exists(candidate):
        shot = candidate
  return out, shot

def _send_photo(path, caption, token=None, chat_id=None):
  """sendPhoto as multipart/form-data. Returns None on success, else a reason.

  Hand-rolled because urllib has no multipart and `requests` is not a
  dependency of this project - the same reason the rest of this module uses
  urllib.
  """
  token, chat_id = _creds(token, chat_id)
  try:
    size = os.path.getsize(path)
    if size > MAX_PHOTO_BYTES:
      return f"the frame is {size // 1024 // 1024}MB, too big to send"
    with open(path, "rb") as f:
      blob = f.read()
  except OSError as e:
    return f"could not read the frame: {e}"

  boundary = "----uma" + uuid.uuid4().hex
  fields = {"chat_id": str(chat_id)}
  if caption:
    fields["caption"] = caption[:CAPTION_LEN]
  body = b""
  for name, value in fields.items():
    body += (f"--{boundary}\r\n"
             f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
             f"{value}\r\n").encode("utf-8")
  body += (f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="photo";'
           f' filename="{os.path.basename(path)}"\r\n'
           f"Content-Type: image/png\r\n\r\n").encode("utf-8")
  body += blob + b"\r\n" + f"--{boundary}--\r\n".encode("utf-8")

  request = urllib.request.Request(
    API.format(token=token, method="sendPhoto"), data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
  try:
    with urllib.request.urlopen(request, timeout=TIMEOUT) as res:
      answer = json.loads(res.read().decode("utf-8", "replace") or "{}")
    if not answer.get("ok"):
      return _redact(answer.get("description"), token) or "Telegram refused the photo"
    return None
  except Exception as e:
    return _redact(f"{type(e).__name__}: {e}", token)

def _handle(text):
  command = (text or "").strip().split()[0].lower() if (text or "").strip() else ""
  # Telegram appends @thebotname when a command is used in a group.
  command = command.split("@")[0]
  if command == "/health":
    return _health()
  if command in ("/help", "/start"):
    return ("Uma Autoplay:\n"
            + "\n".join(f"{c}  -  {w}" for c, w in COMMANDS.items())), None
  return None

def _process(updates, token, chat):
  """Answer what the configured chat asked, and ignore everyone else.

  Its own function so the filter can be tested: anyone can find a bot by name
  and message it, and nobody but the configured chat gets to ask this machine
  anything. The offset advances for ignored messages too - otherwise a stranger
  could park one update at the head of the queue and the listener would fetch
  it forever.
  """
  global _offset
  answered = 0
  for update in updates:
    _offset = update["update_id"] + 1
    message = update.get("message") or update.get("channel_post") or {}
    if str((message.get("chat") or {}).get("id")) != str(chat):
      continue
    reply = _handle(message.get("text"))
    if not reply:
      continue
    text, photo = reply
    # One message when it fits: the frame with the report as its caption.
    if photo and text and len(text) <= CAPTION_LEN:
      if _send_photo(photo, text, token, chat) is None:
        answered += 1
        continue
      # The photo failed; the text still has to arrive.
    if text:
      _post(text, token, chat)
    if photo:
      _send_photo(photo, None, token, chat)
    answered += 1
  return answered

def _listen():
  global _offset
  while True:
    try:
      if not (state.TELEGRAM_ENABLED and configured()):
        time.sleep(5)
        continue
      token, chat = _creds()
      if _offset is None:
        # Start from now: without this, every restart would replay whatever
        # was sent while the bot was down, including a /health from hours ago.
        body = _api("getUpdates", token, {"offset": -1, "limit": 1})
        found = body.get("result") or []
        _offset = (found[-1]["update_id"] + 1) if found else 0
        continue
      body = _api("getUpdates", token,
                  {"offset": _offset, "timeout": POLL_SECONDS},
                  timeout=POLL_SECONDS + 10)
      _process(body.get("result") or [], token, chat)
    except Exception as e:
      _warn_once(f"listen:{type(e).__name__}",
                 _redact(f"Telegram commands: {type(e).__name__}; still listening."))
      time.sleep(10)

def listen():
  """Start answering commands, once. Safe to call when Telegram is switched
  off - the thread waits for it to be switched on rather than being restarted."""
  global _listener
  with _lock:
    if _listener is None or not _listener.is_alive():
      _listener = threading.Thread(target=_listen, name="telegram-commands",
                                   daemon=True)
      _listener.start()
  return _listener
