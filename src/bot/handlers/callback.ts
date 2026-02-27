import { findPermissionHandler } from "../../claude/permission-handler.js";
import { projectRepo } from "../../db/repositories/project.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function handleCallback(ctx: BotContext): Promise<void> {
  const data = ctx.callbackQuery?.data;
  if (!data) return;

  const chatId = ctx.chat?.id;
  if (!chatId) return;

  logger.debug({ chatId, data }, "Callback received");

  // Permission callbacks
  if (data.startsWith("perm:")) {
    const handler = findPermissionHandler(chatId);
    if (handler) {
      const handled = await handler.handleCallback(data, async () => {
        await ctx.answerCallbackQuery();
      });
      if (handled) return;
    }
    await ctx.answerCallbackQuery({ text: "Request expired" });
    return;
  }

  // Project switch callbacks
  if (data.startsWith("project:switch:")) {
    const projectId = parseInt(data.split(":")[2]!, 10);
    if (isNaN(projectId)) return;

    await projectRepo.setActive(chatId, projectId);
    const project = await projectRepo.findById(projectId);
    if (project) {
      await ctx.answerCallbackQuery({
        text: `Switched to ${project.name}`,
      });
      await ctx.editMessageText(`Switched to project "${project.name}"`);
    }
    return;
  }

  // Mode callbacks
  if (data.startsWith("mode:")) {
    const mode = data.split(":")[1];
    const project = ctx.project;
    if (!project) return;

    const permMode = mode === "plan" ? "plan" : "bypassPermissions";
    await projectRepo.update(project.id, { permission_mode: permMode });
    const label = mode === "plan" ? "Plan" : "Execute";
    await ctx.answerCallbackQuery({ text: `Mode: ${label}` });
    await ctx.editMessageText(`Mode set to: ${label}`);
    return;
  }

  await ctx.answerCallbackQuery();
}
