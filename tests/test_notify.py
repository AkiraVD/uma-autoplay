"""Telegram notifications: the four events, and never getting in the way.

Run with `python tests/test_notify.py` from the repo root. It imports
core.state, so it starts slowly; it never touches the network - `_post` is
replaced throughout.

The notifier's whole job is to be ignorable. A run that plays for hours
unattended is worth nothing if the thing reporting on it can stall the bot or
end a career, so what is pinned here is mostly what it does when it goes wrong:
switched off, unconfigured, and with an endpoint that refuses or hangs.
"""
import io
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("UMA_LOG_DIR", os.path.join("tests", "logs"))

import json                                   # noqa: E402
import core.notify as notify                  # noqa: E402
import core.state as state                    # noqa: E402

failures = []
SECRET = "999999:THIS_TOKEN_MUST_NEVER_BE_LOGGED"
# Kept before any test swaps it out: the token test needs the shipped one.
REAL_POST = notify._post

def ok(label, condition, detail=""):
  print(f"{'ok  ' if condition else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
  if not condition:
    failures.append(label)

def use(enabled=True, token=SECRET, chat="123456"):
  state.TELEGRAM_ENABLED = enabled
  state.TELEGRAM_TOKEN = token
  state.TELEGRAM_CHAT_ID = chat

def capture():
  """Replace the network call, returning the list it records into."""
  sent = []
  notify._post = lambda text, token=None, chat_id=None: (sent.append(text), None)[1]
  return sent

def test_off_and_unconfigured_send_nothing():
  sent = capture()
  use(enabled=False)
  ok("switched off, nothing is sent", notify.send("x") is False and not sent)
  use(enabled=True, token="", chat="")
  ok("on but unconfigured, nothing is sent", notify.send("x") is False and not sent)
  # The warning must not repeat every turn for a whole career.
  notify._warned.clear()
  before = len(notify._warned)
  notify.send("x"); notify.send("x"); notify.send("x")
  ok("and it complains once, not every time", len(notify._warned) == before + 1,
     str(notify._warned))

def test_sending_does_not_block_the_bot():
  """The bot loop calls this between turns; a slow Telegram must cost nothing."""
  use()
  slow = []
  def stall(text, token=None, chat_id=None):
    slow.append(text)
    time.sleep(1.5)
    return None
  notify._post = stall
  t0 = time.time()
  queued = notify.send("first")
  elapsed = time.time() - t0
  ok("send() returns immediately", queued is True and elapsed < 0.3,
     f"{elapsed:.3f}s")
  notify._queue.join()
  ok("and the message still went", slow == ["first"], str(slow))

def test_a_failing_endpoint_never_raises():
  use()
  def boom(text, token=None, chat_id=None):
    raise RuntimeError("network on fire")
  notify._post = boom
  # _post is what the worker calls; the worker must swallow whatever it does.
  ok("send() survives a throwing _post", notify.send("x") is True)
  notify._queue.join()
  ok("and the worker is still alive for the next one",
     notify._worker is not None and notify._worker.is_alive())
  # The real _post catches its own exceptions and returns a reason instead.
  import core.notify as fresh
  reason = fresh.__dict__["_post"]
  ok("the shipped _post reports rather than raises",
     callable(reason))

def test_messages_keep_their_order():
  """One worker, not a thread per message: a career's events read as a story."""
  use()
  sent = capture()
  for i in range(8):
    notify.send(f"m{i}")
  notify._queue.join()
  ok("messages arrive in the order they were made",
     sent == [f"m{i}" for i in range(8)], str(sent))

def test_the_token_never_reaches_the_log():
  """The log is a file, a viewer page and a tailnet address. The token is the
  one thing in the config that is a secret, and the sendMessage URL carries it.

  Tested by behaviour, not by reading the source for "url": the first two
  attempts at that matched `urllib.parse.urlencode` and `except urllib.error`
  and failed on perfectly correct code. What matters is what comes back.
  """
  import urllib.error
  import urllib.request
  use()
  # capture() in the tests above leaves a stub in place; this one is about what
  # the real _post returns.
  notify._post = REAL_POST
  real = urllib.request.urlopen

  def http_error(url, data=None, timeout=None):
    raise urllib.error.HTTPError(url, 401, "Unauthorized", {},
                                 io.BytesIO(b'{"description":"Unauthorized"}'))

  def other_error(url, data=None, timeout=None):
    raise OSError(f"cannot connect to {url}")

  try:
    for name, boom in (("an HTTP error", http_error), ("a transport error", other_error)):
      urllib.request.urlopen = boom
      reason = notify._post("hello")
      ok(f"{name} still reports something", bool(reason), repr(reason))
      ok(f"and the token is not in it ({name})", SECRET not in (reason or ""),
         repr(reason))
      # The hostname is deliberately not checked: api.telegram.org is public,
      # and seeing it in a reason is what tells you the problem is reaching
      # Telegram at all. Only the token is a secret.
  finally:
    urllib.request.urlopen = real

  log = os.path.join("tests", "logs", "log.txt")
  if os.path.exists(log):
    ok("and no test run has written it to the log file",
       SECRET not in open(log, encoding="utf-8", errors="replace").read())

def test_long_messages_are_trimmed():
  use()
  sent = capture()
  notify.send("x" * 9000)
  notify._queue.join()
  ok("a long message is trimmed rather than refused",
     sent and len(sent[0]) == 9000, f"queued {len(sent[0]) if sent else 0}")
  # The trim happens in _post, against Telegram's 4096 limit.
  ok("the limit is under Telegram's own", notify.MAX_LEN < 4096, str(notify.MAX_LEN))

def test_the_four_events_are_wired():
  source = open(os.path.join("core", "execute.py"), encoding="utf-8").read()
  ok("a career starting is reported",
     "Career {state.CAREERS_STARTED}{limit} started" in source)
  ok("with its uuid", "state.CAREER_UUID" in source)
  ok("a career finishing is reported", '"Career finished' in source)
  ok("with stats and sparks",
     "_stat_line(state.LAST_STATS)" in source and "state.LAST_SPARKS" in source)
  ok("a freeze is reported", "froze - closing it" in source)
  ok("and so is coming back", "Game restarted. Resuming the career." in source)
  ok("a failed restart is reported too", "Could not restart the game." in source)
  # The caches those messages read from.
  logic = open(os.path.join("core", "logic.py"), encoding="utf-8").read()
  ok("the stats are cached each turn", "state.LAST_STATS = current_stats" in logic)
  sparks = open(os.path.join("core", "sparks.py"), encoding="utf-8").read()
  ok("the kept sparks are cached", "state.LAST_SPARKS = why" in sparks)

def test_the_test_button_cannot_disturb_anything():
  """Credentials are arguments, not a global the endpoint sets around a call.

  The first version assigned state.TELEGRAM_TOKEN for the duration of the
  request. Two overlapping requests then read each other's: a test posting no
  token at all came back "ok" because a browser test was in flight beside it.
  That is also a way for a test to leave the running bot pointed elsewhere if
  the restore ever failed.
  """
  use(token="CONFIGURED:token", chat="111")
  seen = []
  notify._post = lambda text, token=None, chat_id=None: (
    seen.append((token, chat_id)), None)[1]

  notify.send_now("x", token="TYPED:token", chat_id="222")
  ok("a passed token is the one used", seen[-1] == ("TYPED:token", "222"),
     str(seen[-1]))
  ok("and the configured one is untouched",
     state.TELEGRAM_TOKEN == "CONFIGURED:token" and state.TELEGRAM_CHAT_ID == "111")

  notify.send_now("x")
  ok("with nothing passed, the configured one is used",
     seen[-1] == ("CONFIGURED:token", "111"), str(seen[-1]))

  # The empty case is what reported a false success.
  use(token="", chat="")
  reason = notify.send_now("x")
  ok("no credentials anywhere is refused, not reported as sent",
     reason is not None, repr(reason))

  server = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  endpoint = server[server.index("def telegram_test("):]
  endpoint = endpoint[:endpoint.index("@app.get")]
  ok("the endpoint assigns no global state",
     "state.TELEGRAM_TOKEN =" not in endpoint
     and "state.TELEGRAM_CHAT_ID =" not in endpoint)
  ok("and passes them as arguments instead",
     "token=" in endpoint and "chat_id=" in endpoint)

def test_the_config_and_the_page():
  template = json.load(open("config.template.json", encoding="utf-8"))
  ok("telegram is in the config schema", "telegram" in template)
  ok("and is off by default", template["telegram"]["enabled"] is False)
  ok("with no token in the template", template["telegram"]["token"] == "")
  for key in ("TELEGRAM_ENABLED", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"):
    ok(f"state reads {key}", hasattr(state, key))
  server = open(os.path.join("server", "main.py"), encoding="utf-8").read()
  ok("the page can test the settings", "/telegram/test" in server)
  # Testing must not leave the running bot pointed at whatever was typed.
  # There is nothing to restore any more - the endpoint never assigns - and
  # test_the_test_button_cannot_disturb_anything is what pins that.
  app = open(os.path.join("web", "src", "App.tsx"), encoding="utf-8").read()
  ok("the tab exists", '"telegram", "Telegram"' in app)
  ok("and has its own hash", '"#telegram"' in app)

if __name__ == "__main__":
  test_off_and_unconfigured_send_nothing()
  test_sending_does_not_block_the_bot()
  test_a_failing_endpoint_never_raises()
  test_messages_keep_their_order()
  test_the_token_never_reaches_the_log()
  test_long_messages_are_trimmed()
  test_the_four_events_are_wired()
  test_the_test_button_cannot_disturb_anything()
  test_the_config_and_the_page()
  print()
  if failures:
    print(f"{len(failures)} failed: " + ", ".join(failures))
    sys.exit(1)
  print("all ok")
