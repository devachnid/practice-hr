#!/bin/sh
# Nightly copy of the database, and of media once there is any, kept 30
# days, run by hr-backup.service as the practice-hr user. Each copy is
# complete — password hashes, and session keys that work as login cookies —
# so it is written readable by nobody else (umask 077) into the app's own
# directory, which is closed to everyone else.
set -eu
umask 077
root=/srv/practice-hr
mkdir -p "$root/backups"
sqlite3 "$root/db.sqlite3" ".backup '$root/backups/db-$(date +%F).sqlite3'"
# There is no media root yet (plan 3 adds one); skip the archive rather
# than fail the whole backup until then.
if [ -d "$root/media" ]; then
    tar -czf "$root/backups/media-$(date +%F).tgz" -C "$root" media
fi
find "$root/backups" -name 'db-*.sqlite3' -mtime +30 -delete
find "$root/backups" -name 'media-*.tgz' -mtime +30 -delete
