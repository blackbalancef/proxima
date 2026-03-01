from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx


async def download_to_temp(url: str, ext: str) -> Path:
    with NamedTemporaryFile(prefix="proxima-", suffix=f".{ext}", delete=False) as temp:
        temp_path = Path(temp.name)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        await asyncio.to_thread(temp_path.write_bytes, response.content)

    return temp_path


async def ogg_to_mp3(ogg_path: Path) -> Path:
    with NamedTemporaryFile(prefix="proxima-", suffix=".mp3", delete=False) as temp:
        mp3_path = Path(temp.name)

    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(ogg_path),
        str(mp3_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {stderr.decode('utf-8', errors='ignore')}")

    return mp3_path


async def cleanup_temp(path: Path) -> None:
    try:
        await asyncio.to_thread(path.unlink, True)
    except Exception:
        return
