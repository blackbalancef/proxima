from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import tempfile
from collections.abc import AsyncIterator
from typing import Any

from proxima.logging import get_logger

logger = get_logger(__name__)


def _find_claude_binary() -> str:
    path = shutil.which("claude")
    if path:
        return path
    raise FileNotFoundError("claude CLI binary not found in PATH")


async def iter_claude_cli(
    *,
    prompt: str,
    cwd: str,
    permission_mode: str,
    resume_session_id: str | None,
    mcp_servers: dict[str, Any] | None,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    claude_bin = _find_claude_binary()

    args = [
        claude_bin,
        "--print",
        "--verbose",
        "--include-partial-messages",
        "--output-format", "stream-json",
        "--permission-mode", permission_mode,
    ]
    if model:
        args.extend(["--model", model])
    if resume_session_id:
        args.extend(["--resume", resume_session_id])

    mcp_tmpfile: str | None = None
    if mcp_servers:
        mcp_config = {"mcpServers": mcp_servers}
        fd, mcp_tmpfile = tempfile.mkstemp(suffix=".json", prefix="proxima-mcp-")
        os.write(fd, json.dumps(mcp_config).encode())
        os.close(fd)
        args.extend(["--mcp-config", mcp_tmpfile])

    logger.info(
        "claude_cli_start",
        cwd=cwd,
        permission_mode=permission_mode,
        resume=resume_session_id is not None,
        mcp_servers=list(mcp_servers.keys()) if mcp_servers else [],
        model=model,
        prompt_len=len(prompt),
    )

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )

    try:
        assert proc.stdin is not None
        try:
            proc.stdin.write(prompt.encode())
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            logger.warning("stdin_write_failed", error=str(exc))
            await proc.wait()
            stderr_bytes = await proc.stderr.read() if proc.stderr else b""
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            raise RuntimeError(
                f"claude CLI died before accepting input: {stderr_text[:300] or exc}"
            ) from exc
        finally:
            proc.stdin.close()

        assert proc.stdout is not None
        message_count = 0
        async for line in proc.stdout:
            line_str = line.decode().strip()
            if not line_str:
                continue
            try:
                msg = json.loads(line_str)
            except json.JSONDecodeError:
                logger.debug("cli_non_json_line", line=line_str[:200])
                continue
            message_count += 1
            yield msg

        await proc.wait()

        if proc.returncode and proc.returncode != 0:
            stderr_bytes = await proc.stderr.read() if proc.stderr else b""
            stderr_text = stderr_bytes.decode(errors="replace").strip()
            logger.warning(
                "claude_cli_stderr",
                returncode=proc.returncode,
                stderr=stderr_text[:500],
                message_count=message_count,
            )
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}: {stderr_text[:300] or 'no stderr'}"
            )

        logger.info("claude_cli_done", message_count=message_count, returncode=proc.returncode)
    except asyncio.CancelledError:
        logger.info("claude_cli_cancelled")
        try:
            proc.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass
        raise
    finally:
        if mcp_tmpfile:
            try:
                os.unlink(mcp_tmpfile)
            except OSError:
                pass
