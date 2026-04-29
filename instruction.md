# Stand up a Postgres-backed probe API

Bring up a small backend service that proves a database connection is live,
using Ansible to provision the host and Docker Compose to run the stack.

## Requirements

- Install Docker Engine and the Docker Compose plugin with an Ansible playbook.
- Run a Docker Compose stack with two services:
  - **PostgreSQL 16** listening on host port `5432`.
  - A **NestJS** HTTP API listening on host port `8080`.
- `GET /checkdb` on the NestJS service must return HTTP `200` with a JSON body
  that contains the result of a real `SELECT 1` executed against Postgres.
- The endpoint must remain reachable through redeployments — taking the stack
  down (including volumes) and bringing it back up should still produce a
  working `/checkdb`.

## Provided

A NestJS application skeleton is at `/app/service/`. Build and run it as-is —
do not modify its source, its configuration, or its Dockerfile.

## Your output

Place your playbook, your compose file, and any supporting files under `/app/`.
How you organize them is up to you.
