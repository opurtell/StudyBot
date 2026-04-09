from __future__ import annotations

import re
from typing import Any

_INLINE_HEADING_PATTERN = re.compile(r"(?<=[^\s#])(?=#{4,6}\s)")
_INLINE_SPACED_HEADING_PATTERN = re.compile(r"(?<=\S)\s+(?=#{4,6}\s)")
_MALFORMED_BOLD_LABEL_PATTERN = re.compile(r"\*\*\s*([^*\n]+?)\s*:\s*\*\*")
_ADJACENT_BOLD_PATTERN = re.compile(r"(?<=\*\*)(?=\*\*)")
_MISSING_SPACE_AFTER_BOLD_PATTERN = re.compile(r"(?<=:\*\*)(?=[^\s*\n])")
_GLUED_LIST_ITEM_PATTERN = re.compile(r"(?<=[A-Za-z0-9%)])(?=-\s+\*\*)")
_GLUED_BOLD_PATTERN = re.compile(r"(?<=[A-Za-z0-9])(?=\*\*[^*\n]+:\*\*)")
_GLUED_SENTENCE_PATTERN = re.compile(r"([.!?])([A-Z][a-z])")

_ICP_LIST_ITEM_PATTERN = re.compile(r"(?m)^\s*-\s*\*\*ICP[^*]*\*\*")
_ICP_BLOCK_PATTERN = re.compile(
    r"(?m)^(?P<indent>\s*-\s*\*\*ICP[^*]*\*\*.*?)\n"
    r"(?P<sub>(?:\s+-\s.*\n|\s{2,}[^-\s].*\n)*)"
)


def _normalise_bold_label(match: re.Match[str]) -> str:
    return f"**{match.group(1).strip()}:**"


def normalise_markdown_syntax(content: str) -> str:
    if not content:
        return content
    normalised = content
    if "#" in normalised:
        normalised = _INLINE_HEADING_PATTERN.sub("\n\n", normalised)
        normalised = _INLINE_SPACED_HEADING_PATTERN.sub("\n\n", normalised)
    if "**" in normalised:
        normalised = _MALFORMED_BOLD_LABEL_PATTERN.sub(_normalise_bold_label, normalised)
        normalised = _ADJACENT_BOLD_PATTERN.sub(" ", normalised)
        normalised = _MISSING_SPACE_AFTER_BOLD_PATTERN.sub(" ", normalised)
        normalised = _GLUED_BOLD_PATTERN.sub(" ", normalised)
        normalised = _GLUED_LIST_ITEM_PATTERN.sub("\n", normalised)
    normalised = _GLUED_SENTENCE_PATTERN.sub(r"\1 \2", normalised)
    return normalised


def has_icp_content(text: str) -> bool:
    """Return True if the text contains ICP-specific list items."""
    return bool(_ICP_LIST_ITEM_PATTERN.search(text))


def strip_icp_content(text: str) -> str:
    """Remove ICP-marked list items and their indented sub-bullets."""
    result = _ICP_BLOCK_PATTERN.sub("", text)
    # Clean up double blank lines left behind
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def normalise_markdown_payload(value: Any) -> Any:
    if isinstance(value, str):
        return normalise_markdown_syntax(value)
    if isinstance(value, list):
        return [normalise_markdown_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            key: normalise_markdown_payload(item)
            for key, item in value.items()
        }
    return value
