
# Oracle A1 Always Free Provisioner

Provide a guided, auditable setup; do not assume direct cloud access. Scripts are bundled in `scripts/`, a configurable JSON template in `assets/`, detailed workflows in `references/`. Target **A1 Flex, 2 OCPU, 12 GB, 100 GB boot**. This is a deployment target, not a guarantee of zero billing or host availability.

## Non-negotiable safeguards

1. Verify *current* OCI Free Tier limits, home-region eligibility, per-tenancy A1 utilization and storage, backups, billing status, and available quota from Oracle official docs and user account. Never infer free compute eligibility from a non-null quota. A1 service quotas can exceed Always Free allocation. Confirm whether the account is Free Tier or PAYG; get explicit user approval before any possible cost exposure.
2. Treat server modifications, IAM grants, subnet changes, VM creation and firewall changes as gated actions. Explain precise impact and obtain authorization; never automate an unreviewed potentially paid launch. **Never delete or restart an existing n8n/PG/OmniRoute/Caddy deployment.**
3. Avoid private credentials in conversation, scripts, logs, or skill assets. SSH *public* keys only. Create a **new** SSH key if necessary; validate new-key login before disabling passwords. Store Telegram token in a permission-600 env file, not JSON or a command visible in shell history. Rotate leaked tokens.
4. The launcher defaults to **dry-run**; `--launch` submits a real cloud request. Treat any ambiguous API response as pending/manual reconciliation. A confirmed out-of-host-capacity error is eligible for retry. Existing A1 instances, nonempty success marker, or unresolved pending request must block new launches.
5. Check ALL compartments/ADs, volume backups, and account usage first. The bundled runtime check covers the selected compartment/AD plus block volumes, **not the whole tenancy**. Do not enable `--launch` until broader inventory has been independently verified and recorded.
6. Existing E2 Micro might have <1 GB RAM and heavy swap use. Check `free -h`, `df -h /`, `docker stats --no-stream` before adding Python SDK; never install large continuously running monitoring containers. Prefer short systemd oneshots with `Nice=10`.
7. If a capacity shortage persists, explain it cannot be bypassed. Never promise timing or automatic completion in the current ChatGPT conversation. The **user-owned** E2 systemd timer performs future checks independently after setup.

## Decision workflow

1. Ask for current/new account and existing E2 availability only if not already known. If existing E2 is present, follow `references/existing-e2.md`. Otherwise follow `references/fresh-account.md` to establish a safe watcher host or alternative existing Linux host with approved auth. Do not claim an Always Free E2 VM will necessarily be available.
2. Run read-only discovery first: account plan, home region, compartments, shapes/limits, A1 instances, boot and block volumes, backups, images, ADs, networking and SSH ingress. The A1 deployment consumes 2 OCPU/12 GB toward account-wide limits and targets a 100 GB boot volume. Verify effective free allowance and exact root/child resources.
3. Set up OCI **instance principal** dynamic group matched to the exact E2 instance ID and IAM permissions scoped as narrowly as practicable (prefer dedicated compartment). Verify `get_instance`/list before provisioning. A function targeted by OCI Resource Scheduler with `START_RESOURCE` is **not** a supported invoke mechanism; use systemd timer instead. Deactivate failed schedule safely if explicitly approved.
4. Choose a currently available ARM64 Ubuntu 24.04 non-minimal image compatible with `VM.Standard.A1.Flex`, and public subnet (public IP allowed, approved SSH ingress), and trusted public key.
5. Place `scripts/a1_launcher.py`, `assets/config.example.json` customized to the tenancy, and public key in `/home/ubuntu`. Create isolated venv `python3 -m venv ~/a1-watcher-env`; install `oci` into venv. Never modify system Python or existing containers.
6. `python ~/a1_launcher.py --config ~/a1-config.json` must pass in dry-run. `scripts/install_timer.sh` installs a **dry-run hourly** systemd timer; verify journal and scheduling. For real provisioning only after approval and account-wide audit, stop timer, edit service `ExecStart` to append `--launch`, `systemctl daemon-reload`, run a single controlled attempt, inspect logs/status/markers, then start timer when safe. Do not overlook timer activation.
7. On accepted launch, rely on later hourly polling to detect `RUNNING` and deliver Telegram notification. On capacity error, keep retrying hourly. On ambiguity or other errors, stop/hold and reconcile from OCI Console before clearing pending marker. Never clear markers without inspection.
8. After A1 is `RUNNING`, verify public IP, SSH key login, OS architecture and boot size, update security packages on **new A1 only**, apply `scripts/harden_ssh.sh` after confirming key access, verify `sshd -t` and separate session, then review OS firewall carefully. Note OCI VCN security lists may permit HTTP/HTTPS even when server firewall blocks them; restrict at source as needed without breaking E2 services.
9. Deliver a deployment report: tenancy and region (no credentials), shape, OCPU/RAM, boot volume, assigned IP, SSH command, quota/free-tier assumptions, A1 instance OCID, watcher logs/next run, notification status, risks and verification proof. Do not claim deployed until OCI shows `RUNNING` and user validates SSH.

## Scripts

- `scripts/a1_launcher.py`: idempotent conservative capacity launcher with dry-run, instance-principal auth, lock, request-token/pending reconciliation, volume guard, optional Telegram, CLI exit codes. Depends on `oci` Python package; fully parametric except intentional fixed shape/resources.
- `scripts/install_timer.sh`: creates an hourly systemd unit in dry-run mode. Expects launcher/config under `/home/ubuntu`; review after setup.
- `scripts/harden_ssh.sh`: changes SSH settings on **new A1 only**, refuses if `authorized_keys` absent.
- `assets/config.example.json`: replace placeholders locally. Never bundle live OCIDs, bot tokens, private keys, or user addresses in the distributable skill.

## Tests and limitations

Run `python -m unittest discover -s tests -v` when updating. Unit tests mock OCI to verify dry-run, capacity retries, ambiguous errors and duplicate guards; **no real OCI provisioning is performed by tests**. Always verify live SDK signature with named `availability_domain=` and `compartment_id=`. Current availability of shapes, quotas, OCI policies and pricing is subject to change: confirm official docs each deployment.
