#!/usr/bin/env bash
# Stop the headless display started by start-display.sh and undo its changes.
#   bash tools/headless/stop-display.sh
# Close the game first if it is running on that display.
set -uo pipefail

NUM="${UMA_GAME_DISPLAY_NUM:-1}"
STATE="$HOME/.uma-display"
USER_XAUTH="${XAUTHORITY:-$HOME/.Xauthority}"

if [ -f "$STATE/metacity.pid" ]; then
  kill "$(cat "$STATE/metacity.pid")" 2>/dev/null
  rm -f "$STATE/metacity.pid"
fi

if pgrep -f "/usr/lib/xorg/Xorg :$NUM " >/dev/null; then
  echo "Stopping Xorg :$NUM. sudo may ask for your password."
  sudo pkill -f "/usr/lib/xorg/Xorg :$NUM "
  for _ in $(seq 1 10); do
    pgrep -f "/usr/lib/xorg/Xorg :$NUM " >/dev/null || break
    sleep 1
  done
fi

# Only the :NUM entry; the desktop's :0 entry stays.
xauth -q -f "$USER_XAUTH" remove ":$NUM" 2>/dev/null
rm -f "$STATE/xauth"

if pgrep -f "/usr/lib/xorg/Xorg :$NUM " >/dev/null; then
  echo "Xorg :$NUM is still running."
  exit 1
fi
echo "Display :$NUM stopped. Remember to clear Umamusume's Steam launch options if you set them."
