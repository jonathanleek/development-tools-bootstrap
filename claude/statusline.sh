#!/bin/bash
# Claude Code statusline. Receives session JSON on stdin, prints one line.
# Shows: model · project dir · git branch(+dirty) · lines changed · session cost
input=$(cat)

j() { printf '%s' "$input" | jq -r "$1" 2>/dev/null; }

model=$(j '.model.display_name // "?"')
dir=$(j '.workspace.current_dir // .cwd // "."')
added=$(j '.cost.total_lines_added // 0')
removed=$(j '.cost.total_lines_removed // 0')
cost=$(j '(.cost.total_cost_usd // 0)')

name=$(basename "$dir")
branch=$(git -C "$dir" rev-parse --abbrev-ref HEAD 2>/dev/null)
dirty=""
[ -n "$branch" ] && [ -n "$(git -C "$dir" status --porcelain 2>/dev/null | head -1)" ] && dirty="*"

# colors
C='\033[36m'; B='\033[34m'; G='\033[32m'; Y='\033[33m'; R='\033[31m'; D='\033[2m'; X='\033[0m'

out=$(printf "${C}⚡ %s${X}  ${B}%s${X}" "$model" "$name")
if [ -n "$branch" ]; then
  col=$G; [ -n "$dirty" ] && col=$Y
  out="$out$(printf "  ${col} %s%s${X}" "$branch" "$dirty")"
fi
if [ "$added" != "0" ] || [ "$removed" != "0" ]; then
  out="$out$(printf "  ${G}+%s${X}${D}/${X}${R}-%s${X}" "$added" "$removed")"
fi
# cost shown only once it's non-trivial
costfmt=$(printf '%.2f' "$cost" 2>/dev/null || echo 0)
[ "$costfmt" != "0.00" ] && out="$out$(printf "  ${D}\$%s${X}" "$costfmt")"

printf '%b' "$out"
