#!/bin/zsh
# Back up local secrets into Bitwarden under a "Mac Migration" folder: small
# files as Secure Note bodies, large ones as attachments. The list lives in
# scripts/secrets-manifest.sh. No secret value is ever printed.
#
# STEP 1 — unlock your vault in THIS terminal (prompts for master password):
#     export BW_SESSION="$(bw unlock --raw)"
#   (if not logged in yet, run `bw login` first)
#
# STEP 2 — run this script:
#     scripts/backup-secrets-to-bw.sh            # add new items only
#     scripts/backup-secrets-to-bw.sh --update   # also refresh changed ones
#
# Idempotent: by default an item whose name already exists in the folder is
# skipped, even if the local file has changed since. With --update, each
# existing item is compared with the local file (in a private temp dir, never
# printed) and replaced if it differs — run it after a `terraform apply` or
# after rotating a key.
# Restore with scripts/restore-secrets-from-bw.sh.
set -euo pipefail

source "${0:A:h}/secrets-manifest.sh"

UPDATE=0
case "${1:-}" in
  "")       ;;
  --update) UPDATE=1 ;;
  *)        echo "usage: ${0:t} [--update]"; exit 2 ;;
esac

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
if ! err="$(bws sync 2>&1 >/dev/null)"; then
  echo "bw sync failed: ${err:-no message}"
  echo "If the session expired, re-run: export BW_SESSION=\"\$(bw unlock --raw)\""
  exit 1
fi

# --- ensure the "Mac Migration" folder ---
FOLDER="$SECRETS_FOLDER"
FID="$(bws list folders --search "$FOLDER" | jq -r --arg n "$FOLDER" '.[]|select(.name==$n)|.id' | head -1)"
if [ -z "$FID" ]; then
  FID="$(bws get template folder | jq --arg n "$FOLDER" '.name=$n' | bws encode | bws create folder | jq -r '.id')"
  echo "created folder: $FOLDER"
fi

# --- exact-name index of the folder: name<TAB>id<TAB>attachment count ---
# (`bw list --search` is fuzzy, so always compare names exactly)
index() { bws list items --folderid "$FID" | jq -r '.[] | [.name, .id, (.attachments // [] | length)] | @tsv'; }
INDEX="$(index)"
lookup() { print -r -- "$INDEX" | awk -F'\t' -v n="$1" '$1==n {print $'"$2"'; exit}'; }

# Secure Note field caps at 10000 chars; stay under it with margin.
MAXBYTES=9000

# --update compares vault copies with local files here; removed on exit.
CMP_DIR="$(mktemp -d)"; chmod 700 "$CMP_DIR"
trap 'rm -rf "$CMP_DIR"' EXIT

update_note() {   # name, file, item id
  local name="$1" file="$2" id="$3" vault="$CMP_DIR/note"
  if ! bws get notes "$id" > "$vault" 2>/dev/null; then echo "FAILED: $name (could not read vault copy)"; return 0; fi
  if cmp -s "$vault" "$file"; then echo "unchanged: $name"; return 0; fi
  if [ "$(wc -c < "$file")" -gt "$MAXBYTES" ]; then
    echo "SKIP (changed, but now too large for a note — mark it 'file' in secrets-manifest.sh): $name"
    return 0
  fi
  if bws get item "$id" | jq --rawfile c "$file" '.notes=$c' \
       | bws encode | bws edit item "$id" >/dev/null 2>&1; then
    echo "updated: $name"
  else
    echo "FAILED: $name (update failed; vault copy left as it was)"
  fi
}

update_file() {   # name, file, item id
  local name="$1" file="$2" id="$3" vault="$CMP_DIR/file" old
  if ! bws get attachment "${file:t}" --itemid "$id" --output "$vault" >/dev/null 2>&1; then
    echo "FAILED: $name (could not read vault attachment)"; return 0
  fi
  if cmp -s "$vault" "$file"; then echo "unchanged: $name"; return 0; fi
  # upload the new copy first, then delete the old one, so a failed upload
  # never leaves the item without its attachment
  old="$(bws get item "$id" | jq -r --arg f "${file:t}" '.attachments[]? | select(.fileName==$f) | .id')"
  if ! bws create attachment --file "$file" --itemid "$id" >/dev/null 2>&1; then
    echo "FAILED: $name (upload failed; vault copy left as it was)"; return 0
  fi
  local a
  for a in ${(f)old}; do
    bws delete attachment "$a" --itemid "$id" >/dev/null 2>&1 || {
      echo "FAILED: $name (new copy uploaded, but the old attachment could not be removed — delete it in Bitwarden, or restore will stop at 'more than one')"
      return 0
    }
  done
  echo "updated: $name (attachment)"
}

new_note() {   # name, body -> prints new item id
  bws get template item \
    | jq --arg n "$1" --arg f "$FID" --arg c "$2" \
        '.type=2 | .secureNote={"type":0} | .name=$n | .folderId=$f | .notes=$c | .login=null' \
    | bws encode | bws create item | jq -r '.id'
}

add_note() {
  local name="$1" file="$2" id
  id="$(lookup "$name" 2)"
  if [ -n "$id" ]; then
    if [ "$UPDATE" = 1 ]; then update_note "$name" "$file" "$id"; else echo "exists: $name"; fi
    return 0
  fi
  if [ "$(wc -c < "$file")" -gt "$MAXBYTES" ]; then
    echo "SKIP (too large for a note — mark it 'file' in secrets-manifest.sh): $name"
    return 0
  fi
  # content read via jq --rawfile; never echoed
  if bws get template item \
    | jq --arg n "$name" --arg f "$FID" --rawfile c "$file" \
        '.type=2 | .secureNote={"type":0} | .name=$n | .folderId=$f | .notes=$c | .login=null' \
    | bws encode | bws create item >/dev/null 2>&1; then
    echo "saved:  $name"
  else
    echo "FAILED: $name (skipped, continuing)"
  fi
}

add_file() {
  local name="$1" file="$2" id
  id="$(lookup "$name" 2)"
  if [ -n "$id" ] && [ "$(lookup "$name" 3)" -gt 0 ]; then
    if [ "$UPDATE" = 1 ]; then update_file "$name" "$file" "$id"; else echo "exists: $name"; fi
    return 0
  fi
  # the note body only says where the file lives; the content is the attachment
  [ -n "$id" ] || id="$(new_note "$name" "attachment: ${file:t} -> ~/${file#$HOME/}" 2>/dev/null)" || id=""
  if [ -n "$id" ] && bws create attachment --file "$file" --itemid "$id" >/dev/null 2>&1; then
    echo "saved:  $name (attachment)"
  else
    echo "FAILED: $name (attachments need Bitwarden Premium; skipped, continuing)"
  fi
}

for entry in $SECRETS; do
  IFS='|' read -r name rel mode kind <<< "$entry"
  file="$HOME/$rel"
  [ -f "$file" ] || { echo "not on this Mac, skip: $rel"; continue; }
  case "$kind" in
    note) add_note "$name" "$file" ;;
    file) add_file "$name" "$file" ;;
  esac
done

echo ""
echo "Done. Review the '$FOLDER' folder in Bitwarden."
echo "Not in Bitwarden: WireGuard tunnels, the rotated Anthropic API key, gh auth (gh auth login)."
