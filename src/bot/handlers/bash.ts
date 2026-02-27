import { exec } from "child_process";
import { logger } from "../../utils/logger.js";
import type { BotContext } from "../context.js";

const MAX_OUTPUT = 4000;

/**
 * Handle messages starting with "!" as direct bash commands.
 * Example: "! ls -la" runs "ls -la" on the server.
 */
export async function handleBash(ctx: BotContext): Promise<void> {
  const text = ctx.message?.text;
  if (!text || !text.startsWith("!")) return;

  const command = text.slice(1).trim();
  if (!command) {
    await ctx.reply("Usage: ! <command>\nExample: ! ls -la");
    return;
  }

  const project = ctx.project;
  logger.info(
    { command, directory: project.directory },
    "Direct bash command",
  );

  const statusMsg = await ctx.reply(`⚡ Running: ${command.slice(0, 100)}...`);

  try {
    const { stdout, stderr } = await execPromise(command, {
      cwd: project.directory,
      timeout: 30_000,
    });

    const output = (stdout || stderr || "(no output)").slice(0, MAX_OUTPUT);
    await ctx.api.editMessageText(
      statusMsg.chat.id,
      statusMsg.message_id,
      `$ ${command}\n\n${output}`,
    );
  } catch (error) {
    const errMsg =
      error instanceof Error ? error.message : "Command failed";
    await ctx.api.editMessageText(
      statusMsg.chat.id,
      statusMsg.message_id,
      `$ ${command}\n\nError: ${errMsg.slice(0, MAX_OUTPUT)}`,
    );
  }
}

function execPromise(
  command: string,
  options: { cwd: string; timeout: number },
): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    exec(command, options, (error, stdout, stderr) => {
      if (error && !stdout && !stderr) {
        reject(error);
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}
