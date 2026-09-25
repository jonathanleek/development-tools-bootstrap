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
# repos below it. Created empty; fill it by hand.
for dir in $DIRS; do
  mkdir -p "$GIT_ROOT/$dir/.mi6"
  print "created $GIT_ROOT/$dir (with .mi6/)"
done
mkdir -p "$GIT_ROOT/.mi6"

print "Directory structure ready under $GIT_ROOT"
