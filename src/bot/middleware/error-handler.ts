import { BotError } from "grammy";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function errorHandler(err: BotError<BotContext>): Promise<void> {
  const { ctx, error } = err;
  logger.error({ error, update: ctx.update }, "Bot error");

  try {
    await ctx.reply("An error occurred. Please try again.");
  } catch {
    // Failed to send error message — nothing we can do
  }
}
