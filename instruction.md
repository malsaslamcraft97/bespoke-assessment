# Stand up a Postgres-backed probe API

On a fresh Linux host, use Ansible to install Docker. Then bring up a docker-compose stack with PostgreSQL on port 5432 and a NestJS API on port 8080. The API must expose GET /checkdb returning HTTP 200 with the result of a real SELECT 1 query against Postgres.
