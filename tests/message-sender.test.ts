import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock logger
vi.mock("../src/utils/logger.js", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { MessageSender } from "../src/telegram/message-sender.js";

function createMockApi() {
  return {
    editMessageText: vi.fn().mockResolvedValue(true),
    sendMessage: vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve({ message_id: Math.floor(Math.random() * 10000) }),
      ),
    deleteMessage: vi.fn().mockResolvedValue(true),
  } as unknown as ConstructorParameters<typeof MessageSender>[0];
}

describe("MessageSender", () => {
  let api: ReturnType<typeof createMockApi>;
  let sender: MessageSender;
  const chatId = 123;

  beforeEach(() => {
    api = createMockApi();
    sender = new MessageSender(api, chatId);
  });

  describe("updateText", () => {
    it("edits the initial message", async () => {
      sender.setInitialMessage(100);
      await sender.updateText("Hello");

      expect(api.editMessageText).toHaveBeenCalledWith(chatId, 100, "Hello");
    });

    it("skips update when text is unchanged", async () => {
      sender.setInitialMessage(100);
      await sender.updateText("Hello");
      await sender.updateText("Hello");

      expect(api.editMessageText).toHaveBeenCalledTimes(1);
    });

    it("sends a new message when no initial message is set", async () => {
      await sender.updateText("Hello");

      expect(api.sendMessage).toHaveBeenCalledWith(chatId, "Hello");
    });

    it("ignores 'message is not modified' errors", async () => {
      (api.editMessageText as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
        description: "Bad Request: message is not modified",
      });

      sender.setInitialMessage(100);
      // Should not throw
      await sender.updateText("Hello");
    });

    it("rethrows non-telegram errors", async () => {
      (api.editMessageText as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("network error"),
      );

      sender.setInitialMessage(100);
      await expect(sender.updateText("Hello")).rejects.toThrow("network error");
    });

    it("splits long messages into chunks", async () => {
      sender.setInitialMessage(100);

      // Create a message longer than 4000 chars
      const longText = "a".repeat(4500);
      await sender.updateText(longText);

      expect(api.editMessageText).toHaveBeenCalledTimes(1);
      expect(api.sendMessage).toHaveBeenCalledTimes(1);
    });
  });

  describe("sendStatus", () => {
    it("sends a status message and returns its ID", async () => {
      const mockId = 555;
      (api.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        message_id: mockId,
      });

      const id = await sender.sendStatus("Loading...");
      expect(id).toBe(mockId);
      expect(api.sendMessage).toHaveBeenCalledWith(chatId, "Loading...");
    });
  });

  describe("deleteMessage", () => {
    it("deletes a message", async () => {
      await sender.deleteMessage(200);
      expect(api.deleteMessage).toHaveBeenCalledWith(chatId, 200);
    });

    it("does not throw if message is already deleted", async () => {
      (api.deleteMessage as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("not found"),
      );

      await sender.deleteMessage(200);
      // Should not throw
    });
  });
});
