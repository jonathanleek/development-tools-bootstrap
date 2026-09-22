#!/bin/zsh
# Restore secrets from the Bitwarden "Mac Migration" folder to their real paths,
# with correct permissions. Run on the NEW machine. No secret value is printed.
#
# STEP 1 — unlock in this terminal:
#     export BW_SESSION="$(bw unlock --raw)"     # run `bw login` first if needed
# STEP 2 — run this script.
#
# Won't overwrite an existing non-empty file (skips it).
#
# Standalone counterpart to scripts/restore-secrets.sh: that one runs during
# bootstrap and executes whatever the Bitwarden note `restore-script` contains,
# whereas this holds the explicit item -> path -> mode map. Populate the vault
# first with scripts/backup-secrets-to-bw.sh.
set -euo pipefail

command -v bw >/dev/null || { echo "install first: brew install bitwarden-cli"; exit 1; }
if [ -z "${BW_SESSION:-}" ]; then
  echo 'Unlock first:  export BW_SESSION="$(bw unlock --raw)"'
  exit 1
fi
bws() { bw --session "$BW_SESSION" "$@"; }
bws sync >/dev/null 2>&1 || { echo "BW_SESSION invalid — re-run the export"; exit 1; }

# "bitwarden item name | path relative to $HOME | chmod mode"
MAP=(
  "ssh/id_ed25519|.ssh/id_ed25519|600"
  "ssh/homelab_ansible|.ssh/homelab_ansible|600"
  "ssh/airflow_deploy_key|.ssh/airflow_deploy_key|600"
  "ssh/config|.ssh/config|600"
  "ssh/conductor_config|.ssh/conductor_config|600"
  "ssh/id_ed25519.pub|.ssh/id_ed25519.pub|644"
  "ssh/homelab_ansible.pub|.ssh/homelab_ansible.pub|644"
  "ssh/airflow_deploy_key.pub|.ssh/airflow_deploy_key.pub|644"
  "aws/config|.aws/config|600"
  "gh/hosts.yml|.config/gh/hosts.yml|600"
  "docker/config.json|.docker/config.json|600"
  ".leek-homelab-secrets/terraform/proxmox/terraform.tfvars|.leek-homelab-secrets/terraform/proxmox/terraform.tfvars|600"
  ".leek-homelab-secrets/terraform/unifi/terraform.tfvars|.leek-homelab-secrets/terraform/unifi/terraform.tfvars|600"
  ".leek-homelab-secrets/ansible/vars/secrets.yml|.leek-homelab-secrets/ansible/vars/secrets.yml|600"
)

restore() {
  local item="$1" rel="$2" mode="$3" dest="$HOME/$2"
  if [ -s "$dest" ]; then echo "exists, skip: $rel"; return 0; fi
  mkdir -p "${dest:h}"
  if bws get notes "$item" > "$dest" 2>/dev/null && [ -s "$dest" ]; then
    chmod "$mode" "$dest"
    echo "restored: $rel ($mode)"
  else
    rm -f "$dest"
    echo "MISSING in vault: $item"
  fi
}

for entry in $MAP; do
  rest="${entry#*|}"
  restore "${entry%%|*}" "${rest%%|*}" "${rest#*|}"
done

[ -d "$HOME/.ssh" ] && chmod 700 "$HOME/.ssh"
echo ""
echo "Done. Reminders NOT in Bitwarden: Terraform .tfstate files, WireGuard tunnels,"
echo "and the rotated Anthropic API key — restore/re-add those manually."
