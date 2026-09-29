# development-tools-bootstrap
---

Bootstrap a brand-new **Apple Silicon Mac** (arm64, macOS 15+/26) into a working
development environment. Assumes `zsh`. **Idempotent** — safe to re-run.

## Layout

| Path | Purpose |
|------|---------|
| `setup.sh` | Top-level bootstrap — runs everything below in order |
| `Brewfile` | All CLI tools, apps, fonts, and App Store apps (`brew bundle`) |
| `scripts/macos.sh` | Sensible macOS system defaults (`defaults write`) |
| `scripts/bootstrap-keys.sh` | Generates an SSH key and registers it with GitHub |
| `scripts/restore-secrets.sh` | Restores secrets from Bitwarden (pulls + runs the stored `restore-script` note) |
| `scripts/make-dirs.sh` | Creates the `~/Documents/git/<org>/` directory structure, installs `mi6`, and gives every folder a `.mi6/` layer |
| `scripts/vaults.sh` | Clones the Obsidian/data vaults and registers them with Obsidian |
| `scripts/claude-env.sh` | Reproduces the Claude Code environment (plugins, config) |
| `claude/` | Canonical Claude config: `CLAUDE.md`, `statusline.sh`, `settings.json`, hook patch |

> Shell dotfiles (`.zshrc`, `.gitconfig`, etc.) are **not** managed here yet —
> set those up on the new machine and add them to this repo later.

## What `setup.sh` does

1. Installs the Xcode Command Line Tools (and **waits** for them).
2. Installs Rosetta 2.
3. Installs Homebrew and wires it into the shell (`/opt/homebrew`).
4. Installs everything in [`Brewfile`](./Brewfile) via `brew bundle`.
5. Installs Oh My Zsh + powerlevel10k.
6. Installs the latest stable Python via `pyenv` (global).
7. Installs the latest Terraform via `tfenv`.
8. Creates the `~/Documents/git/<org>/` directory structure and runs `mi6 init` on every folder (installing `mi6` with `go install` first).
9. Starts the `ollama` service.
10. Applies macOS defaults.
11. Restores secrets from Bitwarden (SSH keys, `gh` token, homelab secrets) — interactive.
12. Generates an SSH key and adds it to GitHub (reuses a restored key if present).
13. Clones the Obsidian/data vaults and registers them with Obsidian.
14. Reproduces the Claude Code environment.

### Secret restore (step 11)

Requires `bw` (in the Brewfile) and that you previously stored a `restore-script`
Secure Note in a Bitwarden "Mac Migration" folder. The step prompts for your
Bitwarden login/unlock (never stored), pulls the note, and writes each secret to
its real path with correct permissions. Skippable — Ctrl-C the prompt to defer.
Terraform `.tfstate` files, WireGuard tunnels, and the Anthropic API key are
**not** covered (move those manually).

## To run

```sh
chmod +x setup.sh
./setup.sh
```

Individual pieces can be run on their own, e.g. `./scripts/macos.sh`,
`./scripts/vaults.sh`, `./scripts/claude-env.sh`, or `brew bundle`.

## Claude Code environment (`claude/` + `scripts/claude-env.sh`)

Reproduces the personal Claude setup:
- Adds the `astronomer/agents` and `anthropics/claude-plugins-official` marketplaces.
- Installs the `astronomer-data` plugin.
- Re-applies a **narrowed** `airflow-skill-suggester` hook (the shipped one matches
  the fragment `"af"` and generic words, firing on unrelated prompts).
- Installs `~/.claude/CLAUDE.md`, `~/.claude/statusline.sh`, and merges
  `~/.claude/settings.json` (statusline + read-only permission allowlist).

## Per-domain agent config (`scripts/make-dirs.sh`)

Agent configuration per folder comes from
[mi6](https://github.com/jonathanleek/mi6). `make-dirs.sh` installs `mi6`
(`go install`, so `go` is in the Brewfile) and runs `mi6 init` on
`~/Documents/git` and every folder it creates. Each `.mi6/` layer starts as
the stub set of files `mi6` reads; the instructions, permissions, and env
in each layer are filled by hand. Set `GIT_ROOT` to build the tree
somewhere else.
