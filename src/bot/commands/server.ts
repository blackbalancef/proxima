import { hostname, platform, release, totalmem, freemem, cpus } from "os";
import type { BotContext } from "../context.js";

/** /server — Show server information */
export async function serverCommand(ctx: BotContext): Promise<void> {
  const memTotal = (totalmem() / 1024 / 1024 / 1024).toFixed(1);
  const memFree = (freemem() / 1024 / 1024 / 1024).toFixed(1);
  const uptime = formatUptime(process.uptime());

  await ctx.reply(
    [
      `Host: ${hostname()}`,
      `Platform: ${platform()} ${release()}`,
      `CPUs: ${cpus().length}`,
      `Memory: ${memFree}/${memTotal} GB free`,
      `Node: ${process.version}`,
      `Uptime: ${uptime}`,
      `PID: ${process.pid}`,
    ].join("\n"),
  );
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
}
