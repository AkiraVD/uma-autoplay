# logging tools
import logging
import os
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(levelname)s] %(message)s"
)

info = logging.info
warning = logging.warning
error = logging.error
debug = logging.debug

# Overridable so a test run or a probe does not write into the log of a career
# that is running right now - the supervisor watches that file for stalls, and
# reading it afterwards is how a run gets diagnosed.
log_dir = os.environ.get("UMA_LOG_DIR") or os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)

handler = RotatingFileHandler(
    os.path.join(log_dir, "log.txt"),
    maxBytes=1_000_000,
    backupCount=10,
    encoding="utf-8"
)

# The file gets timestamps and a level; the console keeps the bare format set
# above. Without them a run cannot be timed after the fact - how long a race
# took, how long the bot sat on one screen, whether two lines were the same
# turn - which is most of what reading an old log is for.
#
# Anything parsing this file must allow for the prefix: tools/logserver.py
# strips it before matching.
handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S"))

logging.getLogger().addHandler(handler)

# PIL logs every PNG chunk it decodes at DEBUG, which floods log.txt now that
# the gains reader opens images per turn. Same for easyocr's torch plumbing.
for _noisy in ("PIL", "PIL.PngImagePlugin", "matplotlib", "urllib3"):
  logging.getLogger(_noisy).setLevel(logging.INFO)
