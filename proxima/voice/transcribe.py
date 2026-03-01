from __future__ import annotations

from pathlib import Path

from openai import AsyncOpenAI

_client: AsyncOpenAI | None = None


def _get_client(api_key: str) -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def transcribe_audio(
    file_path: Path, api_key: str | None, *, language: str | None = None
) -> str:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured; voice transcription is unavailable")

    client = _get_client(api_key)
    kwargs: dict[str, object] = {"model": "whisper-1"}
    if language:
        kwargs["language"] = language
    with file_path.open("rb") as file_obj:
        response = await client.audio.transcriptions.create(file=file_obj, **kwargs)  # type: ignore[arg-type]
    return response.text
