import { getDb } from "../client.js";
import type { NewSession, Session, SessionUpdate } from "../schema.js";

export const sessionRepo = {
  async findActiveByProject(projectId: number): Promise<Session | undefined> {
    return getDb()
      .selectFrom("sessions")
      .selectAll()
      .where("project_id", "=", projectId)
      .where("status", "=", "active")
      .orderBy("last_activity", "desc")
      .executeTakeFirst();
  },

  async create(session: NewSession): Promise<Session> {
    return getDb()
      .insertInto("sessions")
      .values(session)
      .returningAll()
      .executeTakeFirstOrThrow();
  },

  async update(
    id: number,
    update: SessionUpdate,
  ): Promise<Session | undefined> {
    return getDb()
      .updateTable("sessions")
      .set(update)
      .where("id", "=", id)
      .returningAll()
      .executeTakeFirst();
  },

  async touchActivity(id: number): Promise<void> {
    await getDb()
      .updateTable("sessions")
      .set({ last_activity: new Date() })
      .where("id", "=", id)
      .execute();
  },

  async closeByProject(projectId: number): Promise<void> {
    await getDb()
      .updateTable("sessions")
      .set({ status: "closed" })
      .where("project_id", "=", projectId)
      .where("status", "=", "active")
      .execute();
  },
};
