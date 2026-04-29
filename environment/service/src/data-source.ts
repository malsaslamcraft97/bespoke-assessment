import { TypeOrmModuleOptions } from "@nestjs/typeorm";

/**
 * TypeORM configuration for the probe API.
 *
 * Connection parameters are read from the environment so that the surrounding
 * deployment (docker-compose) controls them. Defaults assume the Postgres
 * service is reachable as `postgres` on port 5432.
 *
 * `retryAttempts: 0` is intentional: this service expects its database to be
 * ready before it starts. If the connection cannot be established on the first
 * attempt, the application will fail to bootstrap and the process will exit.
 */
export const dataSourceOptions: TypeOrmModuleOptions = {
  type: "postgres",
  host: process.env.POSTGRES_HOST || "postgres",
  port: parseInt(process.env.POSTGRES_PORT || "5432", 10),
  username: process.env.POSTGRES_USER || "postgres",
  password: process.env.POSTGRES_PASSWORD || "postgres",
  database: process.env.POSTGRES_DB || "checkdb",
  retryAttempts: 0,
  synchronize: false,
  logging: ["error"],
};
