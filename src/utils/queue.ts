import { logger } from "./logger.js";

type QueueTask = () => Promise<void>;

/**
 * Per-key sequential queue. Ensures messages for the same project
 * are processed one at a time, in order.
 */
export class SequentialQueue {
  private queues = new Map<number, QueueTask[]>();
  private running = new Set<number>();

  enqueue(key: number, task: QueueTask): void {
    const queue = this.queues.get(key) ?? [];
    queue.push(task);
    this.queues.set(key, queue);
    void this.process(key);
  }

  private async process(key: number): Promise<void> {
    if (this.running.has(key)) return;
    this.running.add(key);

    try {
      while (true) {
        const queue = this.queues.get(key);
        if (!queue || queue.length === 0) {
          this.queues.delete(key);
          break;
        }
        const task = queue.shift()!;
        try {
          await task();
        } catch (error) {
          logger.error({ error, key }, "Queue task failed");
        }
      }
    } finally {
      this.running.delete(key);
    }
  }
}

export const messageQueue = new SequentialQueue();
