from proxima.utils.markdown_to_html import markdown_to_html, strip_html_tags


def test_markdown_bold_and_italic() -> None:
    assert markdown_to_html("**bold** and *italic*") == "<b>bold</b> and <i>italic</i>"


def test_markdown_code_fence() -> None:
    assert (
        markdown_to_html("```py\nprint(1)\n```")
        == '<pre><code class="language-py">print(1)</code></pre>'
    )


def test_strip_html_tags() -> None:
    assert strip_html_tags("<b>x</b> &lt;y&gt; &amp; z") == "x <y> & z"


def test_unordered_list_dash() -> None:
    result = markdown_to_html("- first\n- second")
    assert "• first" in result
    assert "• second" in result


def test_unordered_list_asterisk() -> None:
    result = markdown_to_html("* one\n* two")
    assert "• one" in result
    assert "• two" in result


def test_ordered_list() -> None:
    result = markdown_to_html("1. alpha\n2. beta")
    assert "1. alpha" in result
    assert "2. beta" in result


def test_task_list_checked() -> None:
    result = markdown_to_html("- [x] done task")
    assert "[done]" in result
    assert "done task" in result


def test_task_list_unchecked() -> None:
    result = markdown_to_html("- [ ] todo task")
    assert "[ ]" in result
    assert "todo task" in result


def test_image_markdown() -> None:
    result = markdown_to_html("![screenshot](https://example.com/img.png)")
    assert "[Image: screenshot]" in result
    assert "https://example.com/img.png" in result
    assert "<a href=" in result


def test_image_empty_alt() -> None:
    result = markdown_to_html("![](https://example.com/img.png)")
    assert "[Image: image]" in result
