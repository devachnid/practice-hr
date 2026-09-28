#!/bin/sh
set -eu
mkdir -p /root/practice-hr/backups
sqlite3 /root/practice-hr/db.sqlite3 ".backup /root/practice-hr/backups/db-$(date +%F).sqlite3"
tar -czf "/root/practice-hr/backups/media-$(date +%F).tgz" -C /root/practice-hr media
find /root/practice-hr/backups -name 'db-*.sqlite3' -mtime +30 -delete
find /root/practice-hr/backups -name 'media-*.tgz' -mtime +30 -delete
