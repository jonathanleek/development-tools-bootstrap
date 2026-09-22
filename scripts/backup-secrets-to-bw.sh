#!/bin/zsh
# Back up local secrets into Bitwarden as Secure Notes under a "Mac Migration"
# folder. No secret value is ever printed.
#
# STEP 1 — unlock your vault in THIS terminal (prompts for master password):
#     export BW_SESSION="$(bw unlock --raw)"
#   (if not logged in yet, run `bw login` first)
#
# STEP 2 — run this script:
#     scripts/backup-secrets-to-bw.sh
#
# Idempotent: an item whose name already exists in the folder is skipped.
# Restore later:  bw get notes "<item name>" > <destination file>
set -euo pipefail

command -v bw >/dev/null || { echo "install first: brew install bitwarden-cli"; exit 1; }
command -v jq >/dev/null || { echo "install first: brew install jq"; exit 1; }

if [ -z "${BW_SESSION:-}" ]; then
  cat <<'MSG'
BW_SESSION is not set. Unlock your vault first, then re-run this script:

    export BW_SESSION="$(bw unlock --raw)"

(If you are not logged in yet, run `bw login` first.)
MSG
  exit 1
fi

bws() { bw --session "$BW_SESSION" "$@"; }

# verify the session actually works
if ! bws sync >/dev/null 2>&1; then
  echo "BW_SESSION is set but not valid — re-run: export BW_SESSION=\"\$(bw unlock --raw)\""
  exit 1
fi

# --- ensure the "Mac Migration" folder ---
FOLDER="Mac Migration"
FID="$(bws list folders --search "$FOLDER" | jq -r --arg n "$FOLDER" '.[]|select(.name==$n)|.id' | head -1)"
if [ -z "$FID" ]; then
  FID="$(bws get template folder | jq --arg n "$FOLDER" '.name=$n' | bws encode | bws create folder | jq -r '.id')"
  echo "created folder: $FOLDER"
fi

# --- add one Secure Note per file (content read via jq --rawfile; never echoed) ---
# Secure Note field caps at 10000 chars; stay under it with margin.
MAXBYTES=9000

add_note() {
  local name="$1" file="$2"
  [ -f "$file" ] || return 0
  if [ "$(wc -c < "$file")" -gt "$MAXBYTES" ]; then
    echo "SKIP (too large for a Secure Note): $name — back up this file manually"
    return 0
  fi
  if bws list items --folderid "$FID" --search "$name" \
       | jq -e --arg n "$name" '.[]|select(.name==$n)' >/dev/null 2>&1; then
    echo "exists: $name"; return 0
  fi
  if bws get template item \
    | jq --arg n "$name" --arg f "$FID" --rawfile c "$file" \
        '.type=2 | .secureNote={"type":0} | .name=$n | .folderId=$f | .notes=$c | .login=null' \
    | bws encode | bws create item >/dev/null 2>&1; then
    echo "saved:  $name"
  else
    echo "FAILED: $name (skipped, continuing)"
  fi
}

# SSH private + public keys and config
for k in ~/.ssh/id_ed25519 ~/.ssh/homelab_ansible ~/.ssh/airflow_deploy_key \
         ~/.ssh/config ~/.ssh/conductor_config; do
  add_note "ssh/$(basename "$k")" "$k"
done
for pub in ~/.ssh/*.pub(N); do add_note "ssh/$(basename "$pub")" "$pub"; done

# CLI / service credentials
add_note "aws/config"         ~/.aws/config
add_note "gh/hosts.yml"       ~/.config/gh/hosts.yml
add_note "docker/config.json" ~/.docker/config.json

# Secret directories -> one note per file inside
for d in ~/.leek-homelab-secrets ~/.mcp-auth; do
  [ -d "$d" ] || continue
  find "$d" -type f ! -name '.DS_Store' | while read -r f; do
    add_note "${f#$HOME/}" "$f"
  done
done

echo ""
echo "Done. Review the '$FOLDER' folder in Bitwarden."
echo "Reminder: WireGuard tunnels + the (rotated) Anthropic API key must be added manually."
