#!/bin/sh
# Nightly copy of the database, and of media once there is any, kept 30
# days, run by hr-backup.service as the practice-hr user. Each copy is
# complete — password hashes, and session keys that work as login cookies —
# so it is written readable by nobody else (umask 077) into the app's own
# state directory, which is closed too. systemd sets STATE_DIRECTORY from
# the unit's StateDirectory=.
set -eu
umask 077
state="${STATE_DIRECTORY:-/var/lib/practice-hr}"
mkdir -p "$state/backups"
sqlite3 "$state/db.sqlite3" ".backup '$state/backups/db-$(date +%F).sqlite3'"
# MEDIA_ROOT (the payroll reports) is $state/media in production. Nothing
# creates it until the first report is generated, so skip the archive
# rather than fail the whole backup before then.
if [ -d "$state/media" ]; then
    tar -czf "$state/backups/media-$(date +%F).tgz" -C "$state" media
fi
find "$state/backups" -name 'db-*.sqlite3' -mtime +30 -delete
find "$state/backups" -name 'media-*.tgz' -mtime +30 -delete
