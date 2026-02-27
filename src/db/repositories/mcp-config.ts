import { getDb } from "../client.js";
import type { McpConfig, NewMcpConfig } from "../schema.js";

export const mcpConfigRepo = {
  async findByProject(projectId: number): Promise<McpConfig[]> {
    return getDb()
      .selectFrom("mcp_configs")
      .selectAll()
      .where("project_id", "=", projectId)
      .orderBy("server_name")
      .execute();
  },

  async findEnabledByProject(projectId: number): Promise<McpConfig[]> {
    return getDb()
      .selectFrom("mcp_configs")
      .selectAll()
      .where("project_id", "=", projectId)
      .where("enabled", "=", true)
      .execute();
  },

  async upsert(config: NewMcpConfig): Promise<McpConfig> {
    const db = getDb();
    // Try update first
    const existing = await db
      .selectFrom("mcp_configs")
      .selectAll()
      .where("project_id", "=", config.project_id)
      .where("server_name", "=", config.server_name)
      .executeTakeFirst();

    if (existing) {
      return db
        .updateTable("mcp_configs")
        .set({
          config_json: config.config_json,
          enabled: config.enabled,
        })
        .where("id", "=", existing.id)
        .returningAll()
        .executeTakeFirstOrThrow();
    }

    return db
      .insertInto("mcp_configs")
      .values(config)
      .returningAll()
      .executeTakeFirstOrThrow();
  },

  async toggle(id: number, enabled: boolean): Promise<void> {
    await getDb()
      .updateTable("mcp_configs")
      .set({ enabled })
      .where("id", "=", id)
      .execute();
  },

  async deleteById(id: number): Promise<void> {
    await getDb().deleteFrom("mcp_configs").where("id", "=", id).execute();
  },
};
