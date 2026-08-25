# ~/.zprofile — managed in development-tools-bootstrap/dotfiles (symlinked by setup.sh)

# Homebrew (Apple Silicon)
eval "$(/opt/homebrew/bin/brew shellenv)"

# JetBrains Toolbox shell scripts (pycharm, datagrip, etc.)
[[ -d "$HOME/Library/Application Support/JetBrains/Toolbox/scripts" ]] && \
  export PATH="$PATH:$HOME/Library/Application Support/JetBrains/Toolbox/scripts"
