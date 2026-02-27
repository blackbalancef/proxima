import type { BotContext } from "../context.js";

export async function startCommand(ctx: BotContext): Promise<void> {
  await ctx.reply(
    [
      "Welcome to Proxima!",
      "",
      "Send me a text message and I'll forward it to Claude Code.",
      "Send a voice message — I'll transcribe and forward it.",
      "Prefix with ! to run a bash command directly.",
      "",
      "Use /help for the full command list.",
    ].join("\n"),
  );
}

export async function helpCommand(ctx: BotContext): Promise<void> {
  await ctx.reply(
    [
      "Proxima — Claude Code Telegram Bot",
      "",
      "Text message — Claude Code",
      "Voice message — Whisper + Claude Code",
      "! <command> — Direct bash execution",
      "",
      "Projects:",
      "  /new <name> [dir] — Create project",
      "  /projects — List projects",
      "  /switch <name> — Switch project",
      "  /rename <old> <new> — Rename",
      "  /delete <name> — Delete",
      "",
      "Sessions:",
      "  /reset — Reset conversation",
      "  /cancel — Abort current query",
      "  /info — Project/session info",
      "",
      "Settings:",
      "  /mode [plan|execute] — Execution mode",
      "  /permissions [mode] — Permission presets",
      "  /mcp — Manage MCP servers",
      "  /memory — View/edit CLAUDE.md",
      "",
      "Admin:",
      "  /server — Server info",
      "  /users — Allowed users",
    ].join("\n"),
  );
}
