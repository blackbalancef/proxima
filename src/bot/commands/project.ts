import { projectRepo } from "../../db/repositories/project.js";
import { config } from "../../config.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

/** /new [name] — Create a new project */
export async function newProjectCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const args = ctx.message?.text?.split(/\s+/).slice(1).join(" ").trim();
  if (!args) {
    await ctx.reply(
      "Usage: /new <project-name> [directory]\n\nExample:\n/new myapp /path/to/myapp\n/new myapp",
    );
    return;
  }

  const parts = args.split(/\s+/);
  const name = parts[0]!;
  const directory = parts[1] ?? config.workDir;

  try {
    const project = await projectRepo.create({
      telegram_chat_id: chatId,
      name,
      directory,
      is_active: false,
      permission_mode: "bypassPermissions",
    });

    // Switch to it
    await projectRepo.setActive(chatId, project.id);
    ctx.project = project;

    await ctx.reply(`Project "${name}" created and activated.\nDir: ${directory}`);
    logger.info({ chatId, name, directory }, "Project created");
  } catch (error) {
    if (String(error).includes("unique")) {
      await ctx.reply(`Project "${name}" already exists. Use /switch ${name}`);
    } else {
      throw error;
    }
  }
}

/** /projects — List all projects */
export async function listProjectsCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const projects = await projectRepo.findAllByChat(chatId);
  if (projects.length === 0) {
    await ctx.reply("No projects. Use /new to create one.");
    return;
  }

  const lines = projects.map(
    (p) => `${p.is_active ? "▶" : "  "} ${p.name} — ${p.directory}`,
  );
  await ctx.reply(`Projects:\n\n${lines.join("\n")}`);
}

/** /switch <name> — Switch active project */
export async function switchProjectCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const name = ctx.message?.text?.split(/\s+/)[1]?.trim();
  if (!name) {
    await ctx.reply("Usage: /switch <project-name>");
    return;
  }

  const projects = await projectRepo.findAllByChat(chatId);
  const target = projects.find((p) => p.name === name);
  if (!target) {
    await ctx.reply(`Project "${name}" not found. Use /projects to list.`);
    return;
  }

  await projectRepo.setActive(chatId, target.id);
  ctx.project = target;
  await ctx.reply(`Switched to project "${name}"\nDir: ${target.directory}`);
}

/** /delete <name> — Delete a project */
export async function deleteProjectCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const name = ctx.message?.text?.split(/\s+/)[1]?.trim();
  if (!name) {
    await ctx.reply("Usage: /delete <project-name>");
    return;
  }

  const projects = await projectRepo.findAllByChat(chatId);
  const target = projects.find((p) => p.name === name);
  if (!target) {
    await ctx.reply(`Project "${name}" not found.`);
    return;
  }

  if (target.name === "default") {
    await ctx.reply("Cannot delete the default project.");
    return;
  }

  await projectRepo.deleteById(target.id);
  await ctx.reply(`Project "${name}" deleted.`);
  logger.info({ chatId, name }, "Project deleted");
}

/** /rename <old> <new> — Rename a project */
export async function renameProjectCommand(ctx: BotContext): Promise<void> {
  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const parts = ctx.message?.text?.split(/\s+/).slice(1) ?? [];
  const oldName = parts[0];
  const newName = parts[1];

  if (!oldName || !newName) {
    await ctx.reply("Usage: /rename <old-name> <new-name>");
    return;
  }

  const projects = await projectRepo.findAllByChat(chatId);
  const target = projects.find((p) => p.name === oldName);
  if (!target) {
    await ctx.reply(`Project "${oldName}" not found.`);
    return;
  }

  await projectRepo.update(target.id, { name: newName });
  await ctx.reply(`Project renamed: "${oldName}" → "${newName}"`);
}
