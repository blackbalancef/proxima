import { query } from "@anthropic-ai/claude-agent-sdk";
import { config } from "../../config.js";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

export async function handleMessage(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text;
  if (!text) return;

  const chatId = ctx.chat?.id;
  logger.info({ chatId, text: text.slice(0, 100) }, "Incoming message");

  const statusMsg = await ctx.reply("⏳ Thinking...");

  try {
    let resultText = "";

    for await (const message of query({
      prompt: text,
      options: {
        cwd: config.workDir,
        permissionMode: "bypassPermissions",
        allowDangerouslySkipPermissions: true,
      },
    })) {
      if ("result" in message) {
        resultText = message.result;
      }
    }

    if (!resultText) {
      resultText = "(No response from Claude)";
    }

    // Split long messages (Telegram limit is 4096 chars)
    const chunks = splitMessage(resultText, 4000);
    // Edit the first "thinking" message with the first chunk
    await ctx.api.editMessageText(
      statusMsg.chat.id,
      statusMsg.message_id,
      chunks[0]!,
      { parse_mode: undefined },
    );

    // Send remaining chunks as new messages
    for (let i = 1; i < chunks.length; i++) {
      await ctx.reply(chunks[i]!);
    }
  } catch (error) {
    logger.error({ error }, "Claude query failed");
    await ctx.api.editMessageText(
      statusMsg.chat.id,
      statusMsg.message_id,
      `Error: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  }
}

function splitMessage(text: string, maxLen: number): string[] {
  if (text.length <= maxLen) return [text];

  const chunks: string[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      chunks.push(remaining);
      break;
    }

    // Try to split at newline
    let splitIdx = remaining.lastIndexOf("\n", maxLen);
    if (splitIdx < maxLen / 2) {
      // No good newline found — split at space
      splitIdx = remaining.lastIndexOf(" ", maxLen);
    }
    if (splitIdx < maxLen / 2) {
      // No good space found — hard split
      splitIdx = maxLen;
    }

    chunks.push(remaining.slice(0, splitIdx));
    remaining = remaining.slice(splitIdx).trimStart();
  }

  return chunks;
}
