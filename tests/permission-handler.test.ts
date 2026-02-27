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

// Mock keyboard builder
vi.mock("../src/telegram/keyboard-builder.js", () => ({
  buildPermissionKeyboard: vi.fn().mockReturnValue({ inline_keyboard: [] }),
}));

import { PermissionHandler } from "../src/claude/permission-handler.js";

function createMockApi() {
  return {
    sendMessage: vi
      .fn()
      .mockResolvedValue({ message_id: 100 }),
    editMessageText: vi.fn().mockResolvedValue(true),
  } as unknown as ConstructorParameters<typeof PermissionHandler>[0];
}

describe("PermissionHandler", () => {
  let api: ReturnType<typeof createMockApi>;
  let handler: PermissionHandler;
  const chatId = 123;

  beforeEach(() => {
    vi.useFakeTimers();
    api = createMockApi();
    handler = new PermissionHandler(api, chatId);
  });

  afterEach(() => {
    handler.cleanup();
    vi.useRealTimers();
  });

  describe("requestPermission", () => {
    it("sends a permission request message", async () => {
      // Start the request but don't await it — it blocks until user responds
      const promise = handler.requestPermission("Bash", {
        command: "npm test",
      });

      // Let the sendMessage promise resolve
      await vi.advanceTimersByTimeAsync(0);

      expect(api.sendMessage).toHaveBeenCalledTimes(1);
      const callArgs = (api.sendMessage as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(callArgs[0]).toBe(chatId);
      expect(callArgs[1]).toContain("Bash");
      expect(callArgs[1]).toContain("npm test");

      // Now allow it
      const handled = await handler.handleCallback(
        `perm:allow:${chatId}:1`,
        async () => {},
      );
      expect(handled).toBe(true);

      const result = await promise;
      expect(result).toBe(true);
    });

    it("resolves false when denied", async () => {
      const promise = handler.requestPermission("Write", {
        file_path: "/tmp/test",
      });

      await vi.advanceTimersByTimeAsync(0);

      await handler.handleCallback(
        `perm:deny:${chatId}:1`,
        async () => {},
      );

      const result = await promise;
      expect(result).toBe(false);
    });

    it("auto-allows after 'allow all session'", async () => {
      const promise1 = handler.requestPermission("Read", {});
      await vi.advanceTimersByTimeAsync(0);

      await handler.handleCallback(
        `perm:allow_all:${chatId}:1`,
        async () => {},
      );
      await promise1;

      // Second request should auto-allow
      const result = await handler.requestPermission("Write", {});
      expect(result).toBe(true);

      // sendMessage should only have been called once (for the first request)
      expect(api.sendMessage).toHaveBeenCalledTimes(1);
    });

    it("times out after 5 minutes and resolves false", async () => {
      const promise = handler.requestPermission("Bash", { command: "rm -rf" });

      // Advance past the 5-minute timeout
      await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 100);

      const result = await promise;
      expect(result).toBe(false);
    });
  });

  describe("handleCallback", () => {
    it("returns false for non-perm callbacks", async () => {
      const result = await handler.handleCallback(
        "mode:plan",
        async () => {},
      );
      expect(result).toBe(false);
    });

    it("returns false for unknown request IDs", async () => {
      const result = await handler.handleCallback(
        "perm:allow:999:99",
        async () => {},
      );
      expect(result).toBe(false);
    });

    it("edits the permission message with status", async () => {
      const promise = handler.requestPermission("Read", {
        file_path: "/test.ts",
      });
      await vi.advanceTimersByTimeAsync(0);

      await handler.handleCallback(
        `perm:allow:${chatId}:1`,
        async () => {},
      );
      await promise;

      expect(api.editMessageText).toHaveBeenCalledWith(
        chatId,
        100,
        "✅ Allowed: Read",
      );
    });

    it("calls answerCallback on success", async () => {
      const answerCb = vi.fn().mockResolvedValue(undefined);

      const promise = handler.requestPermission("Bash", {});
      await vi.advanceTimersByTimeAsync(0);

      await handler.handleCallback(`perm:allow:${chatId}:1`, answerCb);
      await promise;

      expect(answerCb).toHaveBeenCalledTimes(1);
    });
  });

  describe("resetAllowAll", () => {
    it("resets session auto-allow", async () => {
      // Set allow-all via callback
      const promise = handler.requestPermission("Read", {});
      await vi.advanceTimersByTimeAsync(0);
      await handler.handleCallback(
        `perm:allow_all:${chatId}:1`,
        async () => {},
      );
      await promise;

      handler.resetAllowAll();

      // Next request should NOT auto-allow
      const promise2 = handler.requestPermission("Read", {});
      await vi.advanceTimersByTimeAsync(0);

      // sendMessage should be called again
      expect(api.sendMessage).toHaveBeenCalledTimes(2);

      // Clean up — deny to resolve
      await handler.handleCallback(
        `perm:deny:${chatId}:2`,
        async () => {},
      );
      await promise2;
    });
  });

  describe("cleanup", () => {
    it("resolves all pending requests with false", async () => {
      const promise1 = handler.requestPermission("Read", {});
      const promise2 = handler.requestPermission("Write", {});

      await vi.advanceTimersByTimeAsync(0);

      handler.cleanup();

      expect(await promise1).toBe(false);
      expect(await promise2).toBe(false);
    });
  });
});
