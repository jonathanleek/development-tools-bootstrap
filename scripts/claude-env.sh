#!/bin/zsh
# Reproduce the Claude Code environment: plugin marketplaces, the astronomer-data
# plugin, the narrowed airflow hook, skill repos, and ~/.claude config.
# Idempotent. Needs the `claude` CLI (claude-code cask) and GitHub auth.
set -euo pipefail

REPO="${0:A:h:h}"          # repo root (scripts/ is one level down)
TPL="$REPO/claude"
CLAUDE_DIR="$HOME/.claude"
log() { print -P "%F{cyan}==>%f $*"; }

if ! command -v claude >/dev/null 2>&1; then
  log "claude CLI not found (install the claude-code cask first) — skipping"
  exit 0
fi

mkdir -p "$CLAUDE_DIR/skills"

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

# 4. Skill sources: clone/update each repo, then symlink every skills/<name>/
#    folder that contains a SKILL.md into ~/.claude/skills/<name>.
#    Format: "github-owner/repo-name|local-clone-path". First source wins on a
#    name collision. Only dangling symlinks are ever removed from ~/.claude/skills.
SKILL_SOURCES=(
  "jonathanleek/claude-skills|$HOME/Documents/git/personal/claude-skills"
  "jonathanleek/makerspace-claude-skills|$HOME/Documents/git/westbound-workshop/makerspace-claude-skills"
)

sync_repo() {  # sync_repo owner/name /local/path
  local slug="$1" dest="$2"
  if [[ -d "$dest/.git" ]]; then
    git -C "$dest" pull -q --ff-only 2>/dev/null || true
    return 0
  fi
  mkdir -p "${dest:h}"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh repo clone "$slug" "$dest" 2>/dev/null && return 0
  fi
  git clone "git@github.com:$slug.git" "$dest" 2>/dev/null \
    || git clone "https://github.com/$slug.git" "$dest" 2>/dev/null \
    || { print "   could not clone $slug — skipping"; return 1; }
}

log "Syncing skill sources..."
typeset -A linked
for entry in "${SKILL_SOURCES[@]}"; do
  slug="${entry%%|*}"; dest="${entry#*|}"
  sync_repo "$slug" "$dest" || continue
  for skill_md in "$dest"/skills/*/SKILL.md(N); do
    src="${skill_md:h}"; name="${src:t}"
    if [[ -n "${linked[$name]:-}" ]]; then
      print "   skip $name from $slug (already linked from ${linked[$name]})"
      continue
    fi
    ln -sfn "$src" "$CLAUDE_DIR/skills/$name"
    linked[$name]="$slug"
    print "   linked $name <- $slug"
  done
done

# Remove symlinks whose target no longer exists (skill deleted or repo moved).
for link in "$CLAUDE_DIR"/skills/*(@N); do
  if [[ ! -e "$link" ]]; then
    rm "$link"
    print "   removed dangling link ${link:t}"
  fi
done

# 5. Config: CLAUDE.md + statusline (copy), settings.json (merge, don't clobber)
log "Installing Claude config..."
cp "$TPL/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
cp "$TPL/statusline.sh" "$CLAUDE_DIR/statusline.sh"
chmod +x "$CLAUDE_DIR/statusline.sh"

python3 - "$TPL/settings.json" "$CLAUDE_DIR/settings.json" <<'PY'
import json, os, sys
tpl = json.load(open(sys.argv[1]))
try:
    cur = json.load(open(sys.argv[2]))
except (FileNotFoundError, json.JSONDecodeError):
    cur = {}
cur.setdefault("enabledPlugins", {}).update(tpl.get("enabledPlugins", {}))
cur["tui"] = tpl.get("tui", cur.get("tui"))
cur["statusLine"] = {"type": "command", "command": os.path.expanduser("~/.claude/statusline.sh")}
allow = cur.setdefault("permissions", {}).setdefault("allow", [])
for a in tpl.get("permissions", {}).get("allow", []):
    if a not in allow:
        allow.append(a)
os.makedirs(os.path.dirname(sys.argv[2]), exist_ok=True)
json.dump(cur, open(sys.argv[2], "w"), indent=2)
print("   merged settings.json")
PY

log "Claude environment ready. Restart Claude Code to pick up config."
