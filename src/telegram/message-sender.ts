import { Api } from "grammy";
import { logger } from "../utils/logger.js";

const MAX_MESSAGE_LENGTH = 4000;

/**
 * Manages sending and editing Telegram messages with auto-splitting.
 */
export class MessageSender {
  private chatId: number;
  private api: Api;
  private messages: number[] = [];
  private lastText = "";

  constructor(api: Api, chatId: number) {
    this.api = api;
    this.chatId = chatId;
  }

  /** Set the initial "thinking" message to edit later */
  setInitialMessage(messageId: number): void {
    this.messages = [messageId];
    this.lastText = "";
  }

  /** Update the displayed text (handles splitting across multiple messages) */
  async updateText(text: string): Promise<void> {
    if (text === this.lastText) return;
    this.lastText = text;

    const chunks = splitMessage(text, MAX_MESSAGE_LENGTH);

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i]!;
      if (i < this.messages.length) {
        // Edit existing message
        try {
          await this.api.editMessageText(this.chatId, this.messages[i]!, chunk);
        } catch (error: unknown) {
          // Ignore "message not modified" errors (content unchanged)
          if (isTelegramError(error, "message is not modified")) continue;
          throw error;
        }
      } else {
        // Send new message for overflow
        try {
          const sent = await this.api.sendMessage(this.chatId, chunk);
          this.messages.push(sent.message_id);
        } catch (error) {
          logger.error({ error }, "Failed to send overflow message");
        }
      }
    }
  }

  /** Send a standalone status message (tool activity, etc.) */
  async sendStatus(text: string): Promise<number> {
    const sent = await this.api.sendMessage(this.chatId, text);
    return sent.message_id;
  }

  /** Delete a status message */
  async deleteMessage(messageId: number): Promise<void> {
    try {
      await this.api.deleteMessage(this.chatId, messageId);
    } catch {
      // Message may already be deleted
    }
  }
}

function isTelegramError(error: unknown, substring: string): boolean {
  if (error && typeof error === "object" && "description" in error) {
    return String((error as { description: string }).description).includes(
      substring,
    );
  }
  return false;
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
      splitIdx = remaining.lastIndexOf(" ", maxLen);
    }
    if (splitIdx < maxLen / 2) {
      splitIdx = maxLen;
    }

    chunks.push(remaining.slice(0, splitIdx));
    remaining = remaining.slice(splitIdx).trimStart();
  }

  return chunks;
}
