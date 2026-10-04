#!/bin/sh
# Push the nightly database copy to the Proxmox Backup Server, run by
# hr-pbs.service as the practice-hr user straight after hr-backup.service.
# It sends the finished copies in $state/backups (the database and the
# payroll-report archive), never the live WAL database. The repository
# address and certificate fingerprint (not secrets) arrive as PBS_* variables from
# /etc/pbs-backup/practice-hr.env. The API token and the encryption key are
# systemd credentials, passed by file: a token in the environment would be
# readable from /proc by any other process running as practice-hr, such as
# the web service. The copy is encrypted here: the server holds no plaintext.
set -eu
state="${STATE_DIRECTORY:-/var/lib/practice-hr}"
creds="${CREDENTIALS_DIRECTORY:?run this under hr-pbs.service}"
export PBS_PASSWORD_FILE="$creds/pbs.token"
exec proxmox-backup-client backup "data.pxar:$state/backups" \
    --ns practice-hr --backup-id practice-hr \
    --keyfile "$creds/pbs.key"
