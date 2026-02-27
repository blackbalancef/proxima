/**
 * Tracks active AbortControllers per chat for query cancellation.
 */
const activeControllers = new Map<number, AbortController>();

export function getAbortController(chatId: number): AbortController {
  // Abort any existing query for this chat
  const existing = activeControllers.get(chatId);
  if (existing) {
    existing.abort();
  }

  const controller = new AbortController();
  activeControllers.set(chatId, controller);
  return controller;
}

export function cancelQuery(chatId: number): boolean {
  const controller = activeControllers.get(chatId);
  if (controller) {
    controller.abort();
    activeControllers.delete(chatId);
    return true;
  }
  return false;
}

export function clearController(chatId: number): void {
  activeControllers.delete(chatId);
}
