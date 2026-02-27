import { Bot } from "grammy";
import { config } from "../config.js";
import type { BotContext } from "./context.js";
import { authMiddleware } from "./middleware/auth.js";
import { projectResolverMiddleware } from "./middleware/project-resolver.js";
import { errorHandler } from "./middleware/error-handler.js";
import { handleMessage } from "./handlers/message.js";
import { startCommand, helpCommand } from "./commands/help.js";
import {
  newProjectCommand,
  listProjectsCommand,
  switchProjectCommand,
  deleteProjectCommand,
  renameProjectCommand,
} from "./commands/project.js";
import { resetSessionCommand, infoCommand } from "./commands/session.js";

export function createBot(): Bot<BotContext> {
  const bot = new Bot<BotContext>(config.telegramBotToken);

  bot.catch(errorHandler);

  // Middleware stack
  bot.use(authMiddleware);
  bot.use(projectResolverMiddleware);

  // Commands
  bot.command("start", startCommand);
  bot.command("help", helpCommand);

  // Project commands
  bot.command("new", newProjectCommand);
  bot.command("projects", listProjectsCommand);
  bot.command("switch", switchProjectCommand);
  bot.command("delete", deleteProjectCommand);
  bot.command("rename", renameProjectCommand);

  // Session commands
  bot.command("reset", resetSessionCommand);
  bot.command("info", infoCommand);

  // Text messages → Claude
  bot.on("message:text", handleMessage);

  return bot;
}
