import { sessionManager } from "../../claude/session-manager.js";
import { sessionRepo } from "../../db/repositories/session.js";
import type { BotContext } from "../context.js";

/** /reset — Reset current session (start fresh conversation) */
export async function resetSessionCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) {
    await ctx.reply("No active project. Use /new to create one.");
    return;
  }

  await sessionManager.resetSession(project.id);
  await ctx.reply(
    `Session reset for project "${project.name}".\nNext message starts a fresh conversation.`,
  );
}

/** /info — Show current project and session info */
export async function infoCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) {
    await ctx.reply("No active project.");
    return;
  }

  const session = await sessionRepo.findActiveByProject(project.id);

  const lines = [
    `Project: ${project.name}`,
    `Directory: ${project.directory}`,
    `Permission mode: ${project.permission_mode}`,
    "",
    session
      ? [
          `Session: active`,
          `Claude session: ${session.claude_session_id ?? "(not started)"}`,
          `Last activity: ${session.last_activity.toISOString()}`,
        ].join("\n")
      : "Session: none",
  ];

  await ctx.reply(lines.join("\n"));
}
