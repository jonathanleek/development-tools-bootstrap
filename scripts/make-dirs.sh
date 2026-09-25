#!/bin/zsh
# Create the standard directory structure. Idempotent (mkdir -p).
set -euo pipefail

# git repos, organized one folder per owner/org (plus sub-groupings)
GIT_ROOT="$HOME/Documents/git"
DIRS=(
  personal
  westbound-workshop
  astronomer
  astronomer/customers
  astronomer/examples
  astronomer/internal
  apache
  arch-reactor
)

# Every folder is an mi6 layer: a .mi6/ that holds the agent config for the
# repos below it. `mi6 init` creates one with every file mi6 reads, empty but
# valid, and never overwrites. Without mi6 on the PATH, create the folder only.
init_layer() {
  if command -v mi6 >/dev/null 2>&1; then
    mi6 init "$1" >/dev/null
  else
    mkdir -p "$1/.mi6"
  fi
}

mkdir -p "$GIT_ROOT"
init_layer "$GIT_ROOT"
for dir in $DIRS; do
  mkdir -p "$GIT_ROOT/$dir"
  init_layer "$GIT_ROOT/$dir"
  print "created $GIT_ROOT/$dir (with .mi6/)"
done
command -v mi6 >/dev/null 2>&1 || print "mi6 not installed: layers are empty folders; run 'mi6 init' in each later"

print "Directory structure ready under $GIT_ROOT"
