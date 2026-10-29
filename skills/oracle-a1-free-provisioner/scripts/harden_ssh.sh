#!/usr/bin/env bash
set -euo pipefail
# Must execute locally on NEW A1; never on production E2 without explicit approval.
if [[ $EUID -ne 0 ]]; then echo 'Run with sudo' >&2; exit 1; fi
if [[ ! -f /home/ubuntu/.ssh/authorized_keys || ! -s /home/ubuntu/.ssh/authorized_keys ]]; then
  echo 'No Ubuntu authorized_keys; refusing SSH changes' >&2; exit 1
fi
cat >/etc/ssh/sshd_config.d/90-a1-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
EOF
sshd -t
systemctl reload ssh
printf 'SSH hardening applied; verify separate SSH session before closing current one.\n'
