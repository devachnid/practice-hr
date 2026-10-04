#!/bin/sh
# Push the nightly database copy to the Proxmox Backup Server, run by
# hr-pbs.service as the practice-hr user straight after hr-backup.service.
# It sends the finished copies in $state/backups (the database and the
# payroll-report archive), never the live WAL database. The repository,
# token and fingerprint arrive as PBS_* variables from
# /etc/pbs-backup/practice-hr.env, which systemd reads as root; the
# encryption key arrives as a credential. So neither is ever readable by the
# practice-hr user or by the web process. The copy is encrypted here: the
# server holds no plaintext.
set -eu
state="${STATE_DIRECTORY:-/var/lib/practice-hr}"
exec proxmox-backup-client backup "data.pxar:$state/backups" \
    --ns practice-hr --backup-id practice-hr \
    --keyfile "${CREDENTIALS_DIRECTORY:?run this under hr-pbs.service}/pbs.key"
