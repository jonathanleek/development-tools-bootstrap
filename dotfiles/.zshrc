# ~/.zshrc — managed in development-tools-bootstrap/dotfiles (symlinked by setup.sh)

# ---- Powerlevel10k instant prompt (keep near the top) ----
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# ---- Oh My Zsh ----
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME=""                       # prompt is provided by powerlevel10k below
plugins=(git gh docker aws pyenv)
[[ -r "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"

# ---- Powerlevel10k prompt ----
if [[ -r "$(brew --prefix 2>/dev/null)/opt/powerlevel10k/powerlevel10k.zsh-theme" ]]; then
  source "$(brew --prefix)/opt/powerlevel10k/powerlevel10k.zsh-theme"
fi
[[ -r "$HOME/.p10k.zsh" ]] && source "$HOME/.p10k.zsh"   # run `p10k configure` to create

# ---- pyenv (Python version manager) ----
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
command -v pyenv >/dev/null && eval "$(pyenv init -)"

# ---- Google Cloud SDK ----
[[ -f "$HOME/google-cloud-sdk/path.zsh.inc" ]]       && . "$HOME/google-cloud-sdk/path.zsh.inc"
[[ -f "$HOME/google-cloud-sdk/completion.zsh.inc" ]] && . "$HOME/google-cloud-sdk/completion.zsh.inc"

# ---- LM Studio CLI ----
[[ -d "$HOME/.lmstudio/bin" ]] && export PATH="$PATH:$HOME/.lmstudio/bin"

# ---- uv / local bin ----
[[ -f "$HOME/.local/bin/env" ]] && . "$HOME/.local/bin/env"

# ---- Secrets (gitignored, never committed) ----
[[ -f "$HOME/.zsh_secrets" ]] && source "$HOME/.zsh_secrets"
