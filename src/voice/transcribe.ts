import OpenAI from "openai";
import { createReadStream } from "fs";
import { config } from "../config.js";
import { logger } from "../utils/logger.js";

let client: OpenAI | null = null;

function getClient(): OpenAI {
  if (!client) {
    if (!config.openaiApiKey) {
      throw new Error("OPENAI_API_KEY not set — voice transcription unavailable");
    }
    client = new OpenAI({ apiKey: config.openaiApiKey });
  }
  return client;
}

/**
 * Transcribe an audio file using OpenAI Whisper API.
 */
export async function transcribeAudio(filePath: string): Promise<string> {
  const openai = getClient();

  logger.debug({ filePath }, "Transcribing audio");

  const response = await openai.audio.transcriptions.create({
    model: "whisper-1",
    file: createReadStream(filePath),
    language: "en",
  });

  logger.debug(
    { text: response.text.slice(0, 100) },
    "Transcription complete",
  );

  return response.text;
}
