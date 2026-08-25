#!/bin/zsh
# Create the standard directory structure. Idempotent (mkdir -p).
set -euo pipefail

# git repos, organized one folder per owner/org
GIT_ROOT="$HOME/Documents/git"
ORGS=(
  personal
  westbound-workshop
  astronomer
  apache
  arch-reactor
)

for org in $ORGS; do
  mkdir -p "$GIT_ROOT/$org"
  print "created $GIT_ROOT/$org"
done

print "Directory structure ready under $GIT_ROOT"
