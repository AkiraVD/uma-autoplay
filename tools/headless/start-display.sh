#!/usr/bin/env bash
# Start a headless X display (:1) on the NVIDIA GPU, for background play.
#
# The game renders there and the bot reads and clicks it through XTest, while
# your own desktop (:0) and mouse stay free. Nothing here changes :0: the Xorg
# config is passed with -config (see xorg-uma-headless.conf), the server adds
# no input devices, and it shares vt7 rather than switching to a VT of its own.
#
# Run it yourself in a terminal. It asks for your sudo password once:
#   bash tools/headless/start-display.sh
# Undo everything with:
#   bash tools/headless/stop-display.sh
set -euo pipefail

NUM="${UMA_GAME_DISPLAY_NUM:-1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CONF="$HERE/xorg-uma-headless.conf"
STATE="$HOME/.uma-display"
AUTH="$STATE/xauth"
USER_XAUTH="${XAUTHORITY:-$HOME/.Xauthority}"

if [ -e "/tmp/.X11-unix/X$NUM" ]; then
  echo "Display :$NUM already exists (/tmp/.X11-unix/X$NUM). Run stop-display.sh first."
  exit 1
fi

# A cookie of its own, so :1 accepts only this user's clients.
mkdir -p "$STATE"
chmod 700 "$STATE"
cookie="$(mcookie)"
rm -f "$AUTH"
xauth -q -f "$AUTH" add ":$NUM" MIT-MAGIC-COOKIE-1 "$cookie"
chmod 600 "$AUTH"
# Clients - the bot, and the game launched from Steam - find the cookie here.
# Only the :NUM entry is added; the desktop's :0 entry is left as it is.
xauth -q -f "$USER_XAUTH" add ":$NUM" MIT-MAGIC-COOKIE-1 "$cookie"

echo "Starting Xorg :$NUM on the NVIDIA GPU. sudo will ask for your password."
sudo -v
# setsid -f gives Xorg a session of its own, with no terminal. Started as a plain
# background job, it was stopped (cleanly, "Server terminated successfully") as
# soon as the terminal that ran this script was closed, taking the game with it.
sudo -n setsid -f /usr/lib/xorg/Xorg ":$NUM" vt7 -sharevts -novtswitch -noreset -nolisten tcp \
  -config "$CONF" -auth "$AUTH" -logfile "/var/log/Xorg.$NUM.log" </dev/null >/dev/null 2>&1

for _ in $(seq 1 30); do
  if DISPLAY=":$NUM" XAUTHORITY="$USER_XAUTH" timeout 3 xprop -root >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! DISPLAY=":$NUM" XAUTHORITY="$USER_XAUTH" timeout 3 xprop -root >/dev/null 2>&1; then
  echo "Xorg :$NUM did not come up. Its log: /var/log/Xorg.$NUM.log"
  echo "Undo with: bash $HERE/stop-display.sh"
  exit 1
fi
echo "Xorg :$NUM is up."

# A window manager, so wmctrl (utils/window.py) can list and raise windows on :NUM.
# No compositing: nothing needs it here, and screenshots stay simple. No session
# manager: SESSION_MANAGER points at the desktop's session, which this must not join.
env -u SESSION_MANAGER DISPLAY=":$NUM" XAUTHORITY="$USER_XAUTH" \
  setsid -f metacity --replace --no-composite --sm-disable </dev/null >"$STATE/metacity.log" 2>&1
sleep 1
pgrep -n -f "metacity --replace --no-composite --sm-disable" > "$STATE/metacity.pid" || true
sleep 2
if kill -0 "$(cat "$STATE/metacity.pid")" 2>/dev/null; then
  echo "Window manager (metacity) running on :$NUM."
else
  echo "metacity exited; see $STATE/metacity.log. The display still works without it."
fi

cat <<EOF

Next: in Steam, set Umamusume's launch options to
    DISPLAY=:$NUM %command%
then start the game from Steam. It opens on :$NUM, not on your desktop.
EOF
