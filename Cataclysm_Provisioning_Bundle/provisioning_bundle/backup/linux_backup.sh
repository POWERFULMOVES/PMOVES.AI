#!/usr/bin/env bash
# backup/linux_backup.sh
# Requires restic. Adjust repo/password.
export RESTIC_REPOSITORY=/mnt/backup/restic-repo
export RESTIC_PASSWORD='ChangeThisPassword'
restic init --repo "$RESTIC_REPOSITORY" || true
restic backup -v /home /srv/stacks
restic snapshots
