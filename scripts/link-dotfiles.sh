#!/bin/zsh
# Symlink dotfiles from this repo into $HOME.
# Existing real files are moved to ~/.dotfiles-backup/<timestamp>/ first.
set -euo pipefail

REPO_DIR="${0:A:h:h}"          # repo root (scripts/ is one level down)
DOTFILES="$REPO_DIR/dotfiles"
BACKUP="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"

link() {
  local src="$1" dest="$2"
  if [[ -L "$dest" ]]; then
    ln -sfn "$src" "$dest"                        # already a symlink, repoint
  elif [[ -e "$dest" ]]; then
    mkdir -p "$BACKUP"
    mv "$dest" "$BACKUP/"
    ln -sfn "$src" "$dest"
    print "backed up existing $dest -> $BACKUP/"
  else
    ln -sfn "$src" "$dest"
  fi
  print "linked $dest -> $src"
}

link "$DOTFILES/.zshrc"          "$HOME/.zshrc"
link "$DOTFILES/.zprofile"       "$HOME/.zprofile"
link "$DOTFILES/.gitconfig"      "$HOME/.gitconfig"
link "$DOTFILES/.gitignore_global" "$HOME/.gitignore_global"

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
link "$DOTFILES/ssh_config"      "$HOME/.ssh/config"

# Seed the secrets file (never overwrite an existing one)
if [[ ! -f "$HOME/.zsh_secrets" ]]; then
  cp "$DOTFILES/.zsh_secrets.example" "$HOME/.zsh_secrets"
  chmod 600 "$HOME/.zsh_secrets"
  print "created ~/.zsh_secrets (fill in from Bitwarden)"
fi

print "Dotfiles linked."
