import { downloadToTemp, oggToMp3, cleanupTemp } from "../../voice/ffmpeg.js";
import { transcribeAudio } from "../../voice/transcribe.js";
import { logger } from "../../utils/logger.js";
import { handleMessage } from "./message.js";
import type { BotContext } from "../context.js";

export async function handleVoice(ctx: BotContext): Promise<void> {
  const voice = ctx.message?.voice;
  if (!voice) return;

  const chatId = ctx.chat?.id;
  if (!chatId) return;

  const transcribeMsg = await ctx.reply("🎙️ Transcribing...");
  let oggPath: string | null = null;
  let mp3Path: string | null = null;

  try {
    // Get file from Telegram
    const file = await ctx.api.getFile(voice.file_id);
    const fileUrl = `https://api.telegram.org/file/bot${ctx.api.token}/${file.file_path}`;

    // Download and convert
    oggPath = await downloadToTemp(fileUrl, "ogg");
    mp3Path = await oggToMp3(oggPath);

    // Transcribe
    const text = await transcribeAudio(mp3Path);

    // Update status and show transcription
    await ctx.api.editMessageText(
      transcribeMsg.chat.id,
      transcribeMsg.message_id,
      `🎙️ "${text}"`,
    );

    // Create a fake text message context and forward to message handler
    // by injecting the transcribed text into the message object
    const fakeCtx = Object.create(ctx) as BotContext;
    Object.defineProperty(fakeCtx, "message", {
      value: { ...ctx.message, text },
      writable: false,
    });
    await handleMessage(fakeCtx);
  } catch (error) {
    logger.error({ error }, "Voice processing failed");
    await ctx.api.editMessageText(
      transcribeMsg.chat.id,
      transcribeMsg.message_id,
      `Voice error: ${error instanceof Error ? error.message : "Unknown error"}`,
    );
  } finally {
    if (oggPath) await cleanupTemp(oggPath);
    if (mp3Path) await cleanupTemp(mp3Path);
  }
}
