import { Bot } from "grammy";
import { config } from "../config.js";
import type { BotContext } from "./context.js";
import { authMiddleware } from "./middleware/auth.js";
import { projectResolverMiddleware } from "./middleware/project-resolver.js";
import { errorHandler } from "./middleware/error-handler.js";
import { handleMessage } from "./handlers/message.js";
import { handleCallback } from "./handlers/callback.js";
import { handleVoice } from "./handlers/voice.js";
import { handleBash } from "./handlers/bash.js";
import { startCommand, helpCommand } from "./commands/help.js";
import {
  newProjectCommand,
  listProjectsCommand,
  switchProjectCommand,
  deleteProjectCommand,
  renameProjectCommand,
} from "./commands/project.js";
import { resetSessionCommand, infoCommand } from "./commands/session.js";
import { permissionsCommand } from "./commands/permissions.js";
import { modeCommand } from "./commands/mode.js";
import { cancelCommand } from "./commands/cancel.js";
import { mcpCommand } from "./commands/mcp.js";
import { memoryCommand } from "./commands/memory.js";
import { serverCommand } from "./commands/server.js";
import { usersCommand } from "./commands/users.js";

export function createBot(): Bot<BotContext> {
  const bot = new Bot<BotContext>(config.telegramBotToken);

  bot.catch(errorHandler);

  // Middleware stack
  bot.use(authMiddleware);
  bot.use(projectResolverMiddleware);

  // General commands
  bot.command("start", startCommand);
  bot.command("help", helpCommand);
  bot.command("cancel", cancelCommand);

  // Project commands
  bot.command("new", newProjectCommand);
  bot.command("projects", listProjectsCommand);
  bot.command("switch", switchProjectCommand);
  bot.command("delete", deleteProjectCommand);
  bot.command("rename", renameProjectCommand);

  // Session commands
  bot.command("reset", resetSessionCommand);
  bot.command("info", infoCommand);

  // Settings
  bot.command("mode", modeCommand);
  bot.command("permissions", permissionsCommand);
  bot.command("mcp", mcpCommand);
  bot.command("memory", memoryCommand);

  // Admin
  bot.command("server", serverCommand);
  bot.command("users", usersCommand);

  // Callback queries (inline buttons)
  bot.on("callback_query:data", handleCallback);

  // Voice messages → Whisper → Claude
  bot.on("message:voice", handleVoice);

  // Text messages: "!" prefix → bash, otherwise → Claude
  bot.on("message:text", async (ctx) => {
    if (ctx.message.text.startsWith("!")) {
      await handleBash(ctx);
    } else {
      await handleMessage(ctx);
    }
  });

  return bot;
}
