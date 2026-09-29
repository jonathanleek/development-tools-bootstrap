# Rules for ~/Documents/git

## Folder layout
One folder per org; repos go inside, named in kebab-case. Every folder has a
`.mi6/` layer for the agent config of the repos below it.

- `personal/` — personal projects and vaults
- `astronomer/` — work
  - `internal/` — internal Astronomer work
  - `tools/` — Astronomer product tooling (e.g. astro-agent, terraform-provider-astro)
  - `examples/` — demos and example repos
  - `customers/<customer>/` — customer-specific repos
- `westbound-workshop/` — workshop / maker projects
- `apache/` — Apache projects (Airflow)
- `arch-reactor/` — Arch Reactor makerspace
- `openstl/` — OpenSTL civic projects

New folders are added in `scripts/make-dirs.sh` in
`personal/development-tools-bootstrap`, which creates them and their layers.
