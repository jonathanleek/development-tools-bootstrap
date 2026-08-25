# Brewfile — declarative, idempotent package list for `brew bundle`
# Target: Apple Silicon Mac Studio (arm64), macOS 15+/26
# Re-run any time with: brew bundle
#
# NOTE: A few apps in use have no Homebrew cask and must be installed by hand:
#   Meshmixer, RevoScan5 (Revopoint), Blueprint Studio, TeamSpeak 5,
#   Reolink, Microsoft Defender,
#   UniFi Protect (direct download from ui.com, or use the web console)

# ===========================================================================
# CLI tools (formulae)
# ===========================================================================
brew "git"
brew "gh"                                         # GitHub CLI
brew "jq"                                         # JSON processor (used by the Claude statusline)
brew "mas"                                        # Mac App Store CLI
brew "node"
brew "just"                                       # command runner
brew "pre-commit"                                 # git hook framework
brew "ansible"
brew "astro"                                      # Astronomer / Airflow CLI
brew "awscli"
brew "ollama"                                     # run local LLMs (CLI + server)
brew "pyenv"                                      # Python version manager
brew "tfenv"                                      # Terraform version manager
brew "romkatv/powerlevel10k/powerlevel10k"        # zsh prompt theme
brew "mdbtools"                                   # read MS Access .mdb files
brew "pigz"                                       # parallel gzip
brew "speedtest-cli"
brew "iperf3"

# ===========================================================================
# Fonts
# ===========================================================================
cask "font-hack-nerd-font"                        # glyphs for powerlevel10k

# ===========================================================================
# Dev & terminal apps
# ===========================================================================
cask "iterm2"
cask "sublime-text"
cask "obsidian"
cask "jetbrains-toolbox"                          # installs PyCharm, DataGrip, etc.
cask "docker-desktop"
cask "claude"                                     # Claude desktop app
cask "claude-code"                                # Claude Code CLI
cask "conductor"                                  # Conductor (conductor.build)
cask "lm-studio-bionic"                           # LM Studio Bionic — local model agent

# ===========================================================================
# Browsers & communication
# ===========================================================================
cask "brave-origin"
cask "slack"
cask "discord"
cask "signal"
cask "zoom"

# ===========================================================================
# Utilities
# ===========================================================================
cask "bitwarden"                                  # password manager (also TOTP)
cask "ente-auth"                                  # 2FA authenticator
cask "stats"                                      # free system monitor
cask "appcleaner"

# ===========================================================================
# Microsoft
# ===========================================================================
cask "microsoft-office"                           # Word, Excel, PowerPoint, Outlook, OneNote

# ===========================================================================
# Media
# ===========================================================================
cask "vlc"
cask "plex"
cask "makemkv"

# ===========================================================================
# 3D printing / making
# ===========================================================================
cask "bambu-studio"                               # Bambu Lab slicer
cask "openscad@snapshot"                          # parametric CAD
cask "autodesk-fusion360"                         # CAD/CAM
cask "lightburn"                                  # laser control
cask "raspberry-pi-imager"
cask "balenaetcher"

# ===========================================================================
# Personal / misc
# ===========================================================================
cask "hovrly"                                     # menu-bar world clock
cask "amazon-workspaces"                          # remote desktop
cask "tableau-public"                             # data visualization

# ===========================================================================
# Mac App Store — essentials (requires being signed into the App Store)
# Find IDs with: mas search "<name>"
# ===========================================================================
mas "Fantastical",  id: 975937182
mas "Magnet",       id: 441258766
mas "Amphetamine",  id: 937984704
mas "Okta Verify",  id: 490179405

# ---- Mac App Store — optional / personal ----
mas "Kindle",               id: 302584613
mas "Copilot",              id: 1447330651
mas "iMovie",               id: 408981434
mas "Brother iPrint&Scan",  id: 1193539993
mas "Simple Mouse Locator", id: 946676425
