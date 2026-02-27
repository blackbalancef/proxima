import { Api } from "grammy";
import { buildPermissionKeyboard } from "../telegram/keyboard-builder.js";
import { logger } from "../utils/logger.js";

interface PendingPermission {
  resolve: (allowed: boolean) => void;
  toolName: string;
  telegramMessageId?: number;
}

/**
 * Manages permission requests from Claude SDK.
 * When Claude asks to use a tool, sends inline buttons to Telegram
 * and waits for user response via a deferred Promise.
 */
export class PermissionHandler {
  private pending = new Map<string, PendingPermission>();
  private counter = 0;
  private allowAllSession = false;

  constructor(
    private api: Api,
    private chatId: number,
  ) {}

  /** Generate a unique request ID */
  private nextId(): string {
    return `${this.chatId}:${++this.counter}`;
  }

  /**
   * Called by the SDK when a tool needs permission.
   * Returns a Promise that resolves when the user responds.
   */
  async requestPermission(
    toolName: string,
    toolInput: Record<string, unknown>,
  ): Promise<boolean> {
    // Auto-allow if user chose "Allow All" for this session
    if (this.allowAllSession) {
      logger.debug({ toolName }, "Auto-allowed (session allow all)");
      return true;
    }

    const requestId = this.nextId();

    // Format tool info for display
    let detail = "";
    if ("command" in toolInput) {
      detail = `\nCommand: ${String(toolInput["command"]).slice(0, 200)}`;
    } else if ("file_path" in toolInput) {
      detail = `\nFile: ${toolInput["file_path"]}`;
    } else if ("pattern" in toolInput) {
      detail = `\nPattern: ${toolInput["pattern"]}`;
    }

    const text = `🔒 Permission request\n\nTool: ${toolName}${detail}`;

    const keyboard = buildPermissionKeyboard(requestId);

    return new Promise<boolean>((resolve) => {
      // Send the permission request message
      void this.api
        .sendMessage(this.chatId, text, { reply_markup: keyboard })
        .then((msg) => {
          const pending = this.pending.get(requestId);
          if (pending) {
            pending.telegramMessageId = msg.message_id;
          }
        })
        .catch((error) => {
          logger.error({ error }, "Failed to send permission request");
          resolve(false);
        });

      this.pending.set(requestId, { resolve, toolName });

      // Timeout after 5 minutes
      setTimeout(() => {
        if (this.pending.has(requestId)) {
          this.pending.delete(requestId);
          resolve(false);
          logger.warn({ requestId, toolName }, "Permission request timed out");
        }
      }, 5 * 60 * 1000);
    });
  }

  /**
   * Handle callback from inline button press.
   * Returns true if this callback was handled.
   */
  async handleCallback(
    data: string,
    answerCallback: () => Promise<void>,
  ): Promise<boolean> {
    const parts = data.split(":");
    if (parts[0] !== "perm") return false;

    const action = parts[1];
    const requestId = parts.slice(2).join(":");
    const pending = this.pending.get(requestId);
    if (!pending) return false;

    this.pending.delete(requestId);

    let allowed = false;
    let statusText: string;

    switch (action) {
      case "allow":
        allowed = true;
        statusText = `✅ Allowed: ${pending.toolName}`;
        break;
      case "deny":
        allowed = false;
        statusText = `❌ Denied: ${pending.toolName}`;
        break;
      case "allow_all":
        allowed = true;
        this.allowAllSession = true;
        statusText = `✅ Allowed all for this session: ${pending.toolName}`;
        break;
      default:
        return false;
    }

    // Update the message to show the result
    if (pending.telegramMessageId) {
      try {
        await this.api.editMessageText(
          this.chatId,
          pending.telegramMessageId,
          statusText,
        );
      } catch {
        // Message may have been deleted
      }
    }

    await answerCallback();
    pending.resolve(allowed);
    return true;
  }

  /** Reset session-level auto-allow */
  resetAllowAll(): void {
    this.allowAllSession = false;
  }

  /** Clean up pending requests */
  cleanup(): void {
    for (const [, pending] of this.pending) {
      pending.resolve(false);
    }
    this.pending.clear();
  }
}

// Active permission handlers per chat
const handlers = new Map<number, PermissionHandler>();

export function getPermissionHandler(
  api: Api,
  chatId: number,
): PermissionHandler {
  let handler = handlers.get(chatId);
  if (!handler) {
    handler = new PermissionHandler(api, chatId);
    handlers.set(chatId, handler);
  }
  return handler;
}

export function findPermissionHandler(
  chatId: number,
): PermissionHandler | undefined {
  return handlers.get(chatId);
}
