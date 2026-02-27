import { createBot } from "./bot/bot.js";
import { logger } from "./utils/logger.js";

async function main(): Promise<void> {
  const bot = createBot();

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    logger.info({ signal }, "Shutting down...");
    bot.stop();
  };

  process.on("SIGINT", () => void shutdown("SIGINT"));
  process.on("SIGTERM", () => void shutdown("SIGTERM"));

  logger.info("Starting Proxima bot...");
  await bot.start({
    onStart: (botInfo) => {
      logger.info(
        { username: botInfo.username },
        "Bot started as @%s",
        botInfo.username,
      );
    },
  });
}

main().catch((err) => {
  logger.fatal({ err }, "Failed to start bot");
  process.exit(1);
});
