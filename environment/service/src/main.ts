import "reflect-metadata";
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

/**
 * Eager bootstrap.
 *
 * `AppModule` imports `TypeOrmModule.forRoot(...)` which will attempt to
 * connect to Postgres while the module initializes. Because `retryAttempts`
 * is set to 0 in `data-source.ts`, a single failed connection attempt is
 * fatal: `NestFactory.create` will reject and the process will exit with a
 * non-zero status.
 *
 * This service is therefore expected to be started against an already-ready
 * database. Orchestration concerns (waiting for the database to accept
 * connections before launching this container) are out of scope for the
 * application code and must be handled by the surrounding deployment.
 */
async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, { abortOnError: false });
  app.enableShutdownHooks();
  const port = parseInt(process.env.PORT || "8080", 10);
  await app.listen(port, "0.0.0.0");
}

bootstrap().catch((err: unknown) => {
  // eslint-disable-next-line no-console
  console.error("Bootstrap failed:", err);
  process.exit(1);
});
