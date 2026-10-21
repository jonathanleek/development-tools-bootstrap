#!/bin/zsh
# Build "Whiteboard Snap.app" (see main.swift) into ~/.local/share/streamdeck/.
# Rebuilt only when main.swift or Info.plist change: macOS keys the camera
# permission to the app's signature, so an unneeded rebuild would ask again.
set -euo pipefail

SRC="${0:A:h}"
DEST="$HOME/.local/share/streamdeck/Whiteboard Snap.app"
STAMP="$DEST/Contents/Resources/source.sha256"
sum="$(cat "$SRC/main.swift" "$SRC/Info.plist" | shasum -a 256 | cut -d' ' -f1)"

if [[ -f "$STAMP" && "$(<"$STAMP")" == "$sum" ]]; then
  print "ok:     Whiteboard Snap.app"
  exit 0
fi
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
app="$tmp/Whiteboard Snap.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
swiftc -O -o "$app/Contents/MacOS/whiteboard-snap" "$SRC/main.swift"
cp "$SRC/Info.plist" "$app/Contents/Info.plist"
print -r -- "$sum" > "$app/Contents/Resources/source.sha256"
codesign --force --sign - --identifier com.jonathanleek.whiteboard-snap "$app"
mkdir -p "${DEST:h}"
[[ -e "$DEST" ]] && mv "$DEST" "$tmp/old.app"
mv "$app" "$DEST"
print "built:  Whiteboard Snap.app (macOS will ask for camera access on first use)"
