# development-tools-bootstrap
---

Bootstrap a brand-new **Apple Silicon Mac** (arm64, macOS 15+/26) into a working
development environment. Assumes `zsh`. **Idempotent** — safe to re-run.

## Layout

| Path | Purpose |
|------|---------|
| `setup.sh` | Top-level bootstrap — runs everything below in order |
| `Brewfile` | All CLI tools, apps, fonts, and App Store apps (`brew bundle`) |
| `dotfiles/` | `.zshrc`, `.zprofile`, `.gitconfig`, `.gitignore_global`, `ssh_config` |
| `scripts/link-dotfiles.sh` | Symlinks `dotfiles/` into `$HOME` (backs up existing files) |
| `scripts/macos.sh` | Sensible macOS system defaults (`defaults write`) |
| `scripts/bootstrap-keys.sh` | Generates an SSH key and registers it with GitHub |

## What `setup.sh` does

1. Installs the Xcode Command Line Tools (and **waits** for them).
2. Installs Rosetta 2.
3. Installs Homebrew and wires it into the shell (`/opt/homebrew`).
4. Installs everything in [`Brewfile`](./Brewfile) via `brew bundle`.
5. Symlinks the dotfiles into `$HOME`.
6. Installs Oh My Zsh + powerlevel10k (prompt sourced from the dotfiles).
7. Installs the latest stable Python via `pyenv` (global).
8. Installs the latest Terraform via `tfenv`.
9. Starts the `ollama` service.
10. Applies macOS defaults.
11. Generates an SSH key and adds it to GitHub (via `gh`).

## To run

```sh
chmod +x setup.sh
./setup.sh
```

Individual pieces can be run on their own, e.g. `./scripts/macos.sh` or
`brew bundle`.

## Secrets

Real secrets (API keys, tokens) are **never** committed. `link-dotfiles.sh`
seeds `~/.zsh_secrets` (gitignored) from `dotfiles/.zsh_secrets.example`; fill it
in from Bitwarden. `~/.zshrc` sources it automatically.

## After running

- Open a **new** terminal so Homebrew, pyenv, and the prompt load.
- Run `p10k configure` to create `~/.p10k.zsh`.
- Fill in `~/.zsh_secrets` from Bitwarden.
- Sign into the App Store, then re-run `brew bundle` (Fantastical, Magnet, etc.).
- **Manual installs** (no Homebrew cask): Meshmixer, RevoScan5, Blueprint Studio,
  TeamSpeak 5, Reolink, Microsoft Defender, UniFi Protect.
