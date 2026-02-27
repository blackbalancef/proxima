import { createBot } from "./bot/bot.js";
import { runMigrations } from "./db/migrate.js";
import { setupGracefulShutdown } from "./utils/lifecycle.js";
import { logger } from "./utils/logger.js";

async function main(): Promise<void> {
  // Run DB migrations
  await runMigrations();

  const bot = createBot();
  setupGracefulShutdown(bot);

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
