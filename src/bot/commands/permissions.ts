import { InlineKeyboard } from "grammy";
import { projectRepo } from "../../db/repositories/project.js";
import type { BotContext } from "../context.js";

const PERMISSION_PRESETS: Record<string, { label: string; description: string }> = {
  plan: {
    label: "Plan Only",
    description: "Read-only — Claude analyzes but doesn't change files",
  },
  default: {
    label: "Default",
    description: "Prompts for dangerous operations",
  },
  acceptEdits: {
    label: "Accept Edits",
    description: "Auto-accepts file edits, prompts for bash",
  },
  dontAsk: {
    label: "Don't Ask",
    description: "No prompts (CI/CD mode)",
  },
  bypassPermissions: {
    label: "Bypass All",
    description: "Skip all permission prompts",
  },
};

/** /permissions [mode] — View or set permission mode */
export async function permissionsCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) return;

  const arg = ctx.message?.text?.split(/\s+/)[1]?.trim();

  if (arg && arg in PERMISSION_PRESETS) {
    await projectRepo.update(project.id, { permission_mode: arg });
    const preset = PERMISSION_PRESETS[arg]!;
    await ctx.reply(`Permission mode set to: ${preset.label}\n${preset.description}`);
    return;
  }

  const current = PERMISSION_PRESETS[project.permission_mode];
  const keyboard = new InlineKeyboard();
  for (const [key, preset] of Object.entries(PERMISSION_PRESETS)) {
    const prefix = key === project.permission_mode ? "▶ " : "";
    keyboard
      .text(`${prefix}${preset.label}`, `perm_mode:${key}`)
      .row();
  }

  await ctx.reply(
    [
      `Current mode: ${current?.label ?? project.permission_mode}`,
      current ? `\n${current.description}` : "",
      "\nSelect a mode:",
    ].join(""),
    { reply_markup: keyboard },
  );
}
