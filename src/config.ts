import { z } from "zod";
import "dotenv/config";

const configSchema = z.object({
  telegramBotToken: z.string().min(1),
  anthropicApiKey: z.string().min(1),
  allowedUserIds: z
    .string()
    .transform((s) => s.split(",").map((id) => Number(id.trim())))
    .pipe(z.array(z.number().int().positive())),
  workDir: z.string().default(process.cwd()),
  databaseUrl: z.string().min(1),
  openaiApiKey: z.string().optional(),
  logLevel: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export type Config = z.infer<typeof configSchema>;

export const config = configSchema.parse({
  telegramBotToken: process.env["TELEGRAM_BOT_TOKEN"],
  anthropicApiKey: process.env["ANTHROPIC_API_KEY"],
  allowedUserIds: process.env["ALLOWED_USER_IDS"],
  workDir: process.env["WORK_DIR"],
  databaseUrl: process.env["DATABASE_URL"],
  openaiApiKey: process.env["OPENAI_API_KEY"],
  logLevel: process.env["LOG_LEVEL"],
});
