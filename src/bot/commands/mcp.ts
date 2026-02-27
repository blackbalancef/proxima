import { mcpConfigRepo } from "../../db/repositories/mcp-config.js";
import type { BotContext } from "../context.js";

/**
 * /mcp — List MCP servers for current project
 * /mcp add <name> <command> [args...] — Add an MCP server
 * /mcp remove <name> — Remove an MCP server
 * /mcp toggle <name> — Enable/disable an MCP server
 */
export async function mcpCommand(ctx: BotContext): Promise<void> {
  const project = ctx.project;
  if (!project) return;

  const parts = ctx.message?.text?.split(/\s+/).slice(1) ?? [];
  const action = parts[0];

  if (!action) {
    // List MCP servers
    const configs = await mcpConfigRepo.findByProject(project.id);
    if (configs.length === 0) {
      await ctx.reply(
        "No MCP servers configured.\n\nUsage: /mcp add <name> <command> [args...]",
      );
      return;
    }

    const lines = configs.map((c) => {
      const status = c.enabled ? "✅" : "❌";
      const config = JSON.parse(c.config_json) as Record<string, unknown>;
      return `${status} ${c.server_name} — ${config["command"] ?? ""}`;
    });
    await ctx.reply(`MCP servers:\n\n${lines.join("\n")}`);
    return;
  }

  if (action === "add") {
    const name = parts[1];
    const command = parts[2];
    const args = parts.slice(3);

    if (!name || !command) {
      await ctx.reply(
        "Usage: /mcp add <name> <command> [args...]\n\nExample: /mcp add playwright npx @playwright/mcp@latest",
      );
      return;
    }

    await mcpConfigRepo.upsert({
      project_id: project.id,
      server_name: name,
      config_json: JSON.stringify({ command, args }),
      enabled: true,
    });

    await ctx.reply(`MCP server "${name}" added.\nCommand: ${command} ${args.join(" ")}`);
    return;
  }

  if (action === "remove") {
    const name = parts[1];
    if (!name) {
      await ctx.reply("Usage: /mcp remove <name>");
      return;
    }

    const configs = await mcpConfigRepo.findByProject(project.id);
    const target = configs.find((c) => c.server_name === name);
    if (!target) {
      await ctx.reply(`MCP server "${name}" not found.`);
      return;
    }

    await mcpConfigRepo.deleteById(target.id);
    await ctx.reply(`MCP server "${name}" removed.`);
    return;
  }

  if (action === "toggle") {
    const name = parts[1];
    if (!name) {
      await ctx.reply("Usage: /mcp toggle <name>");
      return;
    }

    const configs = await mcpConfigRepo.findByProject(project.id);
    const target = configs.find((c) => c.server_name === name);
    if (!target) {
      await ctx.reply(`MCP server "${name}" not found.`);
      return;
    }

    await mcpConfigRepo.toggle(target.id, !target.enabled);
    const status = !target.enabled ? "enabled" : "disabled";
    await ctx.reply(`MCP server "${name}" ${status}.`);
    return;
  }

  await ctx.reply("Unknown action. Use: /mcp, /mcp add, /mcp remove, /mcp toggle");
}
