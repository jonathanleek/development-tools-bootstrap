# Personal working preferences — Jonathan Leek

Applies to all projects. A repo's own CLAUDE.md takes precedence over this.

## Interaction style
- **Break large requests into small, reviewable chunks.** When a task means
  reviewing or deciding over a list — package lists, files, config entries,
  options, a multi-part plan — present **one section at a time**, wait for my
  approval, then continue. Do not dump the whole thing at once.
  - Example: approving an app-install list *group by group* (CLI tools, then dev
    apps, then browsers…) rather than all thirty entries in one message.
  - Number the chunks ("List 3 of 6") so I know how much is left.
- Keep responses concise and skimmable. Lead with the answer or recommendation,
  not a survey of every option.
- When you have enough to act, act — but see "Confirm first."

## Confirm first
- Never push commits, open/merge PRs, or rename/delete remote repos or other
  outward-facing / hard-to-reverse actions without my explicit OK. Preparing a
  local commit is fine; ask before pushing.
- Before deleting or overwriting something you didn't create, show me what it is
  first. Prefer moving to a backup over hard-deleting when practical.

## Conventions
- Repo and directory names use **kebab-case**. Local repos live in
  `~/Documents/git/<org>/` — orgs: `personal`, `astronomer`, `westbound-workshop`,
  `apache`, `arch-reactor`.
- Secrets never go in git or plaintext dotfiles; source them from a gitignored
  file or pull from Bitwarden.
- Commit messages: concise subject line + a body explaining *why*; end with the
  `Co-Authored-By` trailer.

## Verify before recommending
- Check facts against the live source rather than assuming — e.g. confirm a
  Homebrew cask/formula actually exists, a path resolves, a repo/remote is real —
  before suggesting or acting on it.
