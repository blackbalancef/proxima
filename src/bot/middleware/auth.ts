import { NextFunction } from "grammy";
import { config } from "../../config.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function authMiddleware(
  ctx: BotContext,
  next: NextFunction,
): Promise<void> {
  const userId = ctx.from?.id;
  if (!userId || !config.allowedUserIds.includes(userId)) {
    logger.warn({ userId }, "Unauthorized access attempt");
    return;
  }
  await next();
}
