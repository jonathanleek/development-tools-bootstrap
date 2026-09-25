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

for dir in $DIRS; do
  mkdir -p "$GIT_ROOT/$dir"
  print "created $GIT_ROOT/$dir"
done

print "Directory structure ready under $GIT_ROOT"
