import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";
import { existsSync } from "fs";
import type { BotContext } from "../context.js";

/**
 * /memory — View project's CLAUDE.md
 * /memory set <content> — Replace CLAUDE.md content
 * /memory append <content> — Append to CLAUDE.md
 */
export async function memoryCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) return;

  const claudeMdPath = join(project.directory, "CLAUDE.md");
  const parts = ctx.message?.text?.split(/\s+/).slice(1) ?? [];
  const action = parts[0];

  if (!action) {
    // Show current CLAUDE.md
    try {
      const content = await readFile(claudeMdPath, "utf-8");
      const truncated =
        content.length > 3500
          ? content.slice(0, 3500) + "\n\n... (truncated)"
          : content;
      await ctx.reply(`CLAUDE.md:\n\n${truncated}`);
    } catch {
      await ctx.reply(
        "No CLAUDE.md found in project directory.\n\nUse /memory set <content> to create one.",
      );
    }
    return;
  }

  if (action === "set") {
    const content = parts.slice(1).join(" ");
    if (!content) {
      await ctx.reply("Usage: /memory set <content>");
      return;
    }
    await ensureDir(project.directory);
    await writeFile(claudeMdPath, content, "utf-8");
    await ctx.reply("CLAUDE.md updated.");
    return;
  }

  if (action === "append") {
    const content = parts.slice(1).join(" ");
    if (!content) {
      await ctx.reply("Usage: /memory append <content>");
      return;
    }

    let existing = "";
    try {
      existing = await readFile(claudeMdPath, "utf-8");
    } catch {
      // File doesn't exist yet
    }

    await ensureDir(project.directory);
    await writeFile(claudeMdPath, existing + "\n" + content, "utf-8");
    await ctx.reply("Content appended to CLAUDE.md.");
    return;
  }

  await ctx.reply("Usage: /memory, /memory set <content>, /memory append <content>");
}

async function ensureDir(dir: string): Promise<void> {
  if (!existsSync(dir)) {
    await mkdir(dir, { recursive: true });
  }
}
