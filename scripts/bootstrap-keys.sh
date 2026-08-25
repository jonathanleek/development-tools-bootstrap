#!/bin/zsh
# Generate an SSH key, load it into the agent/keychain, and register it with GitHub.
# Safe to re-run: an existing key is reused, not overwritten.
set -euo pipefail

KEY="$HOME/.ssh/id_ed25519"
EMAIL="$(git config --global user.email 2>/dev/null || echo "$USER@$(hostname -s)")"
TITLE="$(hostname -s)-$(date +%Y%m%d)"

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"

if [[ -f "$KEY" ]]; then
  print "SSH key already exists at $KEY — reusing it."
else
  print "Generating ed25519 SSH key for $EMAIL ..."
  ssh-keygen -t ed25519 -C "$EMAIL" -f "$KEY" -N ""
fi

# Load into the running agent + macOS keychain
eval "$(ssh-agent -s)" >/dev/null
ssh-add --apple-use-keychain "$KEY" 2>/dev/null || ssh-add "$KEY"

# Register with GitHub if the gh CLI is authenticated
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  print "Adding public key to GitHub as '$TITLE'..."
  gh ssh-key add "$KEY.pub" --title "$TITLE" || print "  (key may already be registered)"
else
  print "gh not authenticated. Run:  gh auth login"
  print "then:  gh ssh-key add $KEY.pub --title \"$TITLE\""
fi

print ""
print "Public key (also add to any other git host you use):"
cat "$KEY.pub"
