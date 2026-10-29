#!/usr/bin/env bash
set -euo pipefail
# Install in dry-run mode; enabling live launches requires explicit post-review edit.
if [[ $# -ne 2 ]]; then echo 'Usage: sudo bash install_timer.sh /absolute/script.py /absolute/config.json' >&2; exit 2; fi
SCRIPT=$(realpath "$1"); CONFIG=$(realpath "$2")
[[ -f "$SCRIPT" && -f "$CONFIG" ]] || { echo 'Missing files' >&2; exit 2; }
[[ $SCRIPT == /home/ubuntu/* && $CONFIG == /home/ubuntu/* ]] || { echo 'Install under /home/ubuntu only' >&2; exit 2; }
cat > /etc/systemd/system/oracle-a1-provisioner.service <<EOF
[Unit]
Description=Oracle A1 Free Provisioner
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/home/ubuntu/a1-watcher-env/bin/python $SCRIPT --config $CONFIG
TimeoutStartSec=180
Nice=10
NoNewPrivileges=true
EOF
cat > /etc/systemd/system/oracle-a1-provisioner.timer <<'EOF'
[Unit]
Description=Check Oracle A1 capacity hourly
[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=60
Unit=oracle-a1-provisioner.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now oracle-a1-provisioner.timer
systemctl cat oracle-a1-provisioner.service --no-pager
printf '\nTimer installed in DRY-RUN mode. Do NOT enable --launch until full audit.\n'
