import type { Generated, Insertable, Selectable, Updateable } from "kysely";

export interface Database {
  projects: ProjectTable;
  sessions: SessionTable;
}

export interface ProjectTable {
  id: Generated<number>;
  telegram_chat_id: number;
  name: string;
  directory: string;
  is_active: boolean;
  permission_mode: string;
  created_at: Generated<Date>;
}

export type Project = Selectable<ProjectTable>;
export type NewProject = Insertable<ProjectTable>;
export type ProjectUpdate = Updateable<ProjectTable>;

export interface SessionTable {
  id: Generated<number>;
  project_id: number;
  claude_session_id: string | null;
  status: string;
  last_activity: Generated<Date>;
  created_at: Generated<Date>;
}

export type Session = Selectable<SessionTable>;
export type NewSession = Insertable<SessionTable>;
export type SessionUpdate = Updateable<SessionTable>;
