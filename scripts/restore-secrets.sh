#!/bin/zsh
# Restore secrets from Bitwarden: unlock the vault, pull the stored
# `restore-script` note, and run it (it writes each secret to its real path).
# Interactive — prompts for your Bitwarden login + master password, which this
# script never stores. Safe to skip (Ctrl-C the prompt) and run later.
set -uo pipefail

log() { print -P "%F{cyan}==>%f $*"; }

command -v bw >/dev/null 2>&1 || { log "bitwarden-cli not installed — skipping secret restore"; exit 0; }

if [[ ! -t 0 ]]; then
  log "Non-interactive shell — skipping secret restore (run scripts/restore-secrets.sh later)"
  exit 0
fi

manual_hint() {
  log "Skipping secret restore. To do it later:"
  print "    export BW_SESSION=\"\$(bw unlock --raw)\""
  print "    bw get notes restore-script > /tmp/restore.sh && BW_SESSION=\"\$BW_SESSION\" zsh /tmp/restore.sh"
}

# Get a session key: unlock if already logged in, else log in. Both --raw print
# only the session key on success (prompts go to the tty).
if bw login --check >/dev/null 2>&1; then
  SESSION="$(bw unlock --raw)" || { manual_hint; exit 0; }
else
  log "Log into Bitwarden:"
  SESSION="$(bw login --raw)" || { manual_hint; exit 0; }
fi

if [[ -z "${SESSION:-}" ]] || ! bw --session "$SESSION" sync >/dev/null 2>&1; then
  manual_hint; exit 0
fi
export BW_SESSION="$SESSION"

tmp="$(mktemp -t restore-secrets)"
trap 'rm -f "$tmp"' EXIT
if bw get notes restore-script > "$tmp" 2>/dev/null && [[ -s "$tmp" ]]; then
  log "Running restore script from Bitwarden..."
  zsh "$tmp"
else
  log "No 'restore-script' note found in Bitwarden — nothing to restore"
fi
