import { sessionRepo } from "../db/repositories/session.js";
import { logger } from "../utils/logger.js";

export interface ActiveSession {
  dbId: number;
  projectId: number;
  claudeSessionId: string | null;
}

/**
 * Manages Claude Code sessions, mapping projects to SDK sessions.
 * Handles creation, resumption, and cleanup.
 */
export const sessionManager = {
  async getOrCreate(projectId: number): Promise<ActiveSession> {
    // Find existing active session
    const existing = await sessionRepo.findActiveByProject(projectId);
    if (existing) {
      logger.debug(
        { projectId, sessionId: existing.claude_session_id },
        "Resuming session",
      );
      return {
        dbId: existing.id,
        projectId: existing.project_id,
        claudeSessionId: existing.claude_session_id,
      };
    }

    // Create new session
    const session = await sessionRepo.create({
      project_id: projectId,
      status: "active",
    });
    logger.info({ projectId, dbId: session.id }, "Created new session");
    return {
      dbId: session.id,
      projectId: session.project_id,
      claudeSessionId: null,
    };
  },

  async updateClaudeSessionId(
    dbId: number,
    claudeSessionId: string,
  ): Promise<void> {
    await sessionRepo.update(dbId, {
      claude_session_id: claudeSessionId,
    });
    logger.debug({ dbId, claudeSessionId }, "Updated Claude session ID");
  },

  async touchActivity(dbId: number): Promise<void> {
    await sessionRepo.touchActivity(dbId);
  },

  async resetSession(projectId: number): Promise<void> {
    await sessionRepo.closeByProject(projectId);
    logger.info({ projectId }, "Reset session");
  },
};
