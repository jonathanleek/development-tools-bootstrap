#!/bin/zsh
# Reproduce the Claude Code environment: plugin marketplaces, the astronomer-data
# plugin, the narrowed airflow hook, and ~/.claude config.
# Idempotent. Needs the `claude` CLI (native installer, ~/.local/bin).
set -euo pipefail

REPO="${0:A:h:h}"          # repo root (scripts/ is one level down)
TPL="$REPO/claude-config"
CLAUDE_DIR="$HOME/.claude"
log() { print -P "%F{cyan}==>%f $*"; }

if ! command -v claude >/dev/null 2>&1; then
  log "claude CLI not found (run the native installer: curl -fsSL https://claude.ai/install.sh | bash) — skipping"
  exit 0
fi

mkdir -p "$CLAUDE_DIR"

# 1. Plugin marketplaces
log "Adding plugin marketplaces..."
claude plugin marketplace add astronomer/agents 2>/dev/null || true
claude plugin marketplace add anthropics/claude-plugins-official 2>/dev/null || true
claude plugin marketplace update 2>/dev/null || true

# 2. Plugin
log "Installing astronomer-data plugin..."
claude plugin install astronomer-data@astronomer 2>/dev/null || true

# 3. Re-apply the narrowed airflow-skill-suggester hook (plugin ships a broad one)
log "Patching airflow-skill-suggester hook..."
find "$CLAUDE_DIR/plugins/cache" -path '*skills/airflow/hooks/airflow-skill-suggester.sh' 2>/dev/null \
| while read -r hook; do
  [[ -f "$hook.orig-backup" ]] || cp "$hook" "$hook.orig-backup"
  cp "$TPL/airflow-hook-patch.sh" "$hook"
  chmod +x "$hook"
  print "   patched $hook"
done

# 4. Config: CLAUDE.md + statusline (copy), settings.json (merge, don't clobber)
log "Installing Claude config..."
cp "$TPL/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
cp "$TPL/statusline.sh" "$CLAUDE_DIR/statusline.sh"
chmod +x "$CLAUDE_DIR/statusline.sh"

# Merge the template settings into a settings file. Used for ~/.claude and for
# the mi6 user layer, which is the whole of Claude Code's settings under
# `mi6 claude` (mi6 points CLAUDE_CONFIG_DIR at a set built from the layers).
merge_settings() {
python3 - "$TPL/settings.json" "$1" <<'PY'
import json, os, sys
tpl = json.load(open(sys.argv[1]))
try:
    cur = json.load(open(sys.argv[2]))
except (FileNotFoundError, json.JSONDecodeError):
    cur = {}
cur.setdefault("extraKnownMarketplaces", {}).update(tpl.get("extraKnownMarketplaces", {}))
cur.setdefault("enabledPlugins", {}).update(tpl.get("enabledPlugins", {}))
cur["tui"] = tpl.get("tui", cur.get("tui"))
cur["statusLine"] = {"type": "command", "command": os.path.expanduser("~/.claude/statusline.sh")}
allow = cur.setdefault("permissions", {}).setdefault("allow", [])
for a in tpl.get("permissions", {}).get("allow", []):
    if a not in allow:
        allow.append(a)
os.makedirs(os.path.dirname(sys.argv[2]), exist_ok=True)
json.dump(cur, open(sys.argv[2], "w"), indent=2)
print("   merged " + sys.argv[2].replace(os.path.expanduser("~"), "~"))
PY
}
merge_settings "$CLAUDE_DIR/settings.json"

# 5. mi6 user layer (~/.mi6): the same preferences and settings for `mi6 claude`
export PATH="${GOBIN:-$(go env GOPATH 2>/dev/null || print "$HOME/go")/bin}:$PATH"
if command -v mi6 >/dev/null 2>&1; then
  log "Setting up the mi6 user layer..."
  mi6 init "$HOME" >/dev/null
  # AGENTS.md -> the installed CLAUDE.md, so both launch paths read one file.
  # Replace only mi6's empty stub, never a file with real content.
  agents="$HOME/.mi6/AGENTS.md"
  if [[ -L "$agents" ]]; then
    :
  elif ! awk '!/^# Rules for/ && NF {found=1} END {exit !found}' "$agents"; then
    rm "$agents" && ln -s "$CLAUDE_DIR/CLAUDE.md" "$agents"
    print "   linked ~/.mi6/AGENTS.md -> ~/.claude/CLAUDE.md"
  else
    print "   ~/.mi6/AGENTS.md has its own content — left as is"
  fi
  merge_settings "$HOME/.mi6/claude.json"
else
  log "mi6 not installed (scripts/make-dirs.sh installs it) — skipping the mi6 layer"
fi

log "Claude environment ready. Restart Claude Code to pick up config."
