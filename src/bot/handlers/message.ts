import { query } from "@anthropic-ai/claude-agent-sdk";
import { sessionManager } from "../../claude/session-manager.js";
import { getPermissionHandler } from "../../claude/permission-handler.js";
import {
  getAbortController,
  clearController,
} from "../../claude/query-runner.js";
import { StreamRenderer } from "../../claude/stream-renderer.js";
import { MessageSender } from "../../telegram/message-sender.js";
import { mcpConfigRepo } from "../../db/repositories/mcp-config.js";
import { messageQueue } from "../../utils/queue.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function handleMessage(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text;
  if (!text) return;

  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const project = ctx.project;

  // Enqueue for sequential processing per project
  messageQueue.enqueue(project.id, async () => {
    logger.info(
      { chatId, projectId: project.id, text: text.slice(0, 100) },
      "Processing message",
    );

    const statusMsg = await ctx.reply("⏳ Thinking...");
    const sender = new MessageSender(ctx.api, chatId);
    sender.setInitialMessage(statusMsg.message_id);
    const renderer = new StreamRenderer(sender);
    const permHandler = getPermissionHandler(ctx.api, chatId);
    const abortController = getAbortController(chatId);

    try {
      const session = await sessionManager.getOrCreate(project.id);
      const isBypass = project.permission_mode === "bypassPermissions";

      const options: Record<string, unknown> = {
        cwd: project.directory,
        permissionMode: project.permission_mode,
      };

      if (isBypass) {
        options["allowDangerouslySkipPermissions"] = true;
      }

      // Resume session if we have a Claude session ID
      if (session.claudeSessionId) {
        options["resume"] = session.claudeSessionId;
      }

      // Load MCP servers for this project
      const mcpConfigs = await mcpConfigRepo.findEnabledByProject(project.id);
      if (mcpConfigs.length > 0) {
        const mcpServers: Record<string, unknown> = {};
        for (const cfg of mcpConfigs) {
          mcpServers[cfg.server_name] = JSON.parse(cfg.config_json);
        }
        options["mcpServers"] = mcpServers;
      }

      // Set up PermissionRequest hook for interactive approval
      if (!isBypass && project.permission_mode !== "dontAsk") {
        options["hooks"] = {
          PermissionRequest: [
            {
              matcher: ".*",
              hooks: [
                async (input: Record<string, unknown>) => {
                  const toolName = String(
                    input["tool_name"] ?? input["toolName"] ?? "unknown",
                  );
                  const toolInput =
                    (input["tool_input"] as Record<string, unknown>) ?? {};
                  const allowed = await permHandler.requestPermission(
                    toolName,
                    toolInput,
                  );
                  return allowed ? {} : { decision: "deny" };
                },
              ],
            },
          ],
        };
      }

      for await (const message of query({
        prompt: text,
        options: options as Parameters<typeof query>[0]["options"],
      })) {
        // Capture session ID from init message
        const msg = message as Record<string, unknown>;
        if (msg["type"] === "system" && msg["subtype"] === "init") {
          const sid = msg["session_id"];
          if (typeof sid === "string") {
            await sessionManager.updateClaudeSessionId(session.dbId, sid);
          }
        }

        await renderer.processMessage(msg);
      }

      await renderer.finish();
      await sessionManager.touchActivity(session.dbId);
    } catch (error) {
      if (abortController.signal.aborted) {
        await sender.updateText("Cancelled.");
      } else {
        logger.error({ error }, "Claude query failed");
        await sender.updateText(
          `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
        );
      }
    } finally {
      clearController(chatId);
    }
  });
}
