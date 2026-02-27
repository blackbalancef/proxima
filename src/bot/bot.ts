import { Bot } from "grammy";
import { config } from "../config.js";
import type { BotContext } from "./context.js";
import { authMiddleware } from "./middleware/auth.js";
import { errorHandler } from "./middleware/error-handler.js";
import { handleMessage } from "./handlers/message.js";

export function createBot(): Bot<BotContext> {
  const bot = new Bot<BotContext>(config.telegramBotToken);

  bot.catch(errorHandler);

  // Auth: only allowed users
  bot.use(authMiddleware);

  // Commands
  bot.command("start", (ctx) =>
    ctx.reply(
      "Welcome to Proxima! Send me a message and I'll forward it to Claude Code.",
    ),
  );

  bot.command("help", (ctx) =>
    ctx.reply(
      [
        "Proxima — Claude Code Telegram Bot",
        "",
        "Just send a text message to chat with Claude Code.",
        "",
        "Commands:",
        "/start — Welcome message",
        "/help — Show this help",
      ].join("\n"),
    ),
  );

  // Text messages → Claude
  bot.on("message:text", handleMessage);

  return bot;
}
