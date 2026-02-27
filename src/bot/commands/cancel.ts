import { cancelQuery } from "../../claude/query-runner.js";
import type { BotContext } from "../context.js";

/** /cancel — Abort the current Claude query */
export async function cancelCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const cancelled = cancelQuery(chatId);
  if (cancelled) {
    await ctx.reply("Cancelling current query...");
  } else {
    await ctx.reply("No active query to cancel.");
  }
}
