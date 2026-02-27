import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock logger
vi.mock("../src/utils/logger.js", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

// Mock message-sender module
vi.mock("../src/telegram/message-sender.js", () => ({
  MessageSender: vi.fn(),
}));

import { StreamRenderer } from "../src/claude/stream-renderer.js";

function createMockSender() {
  return {
    updateText: vi.fn().mockResolvedValue(undefined),
    sendStatus: vi.fn().mockResolvedValue(999),
    deleteMessage: vi.fn().mockResolvedValue(undefined),
  };
}

describe("StreamRenderer", () => {
  let sender: ReturnType<typeof createMockSender>;
  let renderer: StreamRenderer;

  beforeEach(() => {
    vi.useFakeTimers();
    sender = createMockSender();
    renderer = new StreamRenderer(sender as never);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("processMessage — result messages", () => {
    it("flushes text immediately for result messages", async () => {
      await renderer.processMessage({ result: "Final answer" });

      expect(sender.updateText).toHaveBeenCalledWith("Final answer");
    });
  });

  describe("processMessage — assistant messages", () => {
    it("schedules debounced update for text blocks", async () => {
      await renderer.processMessage({
        type: "assistant",
        content: [{ type: "text", text: "Hello world" }],
      });

      // Not yet flushed
      expect(sender.updateText).not.toHaveBeenCalled();

      // Advance past debounce timer
      vi.advanceTimersByTime(600);

      expect(sender.updateText).toHaveBeenCalledWith("Hello world");
    });

    it("shows tool status for tool_use blocks", async () => {
      await renderer.processMessage({
        type: "assistant",
        content: [
          {
            type: "tool_use",
            name: "Read",
            input: { file_path: "/src/index.ts" },
          },
        ],
      });

      expect(sender.sendStatus).toHaveBeenCalledWith(
        "📖 Read /src/index.ts...",
      );
    });

    it("shows tool status with command for Bash", async () => {
      await renderer.processMessage({
        type: "assistant",
        content: [
          {
            type: "tool_use",
            name: "Bash",
            input: { command: "npm test" },
          },
        ],
      });

      expect(sender.sendStatus).toHaveBeenCalledWith("⚡ Bash npm test...");
    });

    it("shows generic icon for unknown tools", async () => {
      await renderer.processMessage({
        type: "assistant",
        content: [
          {
            type: "tool_use",
            name: "CustomTool",
            input: {},
          },
        ],
      });

      expect(sender.sendStatus).toHaveBeenCalledWith("🔧 CustomTool...");
    });
  });

  describe("processMessage — tool results", () => {
    it("clears tool status on tool_result messages", async () => {
      // First show a tool status
      await renderer.processMessage({
        type: "assistant",
        content: [{ type: "tool_use", name: "Read", input: {} }],
      });

      // Then process tool result
      await renderer.processMessage({ type: "tool_result" });

      expect(sender.deleteMessage).toHaveBeenCalledWith(999);
    });
  });

  describe("flush", () => {
    it("cancels pending debounce and sends immediately", async () => {
      await renderer.processMessage({
        type: "assistant",
        content: [{ type: "text", text: "Partial text" }],
      });

      await renderer.flush();

      expect(sender.updateText).toHaveBeenCalledWith("Partial text");
    });

    it("does not send if no text accumulated", async () => {
      await renderer.flush();
      expect(sender.updateText).not.toHaveBeenCalled();
    });
  });

  describe("finish", () => {
    it("calls flush", async () => {
      await renderer.processMessage({ result: "Done" });
      await renderer.finish();

      expect(sender.updateText).toHaveBeenCalledWith("Done");
    });
  });
});
