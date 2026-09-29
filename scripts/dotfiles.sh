#!/bin/zsh
# Symlink the dotfiles in ./dotfiles into $HOME. Re-runnable.
#
# Links point into this checkout, so edits to ~/.zshrc etc. are edits to the
# repo — commit them here. Links are only made from the permanent clone
# (CANONICAL below), never from a downloaded copy that may be deleted.
# Anything already at a target that is not our link is moved aside to
# <target>.bak-<timestamp> first, never deleted.
set -euo pipefail

REPO="${0:A:h:h}"
CANONICAL="$HOME/Documents/git/personal/development-tools-bootstrap"

if [[ "$REPO" != "$CANONICAL" ]]; then
  print "dotfiles.sh: run this from the permanent clone, $CANONICAL" >&2
  print "  (this copy is at $REPO; links into it would break if it moves)" >&2
  exit 1
fi

# "file in dotfiles/ | target relative to \$HOME"
LINKS=(
  "zshrc|.zshrc"
  "zprofile|.zprofile"
  "p10k.zsh|.p10k.zsh"
  "gitconfig|.gitconfig"
  "config/git/ignore|.config/git/ignore"
  "config/git/astronomer.gitconfig|.config/git/astronomer.gitconfig"
  "config/ghostty/config|.config/ghostty/config"
  # mi6 layer instructions (AGENTS.md only; layer JSON may hold secrets)
  "mi6/git/AGENTS.md|Documents/git/.mi6/AGENTS.md"
)

stamp="$(date +%Y%m%d%H%M%S)"
for entry in $LINKS; do
  src="$REPO/dotfiles/${entry%%|*}"
  dest="$HOME/${entry#*|}"
  [[ -e "$src" ]] || { print "missing in repo, skip: ${src#$REPO/}"; continue; }
  if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
    print "ok:     ~/${dest#$HOME/}"
    continue
  fi
  mkdir -p "${dest:h}"
  if [[ -e "$dest" || -L "$dest" ]]; then
    mv "$dest" "$dest.bak-$stamp"
    print "moved:  ~/${dest#$HOME/} -> ~/${dest#$HOME/}.bak-$stamp"
  fi
  ln -s "$src" "$dest"
  print "linked: ~/${dest#$HOME/} -> ${src#$REPO/}"
done
