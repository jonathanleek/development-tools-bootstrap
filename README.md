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
| `scripts/streamdeck.sh` + `streamdeck/` | Stream Deck +: links the plugins, generates the profile from disk (see below) |
| `dotfiles/` + `scripts/dotfiles.sh` | Shell dotfiles, symlinked into `$HOME` (see below) |
| `claude-config/` | Canonical Claude config: `CLAUDE.md`, `statusline.sh`, `settings.json`, hook patch |

## Dotfiles

`dotfiles/` holds the shell config (`.zshrc`, `.zprofile`, `.p10k.zsh`) and git
config (`.gitconfig`, global ignore, the work identity for `astronomer/`), plus the
mi6 layer files under `~/Documents/git` that hold no secrets (the folder-layout
`AGENTS.md`; the Fusion MCP server for `personal`, `westbound-workshop` and
`arch-reactor`), and the Ghostty
config (quick terminal on cmd+enter). `scripts/dotfiles.sh`
symlinks them into `$HOME`, so editing `~/.zshrc` edits the repo — commit the
change here. Links are only made from the permanent clone at
`~/Documents/git/personal/development-tools-bootstrap` (setup.sh clones it there
if you ran it from a download); anything already in the way is moved to
`<file>.bak-<timestamp>`, never deleted.

## What `setup.sh` does

1. Installs the Xcode Command Line Tools (and **waits** for them).
2. Installs Rosetta 2.
3. Installs Homebrew and wires it into the shell (`/opt/homebrew`).
4. Installs everything in [`Brewfile`](./Brewfile) via `brew bundle`.
5. Installs Oh My Zsh and links the dotfiles (shell config, powerlevel10k prompt).
6. Installs the latest stable Python via `pyenv` (global).
7. Installs the latest Terraform via `tfenv`.
8. Creates the `~/Documents/git/<org>/` directory structure and runs `mi6 init` on every folder (installing `mi6` with `go install` first).
9. Starts the `ollama` service.
10. Applies macOS defaults.
11. Restores secrets from Bitwarden (SSH keys, AWS/Docker config, homelab secrets and Terraform state) — interactive.
12. Generates an SSH key and adds it to GitHub (reuses a restored key if present).
13. Clones the Obsidian/data vaults and registers them with Obsidian.
14. Reproduces the Claude Code environment.
15. Sets up the Stream Deck + (plugins, generated profile, Link Controller login item).

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

The backup only adds items that aren't in the vault yet. Run it with `--update`
after a `terraform apply` or after rotating a key: it compares each existing
item with the local file and replaces the ones that changed.

WireGuard tunnels, the Anthropic API key, and GitHub CLI auth (`gh auth login`)
are **not** covered (set those up manually).

## To run

```sh
chmod +x setup.sh
./setup.sh
```

Individual pieces can be run on their own, e.g. `./scripts/macos.sh`,
`./scripts/vaults.sh`, `./scripts/claude-env.sh`, or `brew bundle`.

## Claude Code environment (`claude-config/` + `scripts/claude-env.sh`)

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

## Stream Deck +

The deck's profile is **generated from what's on disk**, not hand-built.
`streamdeck/generate.py` (run with `uv`) writes it straight into the Stream
Deck app's profile folder; `scripts/streamdeck.sh` links the plugins and runs
it. Re-run either after adding a customer folder, a repo, or a client note,
or press **Rescan** on the deck (it restarts the app, ~5 s).

- **Home**: Astronomer, Meeting, Gridfinity, Rescan. No dials.
- **Astronomer** walks `~/Documents/git/astronomer` one page per folder down
  to each git repo: Ghostty here, PyCharm, Finder. **Customers** is the union
  of `customers/` folders and the Astronomer vault's `! Clients/Active` notes;
  each customer page has Notes (Obsidian), Finder, Slack Internal / External,
  and its repos. Slack channels come from the client's `Client Info` note —
  rows `Slack (internal)` / `Slack (external)` holding `#channel-name` (looked
  up in `streamdeck/slack-channels.json`; add a line for a new name) or a
  channel link.
- **Meeting**: Zoom plugin keys (mute, video, share the BenQ, leave; more on
  a second page) plus Face / Whiteboard / Desk and zoom / pan / tilt dials,
  which send Insta360 Link Controller's global shortcuts. Emitted twice: as a
  folder off Home and as a profile tied to Zoom's bundle id, so the deck
  switches to it while Zoom is frontmost. Zoom key settings edited in the
  app (which monitor to share) are preserved across rescans.
- **Gridfinity**: dials set X / Y / height, keys toggle label shelf and
  scoop and generate a bin or baseplate (STL + STEP) onto the Workshop share.
  The plugin lives in `westbound-workshop/inventory-kiosk/streamdeck-plugin`
  and reuses the kiosk's CAD engine; `scripts/streamdeck.sh` creates its
  virtualenv (`uv sync --extra cad --extra deck`) and links it in.

`streamdeck/plugins/com.jonathanleek.launch.sdPlugin` is a tiny plugin that
runs the `argv` stored in a key (the built-in Open action can't pass a
working directory to Ghostty or PyCharm). Settings live in
`streamdeck/config.json`; the Astronomer logo and other icons in
`streamdeck/icons/`. Previous profiles are moved to
`~/.local/state/streamdeck-generator/backups/`, never deleted.

**Manual, once per Mac** (can't be scripted):
1. System Settings → Privacy & Security → **Device Control and Data Access** (called Accessibility before macOS 27): add `Elgato Stream Deck` with **+** and switch it on. Without it every hotkey key shows a yellow caution and sends nothing; the app never asks for it.
2. Stream Deck app → Marketplace → install **Zoom** by Elgato (needs an Elgato login).
3. In the Stream Deck app, click the Share Screen key on the Meeting page and on the "(Zoom)" profile and pick the monitor to share.
4. Insta360 Link Controller → ⋯ → Settings → **Hotkeys**: save your framings as scene presets (1 = Meeting, 2 = Whiteboard; the numbering does not follow the thumbnail order), then set these shortcuts and tick **Global Shortcuts** on each row, all with ctrl+option+cmd: Preset 1 `1`, Preset 2 `2`, DeskView `3`, Center gimbal `0`, Enlarge `=`, Zoom out `-`, Gimbal up/down/left/right `I`/`K`/`J`/`L`. Letters, not arrows: ctrl+option+cmd+arrows are Magnet's move-to-display shortcuts. These match `camera` in `streamdeck/config.json`.
