#!/usr/bin/env bash
set -uo pipefail
umask 077
root=/home/work/apps/ai-subscriptions
exec 9>"$root/run/service.lock"
flock -n 9 || exit 0
printf '%s\n' "$$" > "$root/run/supervisor.pid"
child=''
finish() {
  if [[ -n "$child" ]]; then kill "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi
  exit 0
}
trap finish TERM INT
while true; do
  set -a
  source "$root/shared/app.env"
  source "$root/current/release.env"
  set +a
  cd "$root/current/backend" || exit 1
  "$root/current/.venv/bin/python" -m uvicorn app.main:app --host "${APP_BIND_HOST:-127.0.0.1}" --port 18080 --workers 1 &
  child=$!
  wait "$child" || true
  child=''
  sleep 3
done
