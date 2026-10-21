#!/bin/zsh
# Set up the Stream Deck +: link the plugins into the Elgato app, generate the
# profile from disk, make it the device default. Re-runnable.
#
# What this can't do (see README "Stream Deck"): install the Zoom plugin
# (Marketplace needs your Elgato login), save camera presets, or assign the
# Link Controller shortcuts.
set -euo pipefail

REPO="${0:A:h:h}"
SD_SUPPORT="$HOME/Library/Application Support/com.elgato.StreamDeck"
PLUGINS="$SD_SUPPORT/Plugins"
KIOSK="${KIOSK_REPO:-$HOME/Documents/git/westbound-workshop/inventory-kiosk}"
LINK_CONTROLLER="/Applications/Insta360 Link Controller.app"

if [[ ! -d "/Applications/Elgato Stream Deck.app" ]]; then
  print "streamdeck.sh: Elgato Stream Deck app not installed (brew bundle first); skipping" >&2
  exit 0
fi
command -v uv >/dev/null || { print "streamdeck.sh: uv not on PATH (brew install uv)" >&2; exit 1; }
mkdir -p "$PLUGINS"

link_plugin() {  # <source .sdPlugin dir>
  local src="$1" dest="$PLUGINS/${1:t}"
  if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
    print "ok:     plugin ${1:t}"
  elif [[ -e "$dest" || -L "$dest" ]]; then
    mv "$dest" "$dest.bak-$(date +%Y%m%d%H%M%S)"
    ln -s "$src" "$dest"; print "linked: plugin ${1:t} (old copy moved aside)"
  else
    ln -s "$src" "$dest"; print "linked: plugin ${1:t}"
  fi
}

# 1. Launch plugin (this repo; stdlib Python, nothing to install)
link_plugin "$REPO/streamdeck/plugins/com.jonathanleek.launch.sdPlugin"

# 2. Gridfinity plugin (inventory-kiosk repo; needs its CAD virtualenv)
if [[ -d "$KIOSK/streamdeck-plugin/com.westboundworkshop.gridfinity.sdPlugin" ]]; then
  if [[ ! -x "$KIOSK/.venv/bin/python" ]]; then
    print "Gridfinity: creating the kiosk virtualenv (uv sync --extra cad --extra deck)..."
    (cd "$KIOSK" && uv sync --extra cad --extra deck)
  fi
  link_plugin "$KIOSK/streamdeck-plugin/com.westboundworkshop.gridfinity.sdPlugin"
else
  print "Gridfinity: $KIOSK not cloned; skipping that plugin (re-run after cloning)"
fi

# 3. Whiteboard Snap.app: takes the deck's whiteboard stills (needs swiftc,
#    from the Xcode command line tools)
if command -v swiftc >/dev/null; then
  "$REPO/streamdeck/snap-app/build.sh"
else
  print "Whiteboard Snap: swiftc not found (xcode-select --install); the Snap key won't work" >&2
fi

# 4. Link Controller runs at login so its global camera shortcuts work
if [[ -d "$LINK_CONTROLLER" ]]; then
  if ! osascript -e 'tell application "System Events" to get the name of every login item' | grep -q "Insta360 Link Controller"; then
    osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$LINK_CONTROLLER\", hidden:true}" >/dev/null
    print "added:  Insta360 Link Controller to login items"
  else
    print "ok:     Insta360 Link Controller login item"
  fi
fi

# 5. Generate and install the profile. Needs the device to have been seen by
#    the app once (its UUID comes from the app's preferences).
if defaults read com.elgato.StreamDeck Devices 2>/dev/null | grep -q 'DeviceName = "Stream Deck +"'; then
  uv run --quiet "$REPO/streamdeck/generate.py" --install --restart --set-default
else
  print "Stream Deck +: not seen by the app yet. Plug it in, open the Stream Deck app once, then re-run scripts/streamdeck.sh"
fi
