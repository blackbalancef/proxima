import { config } from "../../config.js";
import type { BotContext } from "../context.js";

/**
 * /users — List allowed user IDs
 *
 * Note: Dynamic allow/deny would require persisting to DB.
 * For now, this just shows the static allowlist from config.
 */
export async function usersCommand(ctx: BotContext): Promise<void> {
  const userIds = config.allowedUserIds;
  const lines = userIds.map((id) => `  ${id}`);
  await ctx.reply(
    [
      "Allowed users (from ALLOWED_USER_IDS):",
      "",
      ...lines,
      "",
      "Edit .env to add/remove users, then restart.",
    ].join("\n"),
  );
}
