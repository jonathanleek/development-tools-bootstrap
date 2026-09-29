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
| `scripts/secrets-manifest.sh` | The list of secrets kept in Bitwarden (name, path, mode, note vs. attachment) |
| `scripts/backup-secrets-to-bw.sh` / `scripts/restore-secrets-from-bw.sh` | Back up / restore everything in the manifest |
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
11. Restores secrets from Bitwarden (SSH keys, AWS/Docker config, homelab secrets and Terraform state) — interactive.
12. Generates an SSH key and adds it to GitHub (reuses a restored key if present).
13. Clones the Obsidian/data vaults and registers them with Obsidian.
14. Reproduces the Claude Code environment.

### Secret restore (step 11)

Runs `scripts/restore-secrets-from-bw.sh`, which restores everything listed in
`scripts/secrets-manifest.sh` from the Bitwarden "Mac Migration" folder, with
correct permissions. It prompts for your Bitwarden login/unlock (never stored)
unless `BW_SESSION` is already set, and skips any file that already exists.
Skippable — Ctrl-C the prompt to defer.

Populate the vault first by running `scripts/backup-secrets-to-bw.sh` on the old
machine. Small files are stored as Secure Note bodies; large ones (Terraform
`.tfstate`, etc.) as attachments, which need Bitwarden Premium. Items are matched
by exact name inside the folder.

WireGuard tunnels, the Anthropic API key, and GitHub CLI auth (`gh auth login`)
are **not** covered (set those up manually).

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
