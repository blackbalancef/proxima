import { getDb } from "../client.js";
import type { NewProject, Project, ProjectUpdate } from "../schema.js";

export const projectRepo = {
  async findActiveByChat(chatId: number): Promise<Project | undefined> {
    return getDb()
      .selectFrom("projects")
      .selectAll()
      .where("telegram_chat_id", "=", chatId)
      .where("is_active", "=", true)
      .executeTakeFirst();
  },

  async findAllByChat(chatId: number): Promise<Project[]> {
    return getDb()
      .selectFrom("projects")
      .selectAll()
      .where("telegram_chat_id", "=", chatId)
      .orderBy("created_at", "desc")
      .execute();
  },

  async findById(id: number): Promise<Project | undefined> {
    return getDb()
      .selectFrom("projects")
      .selectAll()
      .where("id", "=", id)
      .executeTakeFirst();
  },

  async create(project: NewProject): Promise<Project> {
    return getDb()
      .insertInto("projects")
      .values(project)
      .returningAll()
      .executeTakeFirstOrThrow();
  },

  async update(id: number, update: ProjectUpdate): Promise<Project | undefined> {
    return getDb()
      .updateTable("projects")
      .set(update)
      .where("id", "=", id)
      .returningAll()
      .executeTakeFirst();
  },

  async setActive(chatId: number, projectId: number): Promise<void> {
    const db = getDb();
    // Deactivate all projects for this chat
    await db
      .updateTable("projects")
      .set({ is_active: false })
      .where("telegram_chat_id", "=", chatId)
      .execute();
    // Activate selected
    await db
      .updateTable("projects")
      .set({ is_active: true })
      .where("id", "=", projectId)
      .execute();
  },

  async deleteById(id: number): Promise<void> {
    await getDb().deleteFrom("projects").where("id", "=", id).execute();
  },
};
