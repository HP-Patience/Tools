#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root=/home/work/apps/ai-subscriptions
exec 8>"$root/run/maintenance.lock"
flock -n 8 || exit 0
set -a
source "$root/shared/app.env"
source "$root/current/release.env"
set +a
cd "$root/current/backend"
case "${1:-}" in
  reminders) exec "$root/current/.venv/bin/python" -m app.cli run-reminders ;;
  backup) exec "$root/current/.venv/bin/python" "$root/current/ops/backup.py" "$APP_DATABASE_PATH" "$root/shared/backups" ;;
  *) exit 2 ;;
esac
