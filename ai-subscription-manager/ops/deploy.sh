#!/usr/bin/env bash
set -Eeuo pipefail
umask 027
sha="${1:?commit SHA required}"
archive="${2:?archive path required}"
[[ "$sha" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid commit SHA'; exit 2; }
root=/srv/ai-subscriptions
shared="$root/shared"
release="$root/releases/$sha"
[[ "$archive" == "$root/incoming/$sha.tar.gz" ]] || { echo 'Invalid archive path'; exit 2; }
exec 9>"$root/deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
[[ -f "$shared/app.env" ]] || { echo 'Provision shared/app.env first'; exit 1; }
if [[ -L "$root/current" && "$root/current" -ef "$release" ]]; then
  curl --fail --silent http://127.0.0.1:8000/health/ | python3.12 -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get("status")=="ok" and d.get("release")==sys.argv[1] else 1)' "$sha"
  echo 'Same healthy release already active; no files or data changed.'
  exit 0
fi
mkdir -p "$release"
tar -xzf "$archive" -C "$release"
python3.12 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --quiet -r "$release/backend/requirements.lock"
printf 'APP_RELEASE_SHA=%s\n' "$sha" > "$release/release.env"
set -a
source "$shared/app.env"
source "$release/release.env"
set +a
[[ "${APP_DATABASE_PATH:-}" == "$shared/subscriptions.db" ]] || { echo 'Invalid shared database path'; exit 1; }
sudo systemctl stop ai-subscriptions-reminders.timer ai-subscriptions-backup.timer
sudo systemctl stop ai-subscriptions-reminders.service ai-subscriptions-backup.service
sudo systemctl stop ai-subscriptions.service
if [[ -f "$APP_DATABASE_PATH" ]]; then
  "$release/.venv/bin/python" "$release/ops/backup.py" "$APP_DATABASE_PATH" "$shared/backups"
fi
cd "$release/backend"
"$release/.venv/bin/alembic" upgrade head
# Python replaces only the named symlink; never recursively moves a release.
"$release/.venv/bin/python" "$release/ops/activate.py" "$root" "$sha"
sudo systemctl start ai-subscriptions.service
healthy=0
for attempt in {1..15}; do
  if curl --fail --silent http://127.0.0.1:8000/health/ | "$release/.venv/bin/python" -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get("status")=="ok" and d.get("release")==sys.argv[1] else 1)' "$sha"; then healthy=1; break; fi
  sleep 1
done
if [[ "$healthy" != 1 ]]; then
  sudo systemctl stop ai-subscriptions.service
  echo 'Health check failed. Keep writers stopped and inspect migration and backup.'
  exit 1
fi
sudo systemctl start ai-subscriptions-reminders.timer ai-subscriptions-backup.timer
echo "Deployment healthy: $sha"
