import { MessageSender } from "../telegram/message-sender.js";
import { logger } from "../utils/logger.js";

const TOOL_ICONS: Record<string, string> = {
  Read: "📖",
  Write: "✏️",
  Edit: "✏️",
  Bash: "⚡",
  Glob: "🔎",
  Grep: "🔍",
  WebSearch: "🌐",
  WebFetch: "🌐",
  Task: "🔀",
};

const DEBOUNCE_MS = 500;

/**
 * Renders Claude Agent SDK stream events to Telegram messages.
 * Accumulates text and debounces editMessageText calls.
 */
export class StreamRenderer {
  private sender: MessageSender;
  private accumulatedText = "";
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private statusMessageId: number | null = null;

  constructor(sender: MessageSender) {
    this.sender = sender;
  }

  /** Process a single SDK message from the stream */
  async processMessage(message: Record<string, unknown>): Promise<void> {
    // Result message — final text
    if ("result" in message && typeof message["result"] === "string") {
      this.accumulatedText = message["result"];
      await this.flush();
      return;
    }

    // Assistant message with content blocks
    if (message["type"] === "assistant" && Array.isArray(message["content"])) {
      for (const block of message["content"] as Record<string, unknown>[]) {
        if (block["type"] === "text" && typeof block["text"] === "string") {
          this.accumulatedText = block["text"];
          this.scheduleUpdate();
        } else if (block["type"] === "tool_use") {
          const toolName = String(block["name"] ?? "unknown");
          await this.showToolStatus(toolName, block["input"] as Record<string, unknown> | undefined);
        }
      }
      return;
    }

    // Tool result — clear tool status
    if (message["type"] === "tool_result" || message["type"] === "result") {
      await this.clearToolStatus();
    }
  }

  private async showToolStatus(
    toolName: string,
    input?: Record<string, unknown>,
  ): Promise<void> {
    const icon = TOOL_ICONS[toolName] ?? "🔧";
    let detail = "";

    if (input) {
      if ("file_path" in input) detail = ` ${input["file_path"]}`;
      else if ("command" in input)
        detail = ` ${String(input["command"]).slice(0, 60)}`;
      else if ("pattern" in input) detail = ` ${input["pattern"]}`;
      else if ("query" in input) detail = ` ${input["query"]}`;
    }

    const statusText = `${icon} ${toolName}${detail}...`;

    try {
      if (this.statusMessageId) {
        await this.sender.deleteMessage(this.statusMessageId);
      }
      this.statusMessageId = await this.sender.sendStatus(statusText);
    } catch (error) {
      logger.debug({ error }, "Failed to show tool status");
    }
  }

  private async clearToolStatus(): Promise<void> {
    if (this.statusMessageId) {
      await this.sender.deleteMessage(this.statusMessageId);
      this.statusMessageId = null;
    }
  }

  private scheduleUpdate(): void {
    if (this.debounceTimer) return;
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      void this.sender.updateText(this.accumulatedText || "⏳ Thinking...");
    }, DEBOUNCE_MS);
  }

  /** Force flush accumulated text to Telegram */
  async flush(): Promise<void> {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    await this.clearToolStatus();
    if (this.accumulatedText) {
      await this.sender.updateText(this.accumulatedText);
    }
  }

  /** Clean up on completion */
  async finish(): Promise<void> {
    await this.flush();
  }
}
