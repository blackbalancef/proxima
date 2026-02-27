import { describe, it, expect, beforeAll, beforeEach, afterAll } from "vitest";
import {
  setupTestDb,
  cleanTestDb,
  teardownTestDb,
  getTestDb,
} from "./db-setup.js";

// We can't import the real repos because they use the singleton getDb()
// which reads config. Instead we test the same queries against the test db.
import type { Database, NewProject, NewSession } from "../../src/db/schema.js";
import type { Kysely } from "kysely";

let db: Kysely<Database>;

beforeAll(async () => {
  await setupTestDb();
  db = getTestDb();
});

beforeEach(async () => {
  await cleanTestDb();
});

afterAll(async () => {
  await teardownTestDb();
});

describe("projects repository", () => {
  async function createProject(overrides: Partial<NewProject> = {}) {
    return db
      .insertInto("projects")
      .values({
        telegram_chat_id: 111,
        name: "test-project",
        directory: "/tmp/test",
        is_active: false,
        permission_mode: "default",
        ...overrides,
      })
      .returningAll()
      .executeTakeFirstOrThrow();
  }

  it("creates a project", async () => {
    const project = await createProject();

    expect(project.id).toBeGreaterThan(0);
    expect(project.name).toBe("test-project");
    expect(project.telegram_chat_id).toBe(111);
    expect(project.is_active).toBe(false);
  });

  it("finds active project by chat", async () => {
    await createProject({ is_active: true });
    await createProject({ name: "inactive", is_active: false });

    const active = await db
      .selectFrom("projects")
      .selectAll()
      .where("telegram_chat_id", "=", 111)
      .where("is_active", "=", true)
      .executeTakeFirst();

    expect(active).toBeDefined();
    expect(active!.name).toBe("test-project");
  });

  it("lists all projects for a chat", async () => {
    await createProject({ name: "a" });
    await createProject({ name: "b" });
    await createProject({ telegram_chat_id: 999, name: "other" });

    const projects = await db
      .selectFrom("projects")
      .selectAll()
      .where("telegram_chat_id", "=", 111)
      .execute();

    expect(projects.length).toBe(2);
  });

  it("switches active project", async () => {
    const p1 = await createProject({ name: "alpha", is_active: true });
    const p2 = await createProject({ name: "beta", is_active: false });

    // Deactivate all
    await db
      .updateTable("projects")
      .set({ is_active: false })
      .where("telegram_chat_id", "=", 111)
      .execute();

    // Activate p2
    await db
      .updateTable("projects")
      .set({ is_active: true })
      .where("id", "=", p2.id)
      .execute();

    const active = await db
      .selectFrom("projects")
      .selectAll()
      .where("telegram_chat_id", "=", 111)
      .where("is_active", "=", true)
      .executeTakeFirst();

    expect(active!.id).toBe(p2.id);

    // p1 should be inactive
    const old = await db
      .selectFrom("projects")
      .selectAll()
      .where("id", "=", p1.id)
      .executeTakeFirst();
    expect(old!.is_active).toBe(false);
  });

  it("deletes a project and cascades to sessions", async () => {
    const project = await createProject();

    await db
      .insertInto("sessions")
      .values({ project_id: project.id, status: "active" })
      .execute();

    await db.deleteFrom("projects").where("id", "=", project.id).execute();

    const sessions = await db
      .selectFrom("sessions")
      .selectAll()
      .where("project_id", "=", project.id)
      .execute();

    expect(sessions.length).toBe(0);
  });

  it("enforces unique (telegram_chat_id, name) constraint", async () => {
    await createProject({ name: "unique-test" });

    await expect(
      createProject({ name: "unique-test" }),
    ).rejects.toThrow();
  });
});

describe("sessions repository", () => {
  async function createProjectAndSession() {
    const project = await db
      .insertInto("projects")
      .values({
        telegram_chat_id: 222,
        name: "session-test",
        directory: "/tmp",
        is_active: true,
        permission_mode: "default",
      })
      .returningAll()
      .executeTakeFirstOrThrow();

    const session = await db
      .insertInto("sessions")
      .values({ project_id: project.id, status: "active" })
      .returningAll()
      .executeTakeFirstOrThrow();

    return { project, session };
  }

  it("creates a session for a project", async () => {
    const { session } = await createProjectAndSession();

    expect(session.id).toBeGreaterThan(0);
    expect(session.status).toBe("active");
    expect(session.claude_session_id).toBeNull();
  });

  it("finds active session by project", async () => {
    const { project, session } = await createProjectAndSession();

    const found = await db
      .selectFrom("sessions")
      .selectAll()
      .where("project_id", "=", project.id)
      .where("status", "=", "active")
      .executeTakeFirst();

    expect(found).toBeDefined();
    expect(found!.id).toBe(session.id);
  });

  it("updates claude_session_id", async () => {
    const { session } = await createProjectAndSession();

    await db
      .updateTable("sessions")
      .set({ claude_session_id: "sdk-session-123" })
      .where("id", "=", session.id)
      .execute();

    const updated = await db
      .selectFrom("sessions")
      .selectAll()
      .where("id", "=", session.id)
      .executeTakeFirst();

    expect(updated!.claude_session_id).toBe("sdk-session-123");
  });

  it("closes sessions by project", async () => {
    const { project } = await createProjectAndSession();

    await db
      .updateTable("sessions")
      .set({ status: "closed" })
      .where("project_id", "=", project.id)
      .where("status", "=", "active")
      .execute();

    const active = await db
      .selectFrom("sessions")
      .selectAll()
      .where("project_id", "=", project.id)
      .where("status", "=", "active")
      .execute();

    expect(active.length).toBe(0);
  });
});

describe("mcp_configs repository", () => {
  async function createProjectWithMcp() {
    const project = await db
      .insertInto("projects")
      .values({
        telegram_chat_id: 333,
        name: "mcp-test",
        directory: "/tmp",
        is_active: true,
        permission_mode: "default",
      })
      .returningAll()
      .executeTakeFirstOrThrow();

    return project;
  }

  it("creates an MCP config", async () => {
    const project = await createProjectWithMcp();

    const config = await db
      .insertInto("mcp_configs")
      .values({
        project_id: project.id,
        server_name: "playwright",
        config_json: JSON.stringify({ command: "npx", args: ["@playwright/mcp"] }),
        enabled: true,
      })
      .returningAll()
      .executeTakeFirstOrThrow();

    expect(config.server_name).toBe("playwright");
    expect(config.enabled).toBe(true);
  });

  it("finds enabled configs by project", async () => {
    const project = await createProjectWithMcp();

    await db
      .insertInto("mcp_configs")
      .values([
        { project_id: project.id, server_name: "a", config_json: "{}", enabled: true },
        { project_id: project.id, server_name: "b", config_json: "{}", enabled: false },
        { project_id: project.id, server_name: "c", config_json: "{}", enabled: true },
      ])
      .execute();

    const enabled = await db
      .selectFrom("mcp_configs")
      .selectAll()
      .where("project_id", "=", project.id)
      .where("enabled", "=", true)
      .execute();

    expect(enabled.length).toBe(2);
  });

  it("toggles enabled state", async () => {
    const project = await createProjectWithMcp();

    const config = await db
      .insertInto("mcp_configs")
      .values({
        project_id: project.id,
        server_name: "test",
        config_json: "{}",
        enabled: true,
      })
      .returningAll()
      .executeTakeFirstOrThrow();

    await db
      .updateTable("mcp_configs")
      .set({ enabled: false })
      .where("id", "=", config.id)
      .execute();

    const updated = await db
      .selectFrom("mcp_configs")
      .selectAll()
      .where("id", "=", config.id)
      .executeTakeFirst();

    expect(updated!.enabled).toBe(false);
  });

  it("enforces unique (project_id, server_name) constraint", async () => {
    const project = await createProjectWithMcp();

    await db
      .insertInto("mcp_configs")
      .values({ project_id: project.id, server_name: "dup", config_json: "{}" })
      .execute();

    await expect(
      db
        .insertInto("mcp_configs")
        .values({ project_id: project.id, server_name: "dup", config_json: "{}" })
        .execute(),
    ).rejects.toThrow();
  });
});
