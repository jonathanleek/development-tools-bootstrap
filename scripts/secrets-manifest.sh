# Secrets kept in the Bitwarden "Mac Migration" folder. Sourced by
# backup-secrets-to-bw.sh and restore-secrets-from-bw.sh — edit only here.
#
# "bitwarden item name | path relative to $HOME | chmod mode | kind"
#   kind = note  file content stored in the Secure Note body (< 9000 bytes)
#   kind = file  file stored as an attachment on a Secure Note (needs Premium)

SECRETS_FOLDER="Mac Migration"

SECRETS=(
  "ssh/id_ed25519|.ssh/id_ed25519|600|note"
  "ssh/id_ed25519.pub|.ssh/id_ed25519.pub|644|note"
  "ssh/homelab_ansible|.ssh/homelab_ansible|600|note"
  "ssh/homelab_ansible.pub|.ssh/homelab_ansible.pub|644|note"
  "ssh/airflow_deploy_key|.ssh/airflow_deploy_key|600|note"
  "ssh/airflow_deploy_key.pub|.ssh/airflow_deploy_key.pub|644|note"
  "ssh/config|.ssh/config|600|note"
  "aws/config|.aws/config|600|note"
  "docker/config.json|.docker/config.json|600|note"
  ".leek-homelab-secrets/terraform/proxmox/terraform.tfvars|.leek-homelab-secrets/terraform/proxmox/terraform.tfvars|600|note"
  ".leek-homelab-secrets/terraform/unifi/terraform.tfvars|.leek-homelab-secrets/terraform/unifi/terraform.tfvars|600|note"
  ".leek-homelab-secrets/ansible/vars/secrets.yml|.leek-homelab-secrets/ansible/vars/secrets.yml|600|note"
  ".leek-homelab-secrets/terraform/proxmox/terraform.tfstate|.leek-homelab-secrets/terraform/proxmox/terraform.tfstate|600|file"
  ".leek-homelab-secrets/terraform/proxmox/terraform.tfstate.backup|.leek-homelab-secrets/terraform/proxmox/terraform.tfstate.backup|600|file"
  ".leek-homelab-secrets/terraform/unifi/terraform.tfstate|.leek-homelab-secrets/terraform/unifi/terraform.tfstate|600|file"
  ".leek-homelab-secrets/terraform/unifi/terraform.tfstate.backup|.leek-homelab-secrets/terraform/unifi/terraform.tfstate.backup|600|file"
  ".leek-homelab-secrets/.claude/settings.local.json|.leek-homelab-secrets/.claude/settings.local.json|600|file"
)
