#!/bin/sh
# Launcher the Stream Deck app runs (CodePath). Uses the system Python so the
# plugin has no dependencies to install; launch.py is stdlib only.
set -eu
dir="$(cd "$(dirname "$0")" && pwd -P)"
exec /usr/bin/python3 -I "$dir/launch.py" "$@"
