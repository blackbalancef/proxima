import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock logger before importing module
vi.mock("../src/utils/logger.js", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { SequentialQueue } from "../src/utils/queue.js";

describe("SequentialQueue", () => {
  let queue: SequentialQueue;

  beforeEach(() => {
    queue = new SequentialQueue();
  });

  it("executes a single task", async () => {
    const result: number[] = [];
    queue.enqueue(1, async () => {
      result.push(1);
    });

    // Let microtasks run
    await vi.waitFor(() => expect(result).toEqual([1]));
  });

  it("executes tasks for the same key sequentially", async () => {
    const result: number[] = [];

    queue.enqueue(1, async () => {
      await delay(50);
      result.push(1);
    });

    queue.enqueue(1, async () => {
      await delay(10);
      result.push(2);
    });

    queue.enqueue(1, async () => {
      result.push(3);
    });

    await vi.waitFor(() => expect(result).toEqual([1, 2, 3]), {
      timeout: 500,
    });
  });

  it("executes tasks for different keys concurrently", async () => {
    const result: string[] = [];

    queue.enqueue(1, async () => {
      await delay(50);
      result.push("a");
    });

    queue.enqueue(2, async () => {
      result.push("b");
    });

    // Key 2 should finish first since key 1 has delay
    await vi.waitFor(() => expect(result.length).toBe(2), { timeout: 500 });
    expect(result[0]).toBe("b");
    expect(result[1]).toBe("a");
  });

  it("continues processing after a task throws", async () => {
    const result: number[] = [];

    queue.enqueue(1, async () => {
      throw new Error("boom");
    });

    queue.enqueue(1, async () => {
      result.push(2);
    });

    await vi.waitFor(() => expect(result).toEqual([2]), { timeout: 500 });
  });

  it("cleans up the queue map after all tasks complete", async () => {
    const done = vi.fn();

    queue.enqueue(42, async () => {
      done();
    });

    await vi.waitFor(() => expect(done).toHaveBeenCalled());
    // Internal state should be clean - enqueue a new task to verify it works
    queue.enqueue(42, async () => {
      done();
    });

    await vi.waitFor(() => expect(done).toHaveBeenCalledTimes(2));
  });
});

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
