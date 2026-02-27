/**
 * Shared test setup for integration tests that require PostgreSQL.
 *
 * Expects DATABASE_URL env var to point to a test database.
 * Run: DATABASE_URL=postgresql://proxima:dev@localhost:5432/proxima_test pnpm vitest run tests/integration
 */
import { Kysely, PostgresDialect, sql } from "kysely";
import pg from "pg";
import type { Database } from "../../src/db/schema.js";

let db: Kysely<Database>;

export function getTestDb(): Kysely<Database> {
  return db;
}

export async function setupTestDb(): Promise<void> {
  const url = process.env["DATABASE_URL"];
  if (!url) {
    throw new Error("DATABASE_URL is required for integration tests");
  }

  db = new Kysely<Database>({
    dialect: new PostgresDialect({
      pool: new pg.Pool({ connectionString: url, max: 3 }),
    }),
  });

  // Run migrations inline
  await sql`
    CREATE TABLE IF NOT EXISTS projects (
      id SERIAL PRIMARY KEY,
      telegram_chat_id BIGINT NOT NULL,
      name TEXT NOT NULL,
      directory TEXT NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT false,
      permission_mode TEXT NOT NULL DEFAULT 'default',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE(telegram_chat_id, name)
    )
  `.execute(db);

  await sql`
    CREATE TABLE IF NOT EXISTS sessions (
      id SERIAL PRIMARY KEY,
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      claude_session_id TEXT,
      status TEXT NOT NULL DEFAULT 'active',
      last_activity TIMESTAMPTZ NOT NULL DEFAULT now(),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
  `.execute(db);

  await sql`
    CREATE TABLE IF NOT EXISTS mcp_configs (
      id SERIAL PRIMARY KEY,
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      server_name TEXT NOT NULL,
      config_json TEXT NOT NULL DEFAULT '{}',
      enabled BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE(project_id, server_name)
    )
  `.execute(db);
}

export async function cleanTestDb(): Promise<void> {
  await sql`DELETE FROM mcp_configs`.execute(db);
  await sql`DELETE FROM sessions`.execute(db);
  await sql`DELETE FROM projects`.execute(db);
}

export async function teardownTestDb(): Promise<void> {
  await db.destroy();
}
