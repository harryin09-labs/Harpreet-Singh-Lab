# Common failure signatures and remedies

- `NotAuthorizedOrNotFound` on an existing Compute OCID: instance principal may authenticate but lack appropriate dynamic-group IAM policies. Inspect exact membership and policy statements; allow propagation and retest.
- `Out of host capacity` (often HTTP 500): genuine A1 host capacity shortage. Retain no pending marker only when response is explicit. Retry by systemd timer. Quota availability ≠ physical capacity.
- `list_boot_volumes() takes 1 positional argument but 3 were given`: OCI Python SDK uses named `availability_domain=` and `compartment_id=`.
- OCI Resource Scheduler `START_RESOURCE` targeting `fnfunc` with repeated FAILED work requests: it does not invoke Function code; choose systemd watcher or a supported function triggering mechanism.
- `pending.json` exists: possible accepted/lost launch response. Investigate Console and OCI APIs carefully. Do not silently auto-clear after a fixed timeout.
- `success.txt` exists but no A1 visible: fail closed; investigate deletion, region mismatch, access, and consistency.
- `a1-notified` missing: Telegram delivery may retry; no Telegram secret in logs. Any HTTP exception can contain credential-bearing URL; print only exception type.
- `systemctl show` pager stuck `lines ... (END)`: press `q`, use `--no-pager`.
- Cloud Shell SSH private key missing: run SSH from machine storing the key; do not paste private key in chat.
- `Subscription: null` from `oci iam tenancy get`: not proof of Free/PAYG; verify account plan in Console.
- Public SSH rule 0.0.0.0/0: operationally possible but riskier than a trusted-IP CIDR; narrow when safely possible.
- Unhealthy 1GB E2: swap use, OOM or disk exhaustion can affect n8n; limit watcher frequency, use one-shot, and audit resources.
