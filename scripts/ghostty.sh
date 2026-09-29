#!/bin/zsh
# Install the Ghostty config from ghostty/config into ~/.config/ghostty/config.
# Re-runnable. An existing config that differs is moved aside first, never lost.
set -euo pipefail

REPO="${0:A:h:h}"
SRC="$REPO/ghostty/config"
DEST="$HOME/.config/ghostty/config"

mkdir -p "${DEST:h}"
if [[ -f "$DEST" ]] && ! cmp -s "$SRC" "$DEST"; then
  bak="$DEST.bak-$(date +%Y%m%d%H%M%S)"
  mv "$DEST" "$bak"
  print "Existing Ghostty config moved to $bak"
fi
cp "$SRC" "$DEST"
print "Ghostty config installed at $DEST"
print "For the cmd+enter quick terminal, allow Ghostty under System Settings ->"
print "Privacy & Security -> Accessibility (macOS asks on first use)."
