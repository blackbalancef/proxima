import { NextFunction } from "grammy";
import { projectRepo } from "../../db/repositories/project.js";
import { config } from "../../config.js";
import type { BotContext } from "../context.js";

/**
 * Resolves the active project for the current chat.
 * Creates a default project if none exists.
 * Attaches project to ctx.project.
 */
export async function projectResolverMiddleware(
  ctx: BotContext,
  next: NextFunction,
): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) {
    await next();
    return;
  }

  let project = await projectRepo.findActiveByChat(chatId);
  if (!project) {
    project = await projectRepo.create({
      telegram_chat_id: chatId,
      name: "default",
      directory: config.workDir,
      is_active: true,
      permission_mode: "bypassPermissions",
    });
  }

  ctx.project = project;
  await next();
}
