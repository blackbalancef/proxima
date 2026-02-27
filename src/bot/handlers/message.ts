import { query } from "@anthropic-ai/claude-agent-sdk";
import { config } from "../../config.js";
import { sessionManager } from "../../claude/session-manager.js";
import { StreamRenderer } from "../../claude/stream-renderer.js";
import { MessageSender } from "../../telegram/message-sender.js";
import { projectRepo } from "../../db/repositories/project.js";
import { messageQueue } from "../../utils/queue.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function handleMessage(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text;
  if (!text) return;

  const chatId = ctx.chat?.id;
  if (!chatId) return;

  // Get or create default project
  let project = await projectRepo.findActiveByChat(chatId);
  if (!project) {
    project = await projectRepo.create({
      telegram_chat_id: chatId,
      name: "default",
      directory: config.workDir,
      is_active: true,
      permission_mode: "bypassPermissions",
    });
  }

  const projectId = project.id;

  // Enqueue for sequential processing per project
  messageQueue.enqueue(projectId, async () => {
    logger.info(
      { chatId, projectId, text: text.slice(0, 100) },
      "Processing message",
    );

    const statusMsg = await ctx.reply("⏳ Thinking...");
    const sender = new MessageSender(ctx.api, chatId);
    sender.setInitialMessage(statusMsg.message_id);
    const renderer = new StreamRenderer(sender);

    try {
      const session = await sessionManager.getOrCreate(projectId);

      const options: Record<string, unknown> = {
        cwd: project.directory,
        permissionMode: "bypassPermissions",
        allowDangerouslySkipPermissions: true,
      };

      // Resume session if we have a Claude session ID
      if (session.claudeSessionId) {
        options["resume"] = session.claudeSessionId;
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
      logger.error({ error }, "Claude query failed");
      await sender.updateText(
        `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  });
}
