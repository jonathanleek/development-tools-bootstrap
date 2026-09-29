#!/bin/zsh
# Restore secrets from the Bitwarden "Mac Migration" folder to their real paths,
# with correct permissions. Run on the NEW machine. No secret value is printed.
# The item -> path -> mode list lives in scripts/secrets-manifest.sh; populate
# the vault with scripts/backup-secrets-to-bw.sh.
#
# Uses $BW_SESSION if set; otherwise prompts to log in / unlock (the master
# password is never stored). setup.sh runs this as its secret-restore step.
#
# Won't overwrite an existing non-empty file (skips it).
set -euo pipefail

source "${0:A:h}/secrets-manifest.sh"

command -v bw >/dev/null || { echo "install first: brew install bitwarden-cli"; exit 1; }
command -v jq >/dev/null || { echo "install first: brew install jq"; exit 1; }

if [ -z "${BW_SESSION:-}" ]; then
  if [[ ! -t 0 ]]; then
    echo 'Non-interactive shell — unlock first:  export BW_SESSION="$(bw unlock --raw)"'
    exit 1
  fi
  # Both --raw forms print only the session key; prompts go to the tty.
  if bw login --check >/dev/null 2>&1; then
    BW_SESSION="$(bw unlock --raw)" || { echo "Unlock failed/cancelled"; exit 1; }
  else
    echo "Log into Bitwarden:"
    BW_SESSION="$(bw login --raw)" || { echo "Login failed/cancelled"; exit 1; }
  fi
  export BW_SESSION
fi
bws() { bw --session "$BW_SESSION" "$@"; }
err="$(bws sync 2>&1 >/dev/null)" || { echo "bw sync failed: ${err:-no message} — if the session expired, re-run the export"; exit 1; }

# Look items up by exact name inside the "Mac Migration" folder. `bw get <name>`
# is a fuzzy search (it also matches note bodies and "x.pub" for "x"), so it
# fails with "More than one result" for most keys.
FOLDER="$SECRETS_FOLDER"
FID="$(bws list folders --search "$FOLDER" | jq -r --arg n "$FOLDER" '.[]|select(.name==$n)|.id' | head -1)"
[ -n "$FID" ] || { echo "No '$FOLDER' folder in Bitwarden — run backup-secrets-to-bw.sh first"; exit 1; }
INDEX="$(bws list items --folderid "$FID" | jq -r '.[] | [.name, .id] | @tsv')"   # names + ids only
item_id() { print -r -- "$INDEX" | awk -F'\t' -v n="$1" '$1==n {print $2; exit}'; }

restore() {
  local item="$1" rel="$2" mode="$3" kind="$4" dest="$HOME/$2"
  if [ -s "$dest" ]; then echo "exists, skip: $rel"; return 0; fi
  local id; id="$(item_id "$item")"
  if [ -z "$id" ]; then echo "MISSING in vault: $item"; return 0; fi
  mkdir -p "${dest:h}"
  local ok=1
  case "$kind" in
    note) bws get notes "$id" > "$dest" 2>/dev/null || ok=0 ;;
    file) bws get attachment "${rel:t}" --itemid "$id" --output "$dest" >/dev/null 2>&1 || ok=0 ;;
  esac
  if [ "$ok" = 1 ] && [ -s "$dest" ]; then
    chmod "$mode" "$dest"
    echo "restored: $rel ($mode)"
  else
    rm -f "$dest"
    echo "FAILED to fetch: $item ($kind)"
  fi
}

for entry in $SECRETS; do
  IFS='|' read -r name rel mode kind <<< "$entry"
  restore "$name" "$rel" "$mode" "$kind"
done

[ -d "$HOME/.ssh" ] && chmod 700 "$HOME/.ssh"
echo ""
echo "Done. Reminders NOT in Bitwarden: WireGuard tunnels, the rotated Anthropic"
echo "API key, and GitHub CLI auth (run: gh auth login) — set those up manually."
