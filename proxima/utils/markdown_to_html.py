from __future__ import annotations

import re
from html import escape

_PLACEHOLDER_PREFIX = "\x00SLOT"
_PLACEHOLDER_SUFFIX = "\x00"


def markdown_to_html(markdown: str) -> str:
    slots: list[str] = []

    def add_slot(html: str) -> str:
        idx = len(slots)
        slots.append(html)
        return f"{_PLACEHOLDER_PREFIX}{idx}{_PLACEHOLDER_SUFFIX}"

    text = re.sub(
        r"```(\w*)\n([\s\S]*?)```",
        lambda m: add_slot(_render_fenced_code(m.group(1), m.group(2))),
        markdown,
    )
    text = re.sub(r"`([^`\n]+)`", lambda m: add_slot(f"<code>{escape(m.group(1))}</code>"), text)
    text = re.sub(
        r"(?:^\|.+\|$\n?){2,}",
        lambda m: add_slot(f"<pre>{escape(m.group(0).rstrip())}</pre>"),
        text,
        flags=re.MULTILINE,
    )

    # Images: ![alt](url) → clickable link (before regular links)
    def _render_image(m: re.Match[str]) -> str:
        alt = escape(m.group(1) or "image")
        url = escape(m.group(2))
        return add_slot(f'<a href="{url}">[Image: {alt}]</a>')

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _render_image, text)

    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: add_slot(f'<a href="{escape(m.group(2))}">{escape(m.group(1))}</a>'),
        text,
    )

    text = re.sub(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?/?>", "", text)
    text = re.sub(r"^\$\$$", "", text, flags=re.MULTILINE)
    text = escape(text)

    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    text = re.sub(
        r"(?:^&gt;[&gt;]* (.+)$\n?)+",
        _render_blockquote,
        text,
        flags=re.MULTILINE,
    )

    # Task lists: - [x] / - [ ]
    text = re.sub(r"^(\s*)[-*]\s+\[x\]\s+(.+)$", r"\1  [done] \2", text, flags=re.MULTILINE)
    text = re.sub(r"^(\s*)[-*]\s+\[ \]\s+(.+)$", r"\1  [ ] \2", text, flags=re.MULTILINE)

    # Unordered lists: - item or * item
    text = re.sub(r"^(\s*)[-*]\s+(.+)$", r"\1  • \2", text, flags=re.MULTILINE)

    # Ordered lists: 1. item
    text = re.sub(r"^(\s*)(\d+)\.\s+(.+)$", r"\1  \2. \3", text, flags=re.MULTILINE)

    text = re.sub(r"^---+$", "-", text, flags=re.MULTILINE)

    pattern = re.compile(f"{re.escape(_PLACEHOLDER_PREFIX)}(\\d+){re.escape(_PLACEHOLDER_SUFFIX)}")
    # Loop to resolve nested slots (e.g., inline code inside tables)
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(lambda m: slots[int(m.group(1))], text)
    return text


def strip_html_tags(html_text: str) -> str:
    return (
        re.sub(r"<[^>]+>", "", html_text)
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )


def _render_fenced_code(language: str, code: str) -> str:
    escaped = escape(code.rstrip("\n"))
    language_attr = f' class="language-{language}"' if language else ""
    return f"<pre><code{language_attr}>{escaped}</code></pre>"


def _render_blockquote(match: re.Match[str]) -> str:
    lines = [line for line in match.group(0).split("\n") if line]
    cleaned = [re.sub(r"^(?:&gt;)+ ", "", line) for line in lines]
    return f"<blockquote>{'\n'.join(cleaned)}</blockquote>"
