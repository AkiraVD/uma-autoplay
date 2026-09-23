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
import queue
import threading
import urllib.error
import urllib.parse
import urllib.request

import core.state as state
from utils.log import info, warning, debug

API = "https://api.telegram.org/bot{token}/sendMessage"
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

def _redact(text):
  """Take the token out of anything on its way to a log or an API response.

  The sendMessage URL has the token in its path, and an exception is free to
  quote whatever it likes - `OSError: cannot connect to https://.../bot<token>/`
  is a real shape. Rather than audit every error string for whether it might
  carry the URL, scrub the token from all of them.
  """
  token = state.TELEGRAM_TOKEN
  if token and text:
    return str(text).replace(token, "<token>")
  return text

def _warn_once(key, message):
  if key not in _warned:
    _warned.add(key)
    warning(message)

def _post(text):
  """One sendMessage call. Returns None on success, or a reason to log."""
  data = urllib.parse.urlencode({
    "chat_id": state.TELEGRAM_CHAT_ID,
    "text": text[:MAX_LEN],
    "disable_web_page_preview": "true",
  }).encode()
  url = API.format(token=state.TELEGRAM_TOKEN)
  try:
    with urllib.request.urlopen(url, data=data, timeout=TIMEOUT) as res:
      body = json.loads(res.read().decode("utf-8", "replace") or "{}")
    if not body.get("ok"):
      # description carries Telegram's own reason: a wrong chat id reads
      # "chat not found", a wrong token never gets this far.
      return _redact(body.get("description")) or "Telegram refused the message"
    return None
  except urllib.error.HTTPError as e:
    # The URL contains the token, so report the code and not the URL.
    detail = ""
    try:
      detail = json.loads(e.read().decode("utf-8", "replace")).get("description", "")
    except Exception:
      pass
    return _redact(f"HTTP {e.code}{': ' + detail if detail else ''}")
  except Exception as e:
    return _redact(f"{type(e).__name__}: {e}")

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

def send_now(text):
  """Send on this thread and report the outcome, for the config page's test.

  The queue is the right shape for the bot and the wrong shape for a button
  that has to say whether it worked.
  """
  if not configured():
    return "The token and chat id both have to be set."
  return _post(text)
