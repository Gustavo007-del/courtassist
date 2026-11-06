#!/usr/bin/env bash
set -euo pipefail
umask 077
: "${PGSERVICE:?set a pg_service.conf entry for the source database}"
: "${BACKUP_DIRECTORY:?set a private backup directory}"
: "${AGE_RECIPIENT:?set the public backup encryption recipient}"
mkdir -p -- "$BACKUP_DIRECTORY"
target="$BACKUP_DIRECTORY/courtassist-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
work=$(mktemp -d)
trap 'rm -f -- "$work/database.dump" "$work/database.dump.age"; rmdir -- "$work"' EXIT
pg_dump --format=custom --no-owner --no-privileges --file="$work/database.dump"
pg_restore --list "$work/database.dump" >/dev/null
age --recipient "$AGE_RECIPIENT" --output "$work/database.dump.age" "$work/database.dump"
install -m 0600 -- "$work/database.dump.age" "$target.partial"
mv -- "$target.partial" "$target"

