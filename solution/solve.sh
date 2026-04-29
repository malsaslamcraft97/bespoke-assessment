#!/usr/bin/env bash
#
# Oracle solution for INCUBYTE/hard-devops-task.
#
# Runs from /solution at task time. Stages a playbook and a compose file
# into /app, runs the playbook to install Docker, then brings up the
# Postgres + NestJS stack and waits for /checkdb to respond with HTTP 200.
#
# This script must succeed deterministically; the verifier uses its
# success as the signal that the task is solvable.

set -euo pipefail

log() { echo "[oracle $(date -u +%H:%M:%S)] $*"; }

TARGET=/app

# 1. Stage our reference playbook and compose file alongside the provided
#    NestJS skeleton at /app/service/.
log "Staging playbook and compose file into ${TARGET}"
cp /solution/playbook.yml "${TARGET}/playbook.yml"
cp /solution/docker-compose.yml "${TARGET}/docker-compose.yml"

cd "${TARGET}"

# 2. Run the Ansible playbook locally. Installs Docker Engine + Compose
#    plugin and starts the daemon.
log "Running Ansible playbook"
ansible-playbook -i 'localhost,' -c local playbook.yml

# 3. Sanity-check the Docker daemon before we try to use it.
log "Verifying Docker daemon"
docker info > /dev/null

# 4. Bring up the stack. --build rebuilds the NestJS image from
#    /app/service/. Postgres is pulled from Docker Hub.
log "Building and starting the docker compose stack"
docker compose up -d --build

# 5. Poll /checkdb until it returns 200 or we hit the deadline. The first
#    cold start can take a while (image build + Postgres init), so we
#    allow a generous 180s.
log "Waiting for /checkdb to return 200"
DEADLINE=$(( $(date +%s) + 180 ))
last_code="none"
while true; do
    last_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:8080/checkdb" || echo "fail")
    if [ "${last_code}" = "200" ]; then
        log "/checkdb returned 200 — oracle complete"
        exit 0
    fi
    if [ "$(date +%s)" -ge "${DEADLINE}" ]; then
        log "Timed out waiting for /checkdb (last status: ${last_code})"
        log "--- docker ps -a ---"
        docker ps -a || true
        log "--- nestjs logs ---"
        docker compose logs --tail=80 nestjs || true
        log "--- postgres logs ---"
        docker compose logs --tail=80 postgres || true
        exit 1
    fi
    sleep 2
done