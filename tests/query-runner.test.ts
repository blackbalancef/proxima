import { describe, it, expect, beforeEach } from "vitest";
import {
  getAbortController,
  cancelQuery,
  clearController,
} from "../src/claude/query-runner.js";

describe("query-runner", () => {
  const chatId = 12345;

  beforeEach(() => {
    // Ensure clean state
    clearController(chatId);
  });

  describe("getAbortController", () => {
    it("returns a new AbortController", () => {
      const controller = getAbortController(chatId);
      expect(controller).toBeInstanceOf(AbortController);
      expect(controller.signal.aborted).toBe(false);
    });

    it("aborts the previous controller when called again", () => {
      const first = getAbortController(chatId);
      const second = getAbortController(chatId);

      expect(first.signal.aborted).toBe(true);
      expect(second.signal.aborted).toBe(false);
    });

    it("tracks controllers per chatId independently", () => {
      const ctrl1 = getAbortController(1);
      const ctrl2 = getAbortController(2);

      expect(ctrl1.signal.aborted).toBe(false);
      expect(ctrl2.signal.aborted).toBe(false);
    });
  });

  describe("cancelQuery", () => {
    it("aborts an active controller and returns true", () => {
      const controller = getAbortController(chatId);
      const result = cancelQuery(chatId);

      expect(result).toBe(true);
      expect(controller.signal.aborted).toBe(true);
    });

    it("returns false when no active controller exists", () => {
      const result = cancelQuery(999);
      expect(result).toBe(false);
    });

    it("removes the controller after cancelling", () => {
      getAbortController(chatId);
      cancelQuery(chatId);

      // Second cancel should return false
      const result = cancelQuery(chatId);
      expect(result).toBe(false);
    });
  });

  describe("clearController", () => {
    it("removes the controller without aborting", () => {
      const controller = getAbortController(chatId);
      clearController(chatId);

      expect(controller.signal.aborted).toBe(false);
      expect(cancelQuery(chatId)).toBe(false);
    });
  });
});
