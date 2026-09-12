#!/bin/zsh
# Clone all Obsidian/data vaults and register them with Obsidian.
# Idempotent: existing repos are pulled (--ff-only); existing Obsidian entries kept.
# Needs GitHub auth (gh logged in, or an SSH key registered) for private repos.
set -euo pipefail

print -P "%F{cyan}==>%f Setting up vaults..."

# "clone_path|github_slug"  (dir name == repo name, kebab-case)
VAULTS=(
  "$HOME/Documents/git/astronomer/astronomer-vault|jonathanleek/astronomer-vault"
  "$HOME/Documents/git/personal/education-vault|jonathanleek/education-vault"
  "$HOME/Documents/git/personal/home-maintenance-vault|jonathanleek/home-maintenance-vault"
  "$HOME/Documents/git/westbound-workshop/westbound-workshop-vault|jonathanleek/westbound-workshop-vault"
)

clone_one() {
  local path="$1" slug="$2"
  if [[ -d "$path/.git" ]]; then
    print "exists: $path (pull --ff-only)"
    git -C "$path" pull --ff-only 2>/dev/null || print "  (skipped pull)"
    return 0
  fi
  mkdir -p "${path:h}"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh repo clone "$slug" "$path"
  else
    git clone "git@github.com:$slug.git" "$path" \
      || git clone "https://github.com/$slug.git" "$path"
  fi
}

for entry in $VAULTS; do
  clone_one "${entry%%|*}" "${entry##*|}" \
    || print "  ⚠ could not clone ${entry##*|} (check gh auth / SSH key, then re-run)"
done

# Register vaults with Obsidian (Obsidian should be closed while this runs).
OBSIDIAN_JSON="$HOME/Library/Application Support/obsidian/obsidian.json"
python3 - "$OBSIDIAN_JSON" \
  "$HOME/Documents/git/astronomer/astronomer-vault" \
  "$HOME/Documents/git/personal/education-vault" \
  "$HOME/Documents/git/personal/home-maintenance-vault" \
  "$HOME/Documents/git/westbound-workshop/westbound-workshop-vault" <<'PY'
import json, os, sys, time, secrets
cfg_path, *vaults = sys.argv[1:]
os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
try:
    with open(cfg_path) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}
cfg.setdefault("vaults", {})
existing = {v.get("path") for v in cfg["vaults"].values()}
added = 0
for p in vaults:
    if p in existing:
        continue
    cfg["vaults"][secrets.token_hex(8)] = {"path": p, "ts": int(time.time() * 1000)}
    added += 1
with open(cfg_path, "w") as f:
    json.dump(cfg, f, indent=2)
print(f"Obsidian: registered {added} new vault(s); {len(existing)} already present")
PY

print "Vaults ready."
