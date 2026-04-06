"""
Angular Compiled Template Parser
Parses Angular compiled template instructions from minified JS bundles.
Handles both direct method calls (.j41, .EFF, .k0s, .nrm) and chained calls
where the method name is on the initial call and subsequent calls are bare (N, args).
"""

import re
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_TEMPLATE_RE = re.compile(r"template\s*:\s*function\s*\(\s*\w+\s*,\s*\w+\s*\)\s*\{")

_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
        "fa-li",
        "ion-icon",
    }
)


def _find_template_boundaries(content: str, start: int) -> Tuple[int, int]:
    depth = 0
    in_string = False
    escape_next = False
    i = start
    while i < len(content):
        ch = content[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if ch == "\\" and in_string:
            escape_next = True
            i += 1
            continue
        if ch == '"':
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    return start, len(content)


def _extract_template_blocks(content: str) -> List[str]:
    blocks = []
    for match in _TEMPLATE_RE.finditer(content):
        _, end = _find_template_boundaries(content, match.end() - 1)
        blocks.append(content[match.start() : end])
    return blocks


def _decode_unicode_escapes(text: str) -> str:
    return (
        text.replace("\\u2019", "\u2019")
        .replace("\\u2018", "\u2018")
        .replace("\\u201c", "\u201c")
        .replace("\\u201d", "\u201d")
        .replace("\\u2013", "\u2013")
        .replace("\\u2014", "\u2014")
        .replace("\\u2010", "\u2010")
        .replace("\\u00b0", "\u00b0")
        .replace("\\u2265", "\u2265")
        .replace("\\u2264", "\u2264")
        .replace("\\u2260", "\u2260")
        .replace("\\u2022", "\u2022")
        .replace("\\u2026", "\u2026")
        .replace("\\u00a0", "\u00a0")
        .replace("\\u03bc", "\u03bc")
        .replace("\\u00b2", "\u00b2")
        .replace("\\u2192", "\u2192")
        .replace("\\u2190", "\u2190")
        .replace("\\u2261", "\u2261")
        .replace("\\u00bd", "\u00bd")
        .replace("\\u00bc", "\u00bc")
        .replace("\\u00be", "\u00be")
        .replace("\\u00d7", "\u00d7")
        .replace("\\u00f7", "\u00f7")
        .replace("\\u00b1", "\u00b1")
        .replace("\\u2248", "\u2248")
        .replace("\\u0394", "\u0394")
        .replace("\\u226b", "\u226b")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


def _extract_template_body(block: str) -> str:
    cond_re = re.compile(r"\d+&\w+&&\(")
    body_start = block.find("{")
    if body_start < 0:
        return block
    body = block[body_start + 1 :]
    if body.endswith("}"):
        body = body[:-1]
    m = cond_re.match(body)
    if m:
        inner = body[m.end() :]
        if inner.endswith(")"):
            inner = inner[:-1]
        return inner
    return body


def _tokenize_template(block: str) -> List[Dict[str, any]]:
    tokens = []
    i = 0
    n = len(block)
    last_method = None

    while i < n:
        while i < n and block[i] in " \t\r\n":
            i += 1
        if i >= n:
            break

        if block[i] == ".":
            j = i + 1
            while j < n and (block[j].isalnum() or block[j] == "_"):
                j += 1
            method = block[i + 1 : j]
            last_method = method
            i = j
            if i >= n or block[i] != "(":
                continue
        elif block[i] == "(":
            method = last_method
        else:
            i += 1
            continue

        i += 1
        args = []
        depth = 0
        arg_start = i
        in_str = False
        esc = False

        while i < n:
            ch = block[i]
            if esc:
                esc = False
                i += 1
                continue
            if ch == "\\" and in_str:
                esc = True
                i += 1
                continue
            if ch == '"':
                in_str = not in_str
                i += 1
                continue
            if in_str:
                i += 1
                continue
            if ch == "(":
                depth += 1
                i += 1
                continue
            if ch == ")":
                if depth == 0:
                    arg_text = block[arg_start:i].strip()
                    if arg_text:
                        args = [a.strip() for a in _split_args(arg_text)]
                    i += 1
                    break
                depth -= 1
                i += 1
                continue
            i += 1

        if method in ("EFF",) and len(args) >= 2:
            text_arg = args[1]
            if text_arg.startswith('"') and text_arg.endswith('"'):
                text = text_arg[1:-1]
                text = _decode_unicode_escapes(text)
                if len(text) >= 1:
                    tokens.append({"type": "text", "content": text})

        elif method in ("j41",) and len(args) >= 2:
            tag = args[1].strip('"')
            if tag:
                tokens.append({"type": "open", "tag": tag})

        elif method in ("k0s",) and len(args) == 0:
            tokens.append({"type": "close"})

        elif method in ("nrm",) and len(args) >= 2:
            tag = args[1].strip('"')
            if tag:
                tokens.append({"type": "self_closing", "tag": tag})

    return tokens


def _split_args(text: str) -> List[str]:
    args = []
    depth = 0
    in_str = False
    esc = False
    current = []

    for ch in text:
        if esc:
            esc = False
            current.append(ch)
            continue
        if ch == "\\" and in_str:
            esc = True
            current.append(ch)
            continue
        if ch == '"':
            in_str = not in_str
            current.append(ch)
            continue
        if in_str:
            current.append(ch)
            continue
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(ch)

    if current:
        args.append("".join(current))
    return args


class _HtmlBuilder:
    def __init__(self):
        self._parts: List[str] = []
        self._tag_stack: List[str] = []

    def open_element(self, tag: str):
        self._parts.append(f"<{tag}>")
        if tag not in _VOID_ELEMENTS:
            self._tag_stack.append(tag)

    def close_element(self):
        if self._tag_stack:
            tag = self._tag_stack.pop()
            self._parts.append(f"</{tag}>")

    def self_closing(self, tag: str):
        self._parts.append(f"<{tag} />")

    def text(self, content: str):
        self._parts.append(content)

    def build(self) -> str:
        while self._tag_stack:
            tag = self._tag_stack.pop()
            self._parts.append(f"</{tag}>")
        return "".join(self._parts)


def _parse_template_block(block: str) -> Optional[str]:
    body = _extract_template_body(block)
    tokens = _tokenize_template(body)
    builder = _HtmlBuilder()
    text_count = 0

    for token in tokens:
        if token["type"] == "text":
            builder.text(token["content"])
            text_count += 1
        elif token["type"] == "open":
            builder.open_element(token["tag"])
        elif token["type"] == "close":
            builder.close_element()
        elif token["type"] == "self_closing":
            builder.self_closing(token["tag"])

    if text_count == 0:
        return None
    return builder.build()


def parse_template_instructions(content: str) -> List[Dict[str, any]]:
    blocks = _extract_template_blocks(content)
    results = []
    for block in blocks:
        html = _parse_template_block(block)
        if html:
            results.append({"html": html, "raw_length": len(block)})
    return results


def extract_text_from_file(file_path: str) -> List[Dict[str, any]]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return []
    return parse_template_instructions(content)


_BOILERPLATE_HTML_PATTERNS = [
    re.compile(r"<span>More information<fa-icon\s*/?></span>"),
    re.compile(r"<section><h4>My Notes</h4><div></div></section>"),
    re.compile(
        r"<div><div><div><div><img[^>]*></div><div><span>Tap to zoom</span></div></div></div></div>"
    ),
    re.compile(r"<div><span>Tap to zoom</span></div>"),
    re.compile(
        r"<section><div><ion-button>Open print version</ion-button></div></section>"
    ),
    re.compile(r"<ion-button>Open print version</ion-button>"),
    re.compile(r"<content-header\s*/?>"),
    re.compile(r"<section-menu[^>]*>\s*</section-menu>"),
    re.compile(r"<print[^>]*>\s*</print>"),
    re.compile(r"<print\s*/?>"),
    re.compile(r"</?ion-content[^>]*>"),
    re.compile(r"</?ion-header[^>]*>"),
    re.compile(r"<ion-toolbar[^>]*>.*?</ion-toolbar>"),
    re.compile(r"<ion-buttons[^>]*>.*?</ion-buttons>"),
    re.compile(r"<ion-title[^>]*>.*?</ion-title>"),
    re.compile(r"<ion-back-button\s*/?>"),
    re.compile(r"<ion-tab-bar[^>]*>.*?</ion-tab-bar>"),
    re.compile(r"<ion-tab-button[^>]*>.*?</ion-tab-button>"),
]

_BOILERPLATE_MD_LINES = frozenset(
    {
        "More information",
        "#### My Notes",
        "Tap to zoom",
        "Open print version",
    }
)


def strip_boilerplate(html: str) -> str:
    for pattern in _BOILERPLATE_HTML_PATTERNS:
        html = pattern.sub("", html)
    html = re.sub(r"\n{3,}", "\n", html)
    return html.strip()


def strip_boilerplate_md(md: str) -> str:
    lines = md.split("\n")
    cleaned = [l for l in lines if l.strip() not in _BOILERPLATE_MD_LINES]
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def html_to_markdown(html: str) -> str:
    html = strip_boilerplate(html)
    md = html
    md = re.sub(
        r"<h([1-6])>(.*?)</h\1>", lambda m: "#" * int(m.group(1)) + " " + m.group(2), md
    )
    md = re.sub(r"<section[^>]*>", "\n", md)
    md = re.sub(r"</section>", "\n", md)
    md = re.sub(r"<p>", "\n", md)
    md = re.sub(r"</p>", "\n", md)
    md = re.sub(r"<ul>", "\n", md)
    md = re.sub(r"</ul>", "\n", md)
    md = re.sub(r"<fa-li>", "- ", md)
    md = re.sub(r"</fa-li>", "\n", md)
    md = re.sub(r"<li>", "\n- ", md)
    md = re.sub(r"</li>", "\n", md)
    md = re.sub(r"<fa-ordered-li>", "\n- ", md)
    md = re.sub(r"</fa-ordered-li>", "\n", md)
    md = re.sub(r"<fa-li-avf>", "- ", md)
    md = re.sub(r"</fa-li-avf>", "\n", md)
    md = re.sub(r"<ol>", "\n", md)
    md = re.sub(r"</ol>", "\n", md)
    md = re.sub(r"<div[^>]*>", "\n", md)
    md = re.sub(r"</div>", "\n", md)
    md = re.sub(r"<checklist-item[^>]*>", "\n- ", md)
    md = re.sub(r"</checklist-item>", "\n", md)
    md = re.sub(r"<ion-list[^>]*>", "\n", md)
    md = re.sub(r"</ion-list>", "\n", md)
    md = re.sub(r"<ion-item[^>]*>", "\n- ", md)
    md = re.sub(r"</ion-item>", "\n", md)
    md = re.sub(r"<strong>(.*?)</strong>", r"**\1**", md)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md)
    md = re.sub(r"<br\s*/?>", "\n", md)
    md = re.sub(r"</?table[^>]*>", "\n", md)
    md = re.sub(r"</tr>", "\n", md)
    md = re.sub(r"<t[hd][^>]*>", " ", md)
    md = re.sub(r"</t[hd]>", " ", md)
    md = re.sub(r"<button[^>]*>", " ", md)
    md = re.sub(r"</button>", " ", md)
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"([.!?])([-])", r"\1\n\2", md)
    return md.strip()
