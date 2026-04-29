import { Controller, Get, InternalServerErrorException } from "@nestjs/common";
import { InjectDataSource } from "@nestjs/typeorm";
import { DataSource } from "typeorm";

interface CheckDbResponse {
  ok: boolean;
  result: number;
}

@Controller()
export class AppController {
  constructor(@InjectDataSource() private readonly dataSource: DataSource) {}

  /**
   * Probe endpoint. Executes `SELECT 1` against the configured Postgres
   * connection and returns the result. The integer in `result` comes from
   * the database, not from the application; if Postgres is reachable but
   * mis-configured, this will surface as a non-1 value.
   */
  @Get("checkdb")
  async checkdb(): Promise<CheckDbResponse> {
    try {
      const rows: { result: string | number }[] =
        await this.dataSource.query("SELECT 1 AS result");
      const value = Number(rows?.[0]?.result);
      if (!Number.isFinite(value)) {
        throw new InternalServerErrorException("Invalid SELECT 1 result");
      }
      return { ok: true, result: value };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new InternalServerErrorException(`DB query failed: ${message}`);
    }
  }
}
