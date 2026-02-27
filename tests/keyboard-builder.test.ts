import { describe, it, expect } from "vitest";
import {
  buildPermissionKeyboard,
  buildModeKeyboard,
  buildProjectKeyboard,
} from "../src/telegram/keyboard-builder.js";

describe("keyboard-builder", () => {
  describe("buildPermissionKeyboard", () => {
    it("creates a keyboard with Allow, Deny, and Allow All buttons", () => {
      const kb = buildPermissionKeyboard("req:1");
      // InlineKeyboard stores data in .inline_keyboard
      const rows = (kb as unknown as { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> }).inline_keyboard;

      expect(rows.length).toBe(2);
      // First row: Allow + Deny
      expect(rows[0]!.length).toBe(2);
      expect(rows[0]![0]!.text).toBe("Allow");
      expect(rows[0]![0]!.callback_data).toBe("perm:allow:req:1");
      expect(rows[0]![1]!.text).toBe("Deny");
      expect(rows[0]![1]!.callback_data).toBe("perm:deny:req:1");
      // Second row: Allow All Session
      expect(rows[1]!.length).toBe(1);
      expect(rows[1]![0]!.text).toBe("Allow All Session");
      expect(rows[1]![0]!.callback_data).toBe("perm:allow_all:req:1");
    });
  });

  describe("buildModeKeyboard", () => {
    it("creates a keyboard with Plan and Execute buttons", () => {
      const kb = buildModeKeyboard();
      const rows = (kb as unknown as { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> }).inline_keyboard;

      expect(rows[0]!.length).toBe(2);
      expect(rows[0]![0]!.text).toBe("Plan");
      expect(rows[0]![0]!.callback_data).toBe("mode:plan");
      expect(rows[0]![1]!.text).toBe("Execute");
      expect(rows[0]![1]!.callback_data).toBe("mode:execute");
    });
  });

  describe("buildProjectKeyboard", () => {
    it("creates buttons for each project with active indicator", () => {
      const projects = [
        { id: 1, name: "alpha", is_active: true },
        { id: 2, name: "beta", is_active: false },
      ];

      const kb = buildProjectKeyboard(projects);
      const rows = (kb as unknown as { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> }).inline_keyboard;

      // grammY .row() adds a trailing empty row
      const nonEmptyRows = rows.filter((r) => r.length > 0);
      expect(nonEmptyRows.length).toBe(2);
      expect(nonEmptyRows[0]![0]!.text).toBe("▶ alpha");
      expect(nonEmptyRows[0]![0]!.callback_data).toBe("project:switch:1");
      expect(nonEmptyRows[1]![0]!.text).toBe("beta");
      expect(nonEmptyRows[1]![0]!.callback_data).toBe("project:switch:2");
    });

    it("handles empty project list", () => {
      const kb = buildProjectKeyboard([]);
      const rows = (kb as unknown as { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> }).inline_keyboard;
      const nonEmptyRows = rows.filter((r) => r.length > 0);
      expect(nonEmptyRows.length).toBe(0);
    });
  });
});
