# development-tools-bootstrap
---

Bootstrap a brand-new **Apple Silicon Mac** (arm64, macOS 15+/26) into a working
development environment. Assumes `zsh`.

The run is **idempotent** — re-running only adds what's missing and won't disturb
already-installed or configured tools.

## What it does

`setup.sh` handles the machine bootstrap:

1. Installs the Xcode Command Line Tools (and **waits** for them to finish).
2. Installs Rosetta 2 (for the occasional x86-only app).
3. Installs Homebrew and wires it into the shell (`/opt/homebrew` on Apple Silicon).
4. Installs everything in [`Brewfile`](./Brewfile) via `brew bundle`.
5. Installs Oh My Zsh + the powerlevel10k prompt.
6. Installs the latest stable Python via `pyenv` and sets it as global.
7. Installs the latest Terraform via `tfenv`.

All the packages, apps, and fonts live in [`Brewfile`](./Brewfile). Edit that file
to add/remove software, then re-run `brew bundle`.

## To run

```sh
chmod +x setup.sh
./setup.sh
```

## After running

- Open a **new** terminal window so Homebrew, pyenv, and the prompt load.
- Run `p10k configure` to configure the powerlevel10k prompt.
- Mac App Store apps (Fantastical, Magnet) require you to be **signed into the App
  Store** first. Sign in, then re-run `brew bundle`.
