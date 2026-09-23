# Domains: per-folder agent configuration

Status: design, not implemented. Nothing in this document exists in the repo yet.

## The problem

Repos live under `~/Documents/git/<domain>/`. The top-level folders are *domains*:
`personal`, `astronomer`, `westbound-workshop`, `apache`, `arch-reactor`, and a
new `meta` domain for this repo and the other config repos. A domain can have
sub-folders that group work, such as `astronomer/customers/<customer>/`.

Every project in a domain should get the same agent setup without any
per-project work, and a project should be able to add to that setup. The setup
must not be committed to the project's repo, because many repos belong to
clients. It must work for Claude Code and for open models run through OpenCode,
and it must work inside Termic, which checks tasks out to
`~/termic/tasks/<project>/<task>/`, outside the domain folder.

The setup has to cover five things:

- instructions, in `AGENTS.md` form
- skills
- MCP servers
- which models and which account a domain may use
- permissions, since the `meta` domain needs write access that no client domain
  gets

## Why not a `CLAUDE.md` in the domain folder

Claude Code loads `CLAUDE.md` from every ancestor of the working directory, so a
`CLAUDE.md` in `~/Documents/git/astronomer/` reaches every repo below it. Three
things rule it out as the whole answer:

- A Termic task is not below the domain folder, so the file never loads there.
- It carries instructions only. Skills, MCP servers, settings, and model policy
  in an ancestor folder are not read.
- OpenCode reads one `AGENTS.md`, the first it finds walking up, so a repo that
  ships its own hides the domain's.

The mechanism that every tool supports, and that reaches a Termic task, is an
alternate config directory chosen by environment variable. Claude Code reads
`CLAUDE_CONFIG_DIR`. OpenCode reads `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR`.
Aider takes `--config`. A domain is therefore a config directory, and a launcher
picks it.

## Terms

- **Domain**: a top-level folder under `~/Documents/git/`.
- **Layer**: a folder in the path from the domain down to the repo that has
  config in this repo. `astronomer`, `astronomer/customers`, and
  `astronomer/customers/acme` are three layers.
- **Config set**: the merged result of `shared` plus every layer on the path,
  built as one directory per tool.
- **Launcher**: the `mi6` script that resolves the layers and starts the tool.

## How the launcher finds the domain

The launcher resolves the domain from the path of the repo's main checkout, not
from its git remote. A remote does not identify the domain: some customer repos
are cloned from the customer, some are created in the Astronomer org, and some
have no remote.

1. Run `git rev-parse --git-common-dir`. Inside a worktree, including a Termic
   task, this returns the main checkout's `.git` directory.
2. Take the path of that checkout relative to `~/Documents/git/`, for example
   `astronomer/customers/acme/acme-pipeline`.
3. Walk that path from the top. Each folder that has a matching folder under
   `domains/` in this repo is a layer.
4. If the checkout is not under `~/Documents/git/`, use the `default` layer.
5. `MI6_DOMAIN=<path>` overrides steps 1 to 4.

## Layout in this repo

```
domains/
	shared/                      applied to every domain
	default/                     repos outside ~/Documents/git
	meta/
	personal/
	astronomer/
	astronomer/customers/        stricter model policy, work account
	astronomer/customers/acme/   one customer
	westbound-workshop/
project-overrides/
	<repo-name>/                 additions for one repo, never committed to it
contexts/
	home/                        applied when on the home network, see Contexts
	away/
machines/
	mac-studio/                  applied on that machine only, see Machines
	macbook-pro/
```

Each layer folder holds any of these, all optional:

| File | Purpose |
|---|---|
| `AGENTS.md` | Instructions. Layers concatenate, top layer first. |
| `skills/<name>/SKILL.md` | Skills kept in this repo. Layers union. On a name collision the deeper layer wins. |
| `skill_sources` in `policy.json` | Skill repos. Each `skills/<name>/` folder with a `SKILL.md` in the repo is linked in, same collision rule. |
| `mcp.json` | MCP servers. Layers union. |
| `policy.json` | Account, allowed models, and which contexts apply. A deeper layer can narrow the model list, not widen it. |
| `claude/settings.json` | Claude Code settings, including permissions. Deep-merged, deeper layer wins. |
| `opencode.json` | OpenCode settings. Deep-merged, deeper layer wins. |

`policy.json`:

```json
{
	"account": "work",
	"models": {
		"claude": ["claude-opus-5-5", "claude-sonnet-5"],
		"opencode": ["anthropic/*", "lmstudio/openai/gpt-oss-120b"]
	},
	"contexts": ["home"],
	"skill_sources": ["jonathanleek/claude-skills"],
	"astro": {
		"organization": "acme-corp",
		"workspace": "acme-prod"
	}
}
```

`astro` names the Astronomer organization and workspace that `astro` and Otto
work against in this layer. See Astronomer organization per layer.

`contexts` lists the context groups the launcher evaluates for this layer. A
layer that lists none runs no network probe.

`skill_sources` lists GitHub repos. The launcher clones each one under
`~/Documents/git/` on first use and links its skills into the set. This is what
`scripts/claude-env.sh` does today with `SKILL_SOURCES`, per layer instead of
for every project. `claude-skills` belongs in `shared`, so every domain gets it.
`makerspace-claude-skills` belongs in `westbound-workshop`.

The build turns `models.claude` into `availableModels` and `model` in the Claude
settings, and `models.opencode` into `enabled_providers` and `model` in the
OpenCode config.

## Built config sets

The build writes one directory per config set and per tool:

```
~/.agents/
	astronomer/customers/acme/
		claude/        CLAUDE_CONFIG_DIR for this set
		opencode/      OPENCODE_CONFIG_DIR for this set
		astro/         ASTRO_HOME for this set, when the layer sets "astro"
	accounts/
		work/          credentials shared by every set with "account": "work"
		personal/
```

A path that adds no layer of its own uses its nearest ancestor's set. A customer
folder with no `domains/` entry runs as `astronomer/customers`.

Inside a set, every file that a tool reads at start is a symlink into this repo:
`AGENTS.md`, each skill, `settings.json`, `opencode.json`. Editing the repo
changes the running setup. Nothing is copied.

Two things are not symlinks, because the tool writes them itself:

- **Plugins.** Claude Code installs plugins into the config directory. The
  launcher installs the ones the set lists, and skips ones already present.
- **MCP servers.** Claude Code stores user-scope servers in the config
  directory's `.claude.json`. The launcher registers the servers from the merged
  `mcp.json` and skips ones already registered.

Credentials are symlinks into `~/.agents/accounts/<account>/`, so two sets that
name the same account share one login. Which files hold credentials on macOS,
and whether the Keychain entry follows `CLAUDE_CONFIG_DIR`, is checked on the new
machine before this is relied on. Termic does the same split for its named
accounts, so it is known to work for Claude Code.

## The launcher

`mi6 <tool> [args]` does this on every run:

1. Pull this repo and every skill repo the layers use, if the last pull is
   more than an hour old. See Keeping two machines in sync.
2. Resolve the layers, or take `MI6_DOMAIN`.
3. Add the machine layer for this hostname, if one exists. See Machines.
4. Evaluate the contexts the merged `policy.json` lists, and add the matching
   context layer on top. See Contexts.
5. Build or refresh the config set. A refresh compares symlink targets and
   takes well under a second. It also creates the set the first time a new
   customer folder is used.
6. Sync plugins and MCP servers if the merged list changed.
7. Export `CLAUDE_CONFIG_DIR` or `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR`,
   and `ASTRO_HOME` when the merged policy sets `astro`.
8. `exec` the real tool with the remaining arguments.

Layers merge in this order, later wins: `shared`, the domain path from the top
down, the machine, the context.

`mi6 --no-domain <tool>` skips steps 1 to 7 and starts the tool with plain
user config. Use it to repair a broken `meta` config.

Termic's agent registry runs `mi6 claude` and `mi6 opencode` in place of the
bare commands. Termic runs registry commands in a login shell, so the launcher
must be on the login-shell `PATH`, which `setup.sh` already sets up through
`.zprofile`.

## What changes when you edit config

| You edit | Effect |
|---|---|
| `AGENTS.md`, a skill, `settings.json`, `opencode.json` | Live. The next agent start reads it. A running Claude Code session reloads settings on its own. |
| `mcp.json`, a plugin list | Applied on the next `mi6` run. |
| A new layer folder under `domains/` | Built on the next `mi6` run under that path. |
| `make-dirs.sh` | Only matters on a new machine. |

You do not re-run the bootstrap after the initial machine setup. `setup.sh`
installs the launcher and builds every set once, before any agent exists to do
it.

## Project overrides

`project-overrides/<repo-name>/` holds `AGENTS.md`, `skills/`, and `mcp.json`
for one repo, on top of its layers. The launcher links them into the checkout as
`.claude/skills/<name>` and `.opencode/skills/<name>`, and adds the link names
to `.git/info/exclude`. That file is per clone and never committed, so the
client's repo stays clean. A Termic worktree shares the main checkout's
`.git/info/exclude`.

Owned repos never commit agent config either. A repo that should carry its own
config is the exception and is not covered here.

## Contexts: config that depends on the network

A context is a layer that applies because of where the machine is, not what
repo it is in. The one context group so far is `home`: whether the machine can
reach the homelab network. It matters for `leek-homelab` and for shop work that
reaches the same network, and for nothing else, so only those layers list it in
`policy.json`. A customer session never runs the probe.

### Detect the network, not the services

A host that does not answer may be down, and that may be the reason for the
session. So the probe tests for the network itself and never for a host on it.
Reachability of individual hosts is reported as a fact, not used as a gate.

Two signals, both independent of any server:

- **Onsite.** The default gateway's MAC address is the UDM-Pro's. A gateway IP
  alone is not enough, since `192.168.1.1` is every coffee shop's router.
- **Remote.** Teleport, through WiFiman, is WireGuard, and on macOS it appears
  as a `utun` interface that carries the route to the homelab VLANs. If the
  route to the server VLAN goes through a `utun` interface, the tunnel is up.

The Wi-Fi name is not used. Reading it needs Location Services permission for
the calling process, which a script spawned by Termic does not have.

```zsh
iface=$(route -n get 10.100.20.0 | awk '/interface/ {print $2}')
gw_mac=$(arp -n $(route -n get default | awk '/gateway/ {print $2}') | awk '{print $4}')

case $iface in
	utun*) ctx=home-vpn ;;
	en*)   [[ $gw_mac == 68:d7:9a:21:c1:9a ]] && ctx=home-lan || ctx=away ;;
	*)     ctx=away ;;
esac
```

| State | Meaning | Context layer |
|---|---|---|
| `home-lan` | Router MAC matches | `contexts/home/` |
| `home-vpn` | Teleport tunnel routes the server VLAN | `contexts/home/` |
| `away` | Neither | `contexts/away/` |

The values come from `~/Documents/git/personal/leek-homelab`, which is the
source of truth for the network. `contexts/home/network.json` holds only what
the probe needs and names the files it was copied from:

| Value | Source in `leek-homelab` |
|---|---|
| UDM-Pro MAC `68:d7:9a:21:c1:9a` | `leek-homelab/infrastructure/network-upgrade-10g.md` |
| Server VLAN `10.100.20.0/24` | `terraform/unifi/networks.tf` |
| Pi-hole `10.100.20.10`, for an optional DNS cross-check | `leek-homelab/runbooks/deploy-new-service.md` |

### Applied at launch and refreshed per prompt

The launcher evaluates the context once and merges the context layer last, so
it can add the homelab MCP servers and an `AGENTS.md` line such as "homelab
reachable over Teleport". A session keeps the MCP servers it started with, so
coming home mid-session needs a restart to gain them.

The other direction is the dangerous one: leaving the house mid-session. A
Claude Code `UserPromptSubmit` hook in `contexts/home/claude/settings.json` runs
the same probe before each prompt and adds one line of context, for example
`network: away, homelab unreachable`, or `network: home-lan, proxmox-1 not
answering on 8006`. The probe takes well under a second. OpenCode's plugin hooks
are checked for an equivalent.

## Astronomer organization per layer

Customer work runs against that customer's Astronomer organization. The Astro
CLI keeps one active organization and workspace in `~/.astro/config.yaml`, and
`astro organization switch` changes it for every shell on the machine. Two
Termic tasks for two customers would fight over it. Otto inherits the same
context: `astro otto` sets `ASTRO_TOKEN`, `ASTRO_DOMAIN`, and
`ASTRO_ORGANIZATION` from the active login.

The CLI reads `ASTRO_HOME` and, when it is set, keeps `.astro/` there instead
of under `$HOME`. That directory holds the login contexts, Otto's user settings
in `otto/settings.json`, and Otto's sessions. So a layer that sets `astro` in
`policy.json` gets its own `astro/` directory in the config set, and `mi6`
exports `ASTRO_HOME` to it. Each customer layer is logged in to its own
organization, and sessions for different customers never share a context.

On launch, when the layer sets `astro`, `mi6`:

1. Creates the `astro/` directory in the set if it is missing.
2. If no login exists there, prints `astro login` as the next step and
   continues. The first launch in a new customer layer is where you log in.
3. If the active organization or workspace in that directory differs from the
   policy, runs `astro organization switch <org> --workspace-id <ws>`.

An organization API token from Bitwarden, exported as `ASTRO_API_TOKEN`, is the
alternative to an interactive login for a layer. The CLI takes the token over
the login context. Use it for a customer organization where a personal login
is not wanted.

Otto's project-level files, `.astro/otto/permissions.json` and
`.astro/otto/extensions.json`, are committed to the repo, so they are not used
for per-layer settings. Otto's user-level `otto/settings.json` lives in
`ASTRO_HOME`, which makes it per layer.

## Machines: config that depends on the hardware

The Mac Studio and the MacBook Pro run the same config repo, but they are not
the same machine. The Studio runs large local models. The laptop cannot, but at
home it can use the Studio's LM Studio server over the LAN. `machines/<name>/`
is a layer for those differences, merged after the domain layers and before the
context. The name comes from `scutil --get LocalHostName`. A machine with no
folder gets no machine layer.

```
machines/
	mac-studio/opencode.json      lmstudio at 127.0.0.1, the large models allowed
	macbook-pro/opencode.json     no local models
contexts/
	home/opencode.json            lmstudio at the Studio's LAN address
```

The laptop at home gets the Studio's models through the `home` context. Away,
it has cloud providers only. Whether the laptop roams is not a machine setting:
the `home` context probe answers that per launch.

## Keeping two machines in sync

Sync the source through git, rebuild what is derived on each machine, and never
file-sync the derived state.

| Thing | Lives in | Synced by |
|---|---|---|
| Domain, context, machine, and project-override config | this repo | git |
| Skills | this repo or a skill repo | git |
| Built config sets | `~/.agents/` | nothing; `mi6` rebuilds them |
| Secrets and API keys | Bitwarden | the bootstrap's restore step |
| Claude Code and OpenCode logins | Keychain | log in once per account per machine |
| Session history, plugin cache, auto-memory | inside each config set | nothing; per machine |
| Tools and versions | `Brewfile` | `brew bundle` on each machine |

An edit to config is a commit. Change a domain's `AGENTS.md` on the laptop
through the `meta` domain, commit, push. On the Studio, the next `mi6` launch
pulls it. Because the config set links to the file, no rebuild follows.

The pull is the sync. `mi6` runs `git pull --ff-only` on this repo and on each
skill repo the layers use, at most once an hour, and carries on when offline.
If a pull cannot fast-forward, because the same file changed on both machines
without a push in between, `mi6` leaves that repo alone, prints one line naming
it, and launches with what is on disk. Pushing stays a deliberate act.

Day to day:

- **Edit a skill.** It is live on that machine at once, because the set links
  to the checkout. Commit and push when it is right.
- **Add a skill.** Add the folder. The refresh pass links it on the next launch.
- **Remove a skill.** Delete the folder. The dangling link is pruned.
- **Uncommitted edits** stay on the machine that made them. That is git, not a
  gap in the sync.

Do not put `~/.agents/` or `~/.claude/` in iCloud Drive, Dropbox, or
Syncthing. They hold symlink farms and SQLite session databases, and file sync
corrupts both.

Claude Code's auto-memory lives in the config set, so each machine builds its
own. If shared memory turns out to matter, it can move to a private repo that
`mi6` links in. Start without that.

## The `meta` domain

`meta` is an ordinary layer. It holds this repo and the skill repos, and its
`settings.json` grants write permission to `~/.agents/` and `~/.claude/`, which
every other layer denies.

The agent running under `meta` edits the files that define its own config. On
the first machine setup, `setup.sh` builds the sets before any agent runs. If an
edit breaks the `meta` set, `mi6 --no-domain claude` starts without it.

## Bootstrap changes this needs

- `scripts/make-dirs.sh`: add `meta`.
- Move this repo from `personal/new_mac_bootstrap/development-tools-bootstrap`
  to `meta/development-tools-bootstrap`.
- `scripts/claude-env.sh`: replace the `SKILL_SOURCES` symlinking into
  `~/.claude/skills/` with the per-set build. The plugin marketplace and hook
  patch steps move into the build, per set.
- `setup.sh`: install `mi6` on the login-shell `PATH` and run the first build.

## Checked on the new machine before relying on it

- `availableModels` from a user-level `settings.json` constrains `/model` and
  `--model`. The docs describe it under managed settings.
- OpenCode reads skills from `OPENCODE_CONFIG_DIR`. The docs list agents,
  commands, modes, and plugins.
- Where Claude Code stores credentials on macOS when `CLAUDE_CONFIG_DIR` is set.
- Termic's named accounts and `mi6 claude` in the registry work together, or
  the launcher's account handling replaces Termic's.
- The gateway MAC that `arp` reports on the client VLAN is the UDM-Pro system
  MAC `68:d7:9a:21:c1:9a`. A UDM can present a different MAC per VLAN.
- Teleport's interface on macOS is `utun*` and carries a route to
  `10.100.20.0/24` while connected.
- OpenCode has a per-prompt hook that can add context, for the network refresh.
- `ASTRO_HOME` moves the whole `.astro/` directory, including Otto's settings
  and sessions, and `astro otto` sets `ASTRO_ORGANIZATION` from the login in
  that directory. The variable is in `config/config.go` in `astronomer/astro-cli`
  and not in the docs.
