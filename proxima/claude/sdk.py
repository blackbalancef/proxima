from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from proxima.logging import get_logger

logger = get_logger(__name__)

PermissionHook = Callable[[str, dict[str, Any]], Awaitable[bool]]


def _load_sdk_symbols() -> dict[str, Any]:
    try:
        import claude_agent_sdk as sdk_mod  # noqa: F811
    except Exception as exc:  # noqa: BLE001
        logger.error("sdk_import_failed", error=str(exc))
        raise RuntimeError(
            "claude-agent-sdk import failed. Reinstall package and verify runtime version."
        ) from exc

    query = getattr(sdk_mod, "query", None)
    allow = getattr(sdk_mod, "PermissionResultAllow", None)
    deny = getattr(sdk_mod, "PermissionResultDeny", None)
    options_cls = getattr(sdk_mod, "ClaudeAgentOptions", None) or getattr(
        sdk_mod, "ClaudeCodeOptions", None
    )

    if not query or not allow or not deny:
        raise RuntimeError(
            "claude-agent-sdk is installed, but required symbols were not found "
            "(query / PermissionResultAllow / PermissionResultDeny)."
        )
    if not options_cls:
        raise RuntimeError(
            "claude-agent-sdk is installed, but no compatible options class was found "
            "(expected ClaudeAgentOptions or ClaudeCodeOptions)."
        )

    logger.debug("sdk_loaded", options_class=options_cls.__name__)
    return {
        "query": query,
        "options": options_cls,
        "allow": allow,
        "deny": deny,
    }


async def iter_claude_query(
    *,
    prompt: str,
    cwd: str,
    permission_mode: str,
    resume_session_id: str | None,
    mcp_servers: dict[str, Any] | None,
    permission_hook: PermissionHook | None,
    model: str | None = None,
) -> AsyncIterator[Any]:
    sdk = _load_sdk_symbols()

    can_use_tool_fn = None
    if permission_hook is not None:
        allow_cls = sdk["allow"]
        deny_cls = sdk["deny"]

        async def _can_use_tool(tool_name: str, tool_input: dict[str, Any], _context: Any) -> Any:
            allowed = await permission_hook(tool_name, tool_input)
            logger.debug(
                "permission_resolved", tool=tool_name, allowed=allowed
            )
            return allow_cls() if allowed else deny_cls()

        can_use_tool_fn = _can_use_tool

    options_kwargs: dict[str, Any] = {
        "cwd": cwd,
        "permission_mode": permission_mode,
    }
    if resume_session_id:
        options_kwargs["resume"] = resume_session_id
    if mcp_servers:
        options_kwargs["mcp_servers"] = mcp_servers
    if can_use_tool_fn is not None:
        options_kwargs["can_use_tool"] = can_use_tool_fn
    if model:
        options_kwargs["model"] = model

    logger.info(
        "claude_query_start",
        cwd=cwd,
        permission_mode=permission_mode,
        resume=resume_session_id is not None,
        mcp_servers=list(mcp_servers.keys()) if mcp_servers else [],
        model=model,
        prompt_len=len(prompt),
    )

    options = sdk["options"](**options_kwargs)
    query = sdk["query"]

    message_count = 0
    async for message in query(prompt=prompt, options=options):
        message_count += 1
        yield message

    logger.info("claude_query_done", message_count=message_count)
