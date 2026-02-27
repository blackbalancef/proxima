import { InlineKeyboard } from "grammy";

export function buildPermissionKeyboard(requestId: string): InlineKeyboard {
  return new InlineKeyboard()
    .text("Allow", `perm:allow:${requestId}`)
    .text("Deny", `perm:deny:${requestId}`)
    .row()
    .text("Allow All Session", `perm:allow_all:${requestId}`);
}

export function buildModeKeyboard(): InlineKeyboard {
  return new InlineKeyboard()
    .text("Plan", "mode:plan")
    .text("Execute", "mode:execute");
}

export function buildProjectKeyboard(
  projects: Array<{ id: number; name: string; is_active: boolean }>,
): InlineKeyboard {
  const kb = new InlineKeyboard();
  for (const p of projects) {
    const prefix = p.is_active ? "▶ " : "";
    kb.text(`${prefix}${p.name}`, `project:switch:${p.id}`).row();
  }
  return kb;
}
