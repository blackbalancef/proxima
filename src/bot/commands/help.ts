import type { BotContext } from "../context.js";

export async function startCommand(ctx: BotContext): Promise<void> {
  await ctx.reply(
    [
      "Welcome to Proxima!",
      "",
      "Send me a text message and I'll forward it to Claude Code.",
      "Use /help for the full command list.",
    ].join("\n"),
  );
}

export async function helpCommand(ctx: BotContext): Promise<void> {
  await ctx.reply(
    [
      "Proxima — Claude Code Telegram Bot",
      "",
      "Send any text to chat with Claude Code.",
      "",
      "Project commands:",
      "  /new <name> [dir] — Create project",
      "  /projects — List projects",
      "  /switch <name> — Switch project",
      "  /rename <old> <new> — Rename project",
      "  /delete <name> — Delete project",
      "",
      "Session commands:",
      "  /reset — Reset conversation",
      "  /info — Show project/session info",
      "",
      "More commands coming soon!",
    ].join("\n"),
  );
}
