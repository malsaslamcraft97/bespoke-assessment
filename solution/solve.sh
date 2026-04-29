#!/usr/bin/env bash

# Solution for INCUBYTE/hard-devops-task.
#
# Runs from /solution at task time. 
# 1. Installs Ansible, then runs the
# 2. reference playbook which (a) installs Docker Engine + Compose plugin,
# (b) generates the NestJS source tree at /app/service/, and (c) writes
# /app/docker-compose.yml. 
# Finally brings up the stack and waits for /checkdb to respond with HTTP 200.
#
# This script must succeed deterministically; the verifier uses its
# success as the signal that the task is solvable.

set -euo pipefail

log() { echo "[oracle $(date -u +%H:%M:%S)] $*"; }

TARGET=/app

# 1. Install Ansible. The Main container intentionally ships without it, 
# hence agent task starts from clean Ubuntu base
log "Installing Ansible"
apt-get update -qq
apt-get install -y --no-install-recommends ansible

cd "${TARGET}"

# 2. Run the Ansible playbook locally. Installs Docker,
# generates NestJS app, writes compose file
log "Running Ansible playbook"
ansible-playbook -i 'localhost,' -c local /solution/playbook.yml

# 3. Sanity-check the Docker daemon before we try to use it.
log "Verifying Docker daemon"
docker info > /dev/null

# 4. Bring up the stack. --build rebuilds the NestJS image from
# /app/service/ (which was playbook generated). 
# Postgres is pulled from Docker Hub.
log "Building and starting the docker compose stack"

# Pre-emptive cleanup: remove any leftover containers from previous trial runs
log "Cleaning up any leftover stack from previous trials"
docker compose -f /app/docker-compose.yml down -v --remove-orphans 2>/dev/null || true

# Catch anything that escaped the project (different project name, etc.)
docker ps -aq --filter "publish=5432" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
docker ps -aq --filter "publish=8080" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true

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