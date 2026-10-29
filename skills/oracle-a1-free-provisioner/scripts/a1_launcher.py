#!/usr/bin/env python3
"""OCI A1 Always Free launcher. Default: audit only; --launch explicitly submits.

Requires `pip install oci`, OCI instance-principal IAM permissions, and a JSON config.
"""
import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request
import uuid

log = logging.getLogger('oracle-a1')
ACTIVE = {'CREATING', 'PROVISIONING', 'STARTING', 'RUNNING', 'STOPPING', 'STOPPED', 'MOVING', 'UPDATING'}
IGNORED = {'TERMINATING', 'TERMINATED'}


def read_config(path):
    c = json.loads(Path(path).read_text())
    mandatory = ('region','compartment_id','availability_domain','image_id','subnet_id','ssh_public_key_file','instance_name')
    for field in mandatory:
        if not isinstance(c.get(field), str) or not c[field].strip():
            raise ValueError('Missing/invalid config field: ' + field)
    if c.get('shape') != 'VM.Standard.A1.Flex' or c.get('ocpus') != 2 or c.get('memory_gbs') != 12 or c.get('boot_volume_gbs') != 100:
        raise ValueError('Fail-closed: expected A1.Flex 2 OCPU, 12 GB RAM, 100 GB boot')
    if c.get('total_storage_limit_gbs', 200) != 200:
        raise ValueError('Storage limit must be 200 GB')
    if c.get('region') not in c['image_id'] or c['region'] not in c['subnet_id']:
        raise ValueError('Image/subnet do not match selected region')
    public_key = Path(c['ssh_public_key_file']).read_text().strip()
    if len(public_key.split()) < 2 or public_key.split()[0] not in ('ssh-rsa','ssh-ed25519','ecdsa-sha2-nistp256'):
        raise ValueError('Invalid SSH public key')
    c['ssh_key'] = public_key
    return c


def notify(cfg, message):
    path = cfg.get('telegram_env_file')
    if not path:
        log.info('Telegram not configured; check status manually')
        return False
    try:
        values = dict(line.split('=',1) for line in Path(path).read_text().splitlines() if '=' in line)
        token = values['TELEGRAM_BOT_TOKEN'].strip()
        chat = values['TELEGRAM_CHAT_ID'].strip()
        if not token or not chat:
            raise ValueError('Empty Telegram credentials')
        data = urllib.parse.urlencode({'chat_id':chat, 'text':message}).encode()
        req = urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage', data=data, method='POST')
        with urllib.request.urlopen(req, timeout=15) as response:
            return bool(json.loads(response.read()).get('ok'))
    except Exception as exc:
        # Never log exception text: URLs may include bot tokens.
        log.warning('Telegram failed: %s', type(exc).__name__)
        return False


def is_capacity_error(exc):
    # Explicit, known negative response only; unknown failures are ambiguous.
    return (getattr(exc, 'status', None) in (400,409,500)
            and any(term in str(getattr(exc,'message','')).lower()
                    for term in ('out of host capacity', 'out of capacity', 'outofhostcapacity')))


def storage_used(block, oci, compartment, ad):
    # One AD for A1 target; caller separately verifies tenancy-wide storage inventory.
    boots = oci.pagination.list_call_get_all_results(block.list_boot_volumes,
        availability_domain=ad, compartment_id=compartment).data
    vols = oci.pagination.list_call_get_all_results(block.list_volumes,
        compartment_id=compartment).data
    active = lambda item: item.lifecycle_state not in IGNORED
    return sum((v.size_in_gbs or 0) for v in boots if active(v)) + sum((v.size_in_gbs or 0) for v in vols if active(v))


def execute(cfg, state, launch=False, oci_module=None):
    if oci_module is None:
        import oci as oci_module
    oci = oci_module
    state.mkdir(parents=True, exist_ok=True)
    pending, success, notified = [state / x for x in ('pending.json','success.txt','notified.txt')]
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    compute = oci.core.ComputeClient({'region': cfg['region']}, signer=signer)
    existing = oci.pagination.list_call_get_all_results(compute.list_instances,
        compartment_id=cfg['compartment_id']).data
    a1 = [x for x in existing if x.shape == cfg['shape'] and x.lifecycle_state not in IGNORED]
    if a1:
        for x in a1:
            log.info('Existing A1: %s %s %s', x.display_name, x.lifecycle_state, x.id)
        target = next((x for x in a1 if x.display_name == cfg['instance_name'] and x.lifecycle_state == 'RUNNING'), None)
        if target:
            success.write_text(target.id+'\n')
            success.chmod(0o600)
            pending.unlink(missing_ok=True)
            if not notified.exists() and notify(cfg, 'Oracle A1 RUNNING\nName: '+target.display_name+'\nOCID: '+target.id+'\n2 OCPU / 12 GB / 100 GB'):
                notified.write_text(target.id+'\n')
                notified.chmod(0o600)
            log.info('SUCCESS: target A1 is running')
        else:
            log.info('HOLD: another A1 exists; inspect before attempting again')
        return 'existing'
    if success.exists():
        log.warning('SUCCESS MARKER EXISTS but no A1 seen; fail closed for manual review')
        return 'hold'
    if pending.exists():
        log.warning('PENDING LAUNCH; no A1 visible; fail closed for manual reconciliation')
        return 'hold'
    log.info('TARGET: %s / 2 OCPU / 12 GB / 100 GB',cfg['instance_name'])
    if not launch:
        log.info('DRY RUN PASS; launch API not called')
        return 'dry-run'
    # Production only: independently audit ALL compartments, volumes, backups, quotas,
    # free eligibility and account usage before enabling the launcher (see SKILL.md).
    block = oci.core.BlockstorageClient({'region':cfg['region']}, signer=signer)
    consumed = storage_used(block, oci, cfg['compartment_id'], cfg['availability_domain'])
    if consumed + 100 > 200:
        raise RuntimeError('Storage protection: root compartment allocation would exceed 200 GB')
    log.info('Root compartment storage %s GB; planned total %s GB',consumed,consumed+100)
    details = oci.core.models.LaunchInstanceDetails(
        compartment_id=cfg['compartment_id'], availability_domain=cfg['availability_domain'],
        display_name=cfg['instance_name'], shape=cfg['shape'],
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=2, memory_in_gbs=12),
        source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=cfg['image_id'],boot_volume_size_in_gbs=100),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=cfg['subnet_id'], assign_public_ip=True),
        metadata={'ssh_authorized_keys':cfg['ssh_key']},
        freeform_tags={'managed-by':'oracle-a1-free-provisioner'})
    token = str(uuid.uuid4())
    # Persist intent before API submission; if connection drops, do NOT blindly retry.
    pending.write_text(json.dumps({'opc_retry_token':token,'instance_name':cfg['instance_name']})+'\n')
    pending.chmod(0o600)
    try:
        response = compute.launch_instance(details, opc_retry_token=token,
            retry_strategy=oci.retry.NoneRetryStrategy())
    except oci.exceptions.ServiceError as exc:
        if is_capacity_error(exc):
            pending.unlink(missing_ok=True)
            log.warning('Out of host capacity; can retry on next timer run')
            return 'capacity'
        log.error('OCI launch failure: HTTP %s code=%s; pending marker retained',exc.status,exc.code)
        return 'hold'
    except Exception:
        log.exception('Ambiguous launch outcome: pending marker retained')
        return 'hold'
    log.info('LAUNCH ACCEPTED: %s state=%s; next run will confirm RUNNING',response.data.id,response.data.lifecycle_state)
    return 'accepted'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--state-dir', default=str(Path.home()/'.oracle-a1-provisioner'))
    p.add_argument('--launch', action='store_true', help='Submit real OCI launch request')
    args=p.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    state=Path(args.state_dir).expanduser()
    state.mkdir(parents=True,exist_ok=True)
    os.chmod(state,0o700)
    with (state/'lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            log.info('Another run is active; skipping')
            return
        try: result=execute(read_config(args.config),state,launch=args.launch)
        except Exception:
            log.exception('Preflight / runtime error; no automatic recovery')
            sys.exit(1)
        log.info('RESULT: %s',result)
        if result == 'hold': sys.exit(2)

if __name__=='__main__':
    main()
