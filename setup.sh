#!/bin/zsh
# Development environment bootstrap
# Target: brand-new Apple Silicon Mac (arm64), macOS 15+/26
# Jonathan Leek
#
# Idempotent: safe to re-run. Package list lives in ./Brewfile.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"

log() { print -P "%F{cyan}==>%f $*"; }

# ---------------------------------------------------------------------------
# 1. Xcode Command Line Tools (blocking — homebrew needs these)
# ---------------------------------------------------------------------------
if ! xcode-select -p >/dev/null 2>&1; then
  log "Installing Xcode Command Line Tools (a GUI dialog will appear)..."
  xcode-select --install || true
  log "Waiting for Xcode Command Line Tools to finish installing..."
  until xcode-select -p >/dev/null 2>&1; do
    sleep 15
  done
else
  log "Xcode Command Line Tools already installed"
fi

# ---------------------------------------------------------------------------
# 2. Rosetta 2 (some casks are still x86-only)
# ---------------------------------------------------------------------------
if [[ "$(uname -m)" == "arm64" ]] && ! /usr/bin/pgrep -q oahd; then
  log "Installing Rosetta 2..."
  softwareupdate --install-rosetta --agree-to-license || true
fi

# ---------------------------------------------------------------------------
# 3. Homebrew
# ---------------------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  log "Installing Homebrew..."
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Load brew into the current shell (Apple Silicon lives in /opt/homebrew)
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# Persist brew for future login shells
if ! grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null; then
  print 'eval "$('"$(command -v brew)"' shellenv)"' >> "$HOME/.zprofile"
fi

log "Updating Homebrew..."
brew update
brew upgrade

# ---------------------------------------------------------------------------
# 4. Install everything from the Brewfile (idempotent)
# ---------------------------------------------------------------------------
log "Installing packages from Brewfile..."
brew bundle --file "$SCRIPT_DIR/Brewfile" || \
  log "Some Brewfile items failed (App Store items need you signed into the App Store first) — continuing"

brew cleanup

# ---------------------------------------------------------------------------
# 5. Oh My Zsh (keep existing .zshrc, don't relaunch a subshell)
# ---------------------------------------------------------------------------
if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
  log "Installing Oh My Zsh..."
  RUNZSH=no KEEP_ZSHRC=yes sh -c \
    "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
fi

# powerlevel10k prompt
if ! grep -q 'powerlevel10k.zsh-theme' "$HOME/.zshrc" 2>/dev/null; then
  log "Enabling powerlevel10k in .zshrc..."
  {
    print ''
    print '# powerlevel10k'
    print "source $(brew --prefix)/opt/powerlevel10k/powerlevel10k.zsh-theme"
  } >> "$HOME/.zshrc"
fi

# ---------------------------------------------------------------------------
# 6. Python via pyenv (latest stable release)
# ---------------------------------------------------------------------------
if ! grep -q 'pyenv init' "$HOME/.zshrc" 2>/dev/null; then
  log "Adding pyenv init to .zshrc..."
  cat >> "$HOME/.zshrc" <<'EOF'

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
EOF
fi

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

PY_LATEST="$(pyenv install --list | grep -E '^[[:space:]]*3\.[0-9]+\.[0-9]+$' | tail -1 | tr -d '[:space:]')"
if [[ -n "$PY_LATEST" ]]; then
  log "Installing Python $PY_LATEST via pyenv..."
  pyenv install -s "$PY_LATEST"
  pyenv global "$PY_LATEST"
  pyenv rehash
  python -m pip install --upgrade pip
fi

# ---------------------------------------------------------------------------
# 7. Terraform via tfenv (latest stable)
# ---------------------------------------------------------------------------
log "Installing latest Terraform via tfenv..."
tfenv install latest
tfenv use latest

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Setup complete."
print -P "%F{yellow}Next steps:%f"
print "  1. Open a NEW terminal window (so brew/pyenv/prompt load)."
print "  2. Run: p10k configure   (to configure the powerlevel10k prompt)"
print "  3. Sign into the App Store, then re-run: brew bundle   (for Fantastical / Magnet)"
