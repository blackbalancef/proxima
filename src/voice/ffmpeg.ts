import ffmpeg from "fluent-ffmpeg";
import { createWriteStream } from "fs";
import { unlink } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { randomUUID } from "crypto";

/**
 * Convert OGG voice file to MP3 for Whisper API.
 * Returns path to the MP3 file (caller must clean up).
 */
export async function oggToMp3(oggPath: string): Promise<string> {
  const mp3Path = join(tmpdir(), `proxima-${randomUUID()}.mp3`);

  return new Promise((resolve, reject) => {
    ffmpeg(oggPath)
      .toFormat("mp3")
      .on("end", () => resolve(mp3Path))
      .on("error", reject)
      .save(mp3Path);
  });
}

/**
 * Download a file from a URL to a temp path.
 */
export async function downloadToTemp(
  url: string,
  ext: string,
): Promise<string> {
  const tempPath = join(tmpdir(), `proxima-${randomUUID()}.${ext}`);
  const response = await fetch(url);
  if (!response.ok || !response.body) {
    throw new Error(`Failed to download: ${response.status}`);
  }

  const fileStream = createWriteStream(tempPath);
  const reader = response.body.getReader();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fileStream.write(value);
    }
    fileStream.end();
  } catch (error) {
    fileStream.destroy();
    await unlink(tempPath).catch(() => {});
    throw error;
  }

  return new Promise((resolve, reject) => {
    fileStream.on("finish", () => resolve(tempPath));
    fileStream.on("error", reject);
  });
}

export async function cleanupTemp(path: string): Promise<void> {
  await unlink(path).catch(() => {});
}
