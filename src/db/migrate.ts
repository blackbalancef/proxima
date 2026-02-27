import { sql } from "kysely";
import { getDb } from "./client.js";
import { logger } from "../utils/logger.js";

export async function runMigrations(): Promise<void> {
  const db = getDb();
  logger.info("Running migrations...");

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
    CREATE INDEX IF NOT EXISTS idx_projects_chat_active
    ON projects(telegram_chat_id, is_active)
  `.execute(db);

  await sql`
    CREATE INDEX IF NOT EXISTS idx_sessions_project
    ON sessions(project_id)
  `.execute(db);

  logger.info("Migrations complete");
}
