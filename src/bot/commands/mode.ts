import { projectRepo } from "../../db/repositories/project.js";
import { buildModeKeyboard } from "../../telegram/keyboard-builder.js";
import type { BotContext } from "../context.js";

/** /mode [plan|execute] — View or set Claude execution mode */
export async function modeCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) return;

  const arg = ctx.message?.text?.split(/\s+/)[1]?.trim();

  if (arg === "plan") {
    await projectRepo.update(project.id, { permission_mode: "plan" });
    await ctx.reply("Mode: Plan\nClaude will analyze but not modify files.");
    return;
  }

  if (arg === "execute") {
    await projectRepo.update(project.id, {
      permission_mode: "bypassPermissions",
    });
    await ctx.reply("Mode: Execute\nClaude can modify files and run commands.");
    return;
  }

  const currentMode =
    project.permission_mode === "plan" ? "Plan" : "Execute";
  await ctx.reply(`Current mode: ${currentMode}\n\nSelect mode:`, {
    reply_markup: buildModeKeyboard(),
  });
}
