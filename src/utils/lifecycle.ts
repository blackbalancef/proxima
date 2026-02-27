import { Bot } from "grammy";
import { closeDb } from "../db/client.js";
import { logger } from "./logger.js";
import type { BotContext } from "../bot/context.js";

export function setupGracefulShutdown(bot: Bot<BotContext>): void {
  const shutdown = async (signal: string) => {
    logger.info({ signal }, "Shutting down gracefully...");
    bot.stop();
    await closeDb();
    logger.info("Shutdown complete");
    process.exit(0);
  };

  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  process.on("unhandledRejection", (error) => {
    logger.error({ error }, "Unhandled rejection");
  });
}
