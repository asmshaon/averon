#!/usr/bin/env bash
# Simulate an inference-process crash (SIGKILL of the server, not `docker kill`, which Docker
# treats as a manual stop and does not restart). Then wait until the service is healthy again.
# Usage: ./crash-service.sh whisper|llama [max_wait_seconds]
set -euo pipefail
cd "$(dirname "$0")"
# ENV_FILE overrides deploy/.env (e.g. for a local smoke stack).
compose() { if [ -n "${ENV_FILE:-}" ]; then docker compose --env-file "$ENV_FILE" "$@"; else docker compose "$@"; fi; }
svc="${1:?service name: whisper or llama}"
max="${2:-300}"
cid="$(compose ps -q "$svc")"
before="$(docker inspect -f '{{.RestartCount}}' "$cid")"
start=$(date +%s)
# `sh -c` so the shell builtin kill is used (slim images may lack /bin/kill).
docker exec "$cid" sh -c 'kill -9 -1' || true
sleep 2
while :; do
  state="$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null || echo gone)"
  [[ "$state" == "running/healthy" ]] && break
  (( $(date +%s) - start > max )) && { echo "service=$svc result=not_recovered state=$state"; exit 1; }
  sleep 2
done
after="$(docker inspect -f '{{.RestartCount}}' "$cid")"
if (( after <= before )); then echo "service=$svc result=not_crashed restarts=$after"; exit 1; fi
echo "service=$svc result=recovered restarts_before=$before restarts_after=$after seconds_to_healthy=$(( $(date +%s) - start ))"
