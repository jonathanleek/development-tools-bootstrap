#!/bin/zsh
# Create the standard directory structure and give every folder an mi6 layer.
# Idempotent: mkdir -p, and `mi6 init` never overwrites a file it finds.
set -euo pipefail

# git repos, organized one folder per owner/org (plus sub-groupings)
GIT_ROOT="${GIT_ROOT:-$HOME/Documents/git}"
DIRS=(
  personal
  westbound-workshop
  astronomer
  astronomer/customers
  astronomer/examples
  astronomer/internal
  astronomer/tools
  apache
  arch-reactor
)

# mi6 (https://github.com/jonathanleek/mi6) is a Go module; `go` comes from
# the Brewfile. `go install` puts the binary in $GOBIN, or $GOPATH/bin, or
# ~/go/bin. Put that on the PATH for this script; the shell dotfiles do it
# for interactive sessions.
export PATH="${GOBIN:-$(go env GOPATH 2>/dev/null || print "$HOME/go")/bin}:$PATH"
if ! command -v mi6 >/dev/null 2>&1; then
  print "Installing mi6..."
  go install github.com/jonathanleek/mi6/cmd/mi6@latest
fi
command -v mi6 >/dev/null 2>&1 || { print "mi6 not on PATH after go install" >&2; exit 1; }

# Every folder is an mi6 layer: a .mi6/ that holds the agent config for the
# repos below it. `mi6 init` creates one with every file mi6 reads, empty but
# valid, and never overwrites.
mkdir -p "$GIT_ROOT"
mi6 init "$GIT_ROOT" >/dev/null
for dir in $DIRS; do
  mkdir -p "$GIT_ROOT/$dir"
  mi6 init "$GIT_ROOT/$dir" >/dev/null
  print "created $GIT_ROOT/$dir (with .mi6/)"
done

print "Directory structure ready under $GIT_ROOT"
