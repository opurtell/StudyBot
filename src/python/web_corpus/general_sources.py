"""Fetch the general open references (Open RN, LITFL ECG Library) for the web corpus.

Run on a machine that can reach the sites, from the repo root:

    PYTHONPATH=src/python python3 -m web_corpus.general_sources fetch openrn [--limit N]
    PYTHONPATH=src/python python3 -m web_corpus.general_sources fetch litfl [--limit N]
    PYTHONPATH=src/python python3 -m web_corpus.general_sources list

Each page becomes one JSON document in ``data/general_refs/<source>/``. Only pathophysiology, physiology and ECG
recognition text is kept: treatment, medication, nursing and procedure sections are dropped, because the ACTAS CMGs
govern those. Images are never kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from paths import GENERAL_REFS_DIR

SOURCE_TYPE = "general_reference"
USER_AGENT = "StudyBot-corpus-fetch/1.0 (free non-commercial paramedic study app; https://study.paramedtools.com)"
REQUEST_DELAY = 1.0
MIN_DOC_CHARS = 300


@dataclass(frozen=True)
class GeneralSource:
    id: str
    name: str
    licence: str
    licence_url: str
    home_url: str
    commercial_use: bool


SOURCES: dict[str, GeneralSource] = {
    "openrn": GeneralSource(
        id="openrn",
        name="Open RN",
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        home_url="https://www.cvtc.edu/experience-cvtc/learning/open-rn",
        commercial_use=True,
    ),
    "litfl": GeneralSource(
        id="litfl",
        name="LITFL ECG Library",
        licence="CC BY-NC-SA 4.0",
        licence_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
        home_url="https://litfl.com/ecg-library/",
        commercial_use=False,
    ),
}


@dataclass(frozen=True)
class Book:
    code: str
    slug: str
    title: str
    editors: str
    section: str
    chapter_pattern: str | None = None


OPENRN_BOOKS = (
    Book("HA", "healthalts", "Health Alterations", "Kimberly Ernstmeyer and Elizabeth Christman", "Pathophysiology"),
    Book("NAS", "nursingadvancedskills", "Nursing Advanced Skills", "Kimberly Ernstmeyer and Elizabeth Christman",
         "ECGs", chapter_pattern=r"^7\.\d"),
)
PRESSBOOKS_ROOT = "https://wtcs.pressbooks.pub"
LITFL_ROOT = "https://litfl.com"
LITFL_INDEXES = ("/ecg-library/", "/ecg-library/basics/", "/ecg-library/diagnosis/")

EXCLUDED_HEADING = re.compile(
    r"\b(medications?|medicines?|pharmacolog\w*|drugs?|doses?|dosing|treatments?|management|managing|interventions?"
    r"|nursing|nclex|learning activit\w*|learning objectives?|glossary|references?|further reading|bibliography"
    r"|patient education|health teaching|care plans?|planning|implementation|evaluation|outcome identification"
    r"|expected outcomes|critical thinking|case stud\w*|clinical judg\w*|checklists?|procedures?|therap\w*|surg\w*"
    r"|related|see also|acknowledg\w*|authors?|credits?|resources|attributions?|licen[cs]e|quiz\w*|prevention"
    r"|precautions|documentation|delegation|safety considerations)\b",
    re.IGNORECASE,
)
EXCLUDED_CHAPTER = re.compile(
    r"\b(preface|about this book|introduction to|learning activities|glossary|appendix|answer key|nursing process"
    r"|references|acknowledg\w*|index|licen[cs]e|version history|review)\b",
    re.IGNORECASE,
)
EXCLUDED_LITFL_SLUG = re.compile(r"(^ecg-library|^top-\d+|quiz|^ecg-case|^ecg-exigency|^category|^tag|^author|^about)")

_SKIP_TAGS = {"script", "style", "figure", "figcaption", "img", "iframe", "nav", "aside", "footer", "form", "button",
              "svg", "noscript", "video", "audio", "picture", "header", "select", "math"}
_BLOCK_TAGS = {"p", "div", "section", "article", "blockquote", "ul", "ol", "table", "dl", "dt", "dd"}
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "param",
              "track"}


class _MarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.list_depth = 0
        self.cell = False

    def _newline(self, n: int = 1) -> None:
        text = "".join(self.out)
        trailing = len(text) - len(text.rstrip("\n"))
        if text and trailing < n:
            self.out.append("\n" * (n - trailing))

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _VOID_TAGS:
            if tag == "br" and not self.skip:
                self.out.append("\n")
            return
        if self.skip or tag in _SKIP_TAGS:
            self.skip += 1
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._newline(2)
            self.out.append("#" * int(tag[1]) + " ")
        elif tag == "li":
            self._newline()
            self.out.append("  " * max(self.list_depth - 1, 0) + "- ")
        elif tag in ("ul", "ol"):
            self.list_depth += 1
            self._newline()
        elif tag in ("td", "th"):
            self.out.append(" | " if self.cell else "")
            self.cell = True
        elif tag == "tr":
            self._newline()
            self.cell = False
        elif tag in _BLOCK_TAGS:
            self._newline(2)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        if self.skip:
            self.skip -= 1
            return
        if re.fullmatch(r"h[1-6]", tag):
            self._newline(2)
        elif tag in ("ul", "ol"):
            self.list_depth = max(self.list_depth - 1, 0)
            self._newline(2)
        elif tag == "li":
            self._newline()
        elif tag in _BLOCK_TAGS:
            self._newline(2)

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        self.out.append(re.sub(r"\s+", " ", data))


def _tidy_line(line: str) -> str:
    match = re.match(r"^( *)(#+ |- )?\s*(.*)$", line)
    indent, marker, rest = match.group(1), match.group(2) or "", match.group(3)
    if not rest:
        return ""
    return f"{indent if marker == '- ' else ''}{marker}{re.sub(r' {2,}', ' ', rest)}"


def html_to_markdown(html: str) -> str:
    parser = _MarkdownParser()
    parser.feed(html)
    parser.close()
    lines = [line.rstrip() for line in "".join(parser.out).splitlines()]
    text = "\n".join(_tidy_line(line) for line in lines)
    text = re.sub(r"^\s*-\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s*$", "", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def keep_recognition_sections(markdown: str) -> str:
    out: list[str] = []
    dropping: int | None = None
    for line in markdown.splitlines():
        match = _MD_HEADING.match(line)
        if match:
            level = len(match.group(1))
            if dropping is not None and level <= dropping:
                dropping = None
            if dropping is None and EXCLUDED_HEADING.search(match.group(2)):
                dropping = level
        if dropping is None:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def strip_empty_headings(markdown: str) -> str:
    lines = markdown.splitlines()

    def has_content(i: int, level: int) -> bool:
        for line in lines[i + 1:]:
            match = _MD_HEADING.match(line)
            if match and len(match.group(1)) <= level:
                return False
            if line.strip() and not match:
                return True
        return False

    kept = [line for i, line in enumerate(lines)
            if not (m := _MD_HEADING.match(line)) or has_content(i, len(m.group(1)))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() + "\n"


def clean(markdown: str) -> str:
    return strip_empty_headings(keep_recognition_sections(markdown))


def _slug_id(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:80]


def make_document(source: GeneralSource, *, doc_id: str, number: str, title: str, section: str, url: str,
                  attribution: str, markdown: str, fetched_at: str) -> dict | None:
    content = clean(markdown)
    body = "\n".join(l for l in content.splitlines() if not _MD_HEADING.match(l)).strip()
    if len(body) < MIN_DOC_CHARS:
        return None
    return {
        "id": doc_id,
        "source": source.id,
        "source_type": SOURCE_TYPE,
        "number": number,
        "title": title,
        "section": section,
        "url": url,
        "licence": source.licence,
        "licence_url": source.licence_url,
        "attribution": attribution,
        "commercial_use": source.commercial_use,
        "fetched_at": fetched_at,
        "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_markdown": content,
    }


def openrn_attribution(book: Book, chapter_title: str, url: str) -> str:
    return (f"\"{chapter_title}\" from {book.title} by Open Resources for Nursing (Open RN), edited by {book.editors}, "
            f"WisTech Open ({url}), licensed under CC BY 4.0. Adapted into quiz questions; Australian spelling and "
            f"terminology applied.")


def litfl_attribution(title: str, authors: str | None, url: str) -> str:
    by = f" by {authors}" if authors else ""
    return (f"\"{title}\"{by}, LITFL ECG Library, Life in the Fast Lane ({url}), licensed under CC BY-NC-SA 4.0. "
            f"Adapted into quiz questions, which are shared under the same licence.")


class Fetcher:
    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.last = 0.0

    def get(self, url: str) -> str:
        wait = self.last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8", errors="replace")
        finally:
            self.last = time.monotonic()

    def get_json(self, url: str):
        return json.loads(self.get(url))


_CHAPTER_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*)\s+")


def _pressbooks_chapters(fetcher: Fetcher, book: Book) -> list[dict]:
    toc = fetcher.get_json(f"{PRESSBOOKS_ROOT}/{book.slug}/wp-json/pressbooks/v2/toc")
    chapters = []
    for part in toc.get("parts") or []:
        for chapter in part.get("chapters") or []:
            chapters.append(chapter)
    return chapters


def _chapter_html(fetcher: Fetcher, book: Book, chapter: dict) -> str:
    if chapter.get("id") is not None:
        try:
            data = fetcher.get_json(f"{PRESSBOOKS_ROOT}/{book.slug}/wp-json/pressbooks/v2/chapters/{chapter['id']}")
            rendered = ((data.get("content") or {}).get("rendered")) or ""
            if rendered.strip():
                return rendered
        except (urllib.error.URLError, json.JSONDecodeError, ValueError):
            pass
    return extract_main_html(fetcher.get(chapter["link"]))


def fetch_openrn(fetcher: Fetcher, out_dir: Path, limit: int | None, fetched_at: str) -> list[dict]:
    source = SOURCES["openrn"]
    docs: list[dict] = []
    for book in OPENRN_BOOKS:
        for chapter in _pressbooks_chapters(fetcher, book):
            if limit is not None and len(docs) >= limit:
                return docs
            title = unescape(re.sub(r"<[^>]+>", "", str(chapter.get("title") or ""))).strip()
            if not title or EXCLUDED_CHAPTER.search(title) or EXCLUDED_HEADING.search(title):
                continue
            if book.chapter_pattern and not re.match(book.chapter_pattern, title):
                continue
            number_match = _CHAPTER_NUMBER.match(title)
            number = f"{book.code} {number_match.group(1)}" if number_match else book.code
            url = chapter.get("link") or f"{PRESSBOOKS_ROOT}/{book.slug}/chapter/{chapter.get('slug')}/"
            try:
                html = _chapter_html(fetcher, book, chapter)
            except urllib.error.URLError as exc:
                print(f"skip {url}: {exc}", file=sys.stderr)
                continue
            doc = make_document(
                source,
                doc_id=f"OPENRN_{book.code}_{_slug_id(chapter.get('slug') or title)}",
                number=number,
                title=_CHAPTER_NUMBER.sub("", title).strip() or title,
                section=book.section,
                url=url,
                attribution=openrn_attribution(book, title, url),
                markdown=html_to_markdown(html),
                fetched_at=fetched_at,
            )
            if doc:
                write_document(out_dir, doc)
                docs.append(doc)
    return docs


_MAIN_PATTERNS = (
    re.compile(r"<div[^>]+class=\"[^\"]*\bentry-content\b[^\"]*\"[^>]*>(.*?)<(?:footer|div[^>]+class=\"[^\"]*\b(?:sharedaddy|post-tags|entry-footer|jp-relatedposts)\b)", re.S),
    re.compile(r"<section[^>]+data-type=\"chapter\"[^>]*>(.*?)</section>\s*(?:</div>|<nav)", re.S),
    re.compile(r"<article\b[^>]*>(.*?)</article>", re.S),
    re.compile(r"<main\b[^>]*>(.*?)</main>", re.S),
)


def extract_main_html(html: str) -> str:
    for pattern in _MAIN_PATTERNS:
        match = pattern.search(html)
        if match and len(match.group(1)) > 500:
            return match.group(1)
    body = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S)
    return body.group(1) if body else html


def page_title(html: str) -> str:
    for pattern in (r"<h1[^>]*>(.*?)</h1>", r"<meta property=\"og:title\" content=\"([^\"]+)\"", r"<title>(.*?)</title>"):
        match = re.search(pattern, html, re.S | re.I)
        if match:
            title = unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
            return re.sub(r"\s*[•|–-]\s*LITFL.*$", "", title).strip()
    return ""


def page_authors(html: str) -> str | None:
    names = [unescape(n).strip() for n in re.findall(r"<meta name=\"author\" content=\"([^\"]+)\"", html, re.I)]
    names = [n for n in names if n and n.lower() not in ("litfl", "admin")]
    return ", ".join(dict.fromkeys(names)) or None


def litfl_links(html: str) -> list[str]:
    links: list[str] = []
    for href in re.findall(r"href=\"(https://litfl\.com/[a-z0-9-]+/)\"", extract_main_html(html)):
        slug = href.rstrip("/").rsplit("/", 1)[-1]
        if EXCLUDED_LITFL_SLUG.search(slug) or href in links:
            continue
        links.append(href)
    return links


def fetch_litfl(fetcher: Fetcher, out_dir: Path, limit: int | None, fetched_at: str) -> list[dict]:
    source = SOURCES["litfl"]
    links: list[str] = []
    for index in LITFL_INDEXES:
        try:
            html = fetcher.get(f"{LITFL_ROOT}{index}")
        except urllib.error.URLError as exc:
            print(f"skip index {index}: {exc}", file=sys.stderr)
            continue
        links.extend(l for l in litfl_links(html) if l not in links)
    docs: list[dict] = []
    for url in links:
        if limit is not None and len(docs) >= limit:
            break
        try:
            html = fetcher.get(url)
        except urllib.error.URLError as exc:
            print(f"skip {url}: {exc}", file=sys.stderr)
            continue
        if "ECG" not in html or "creativecommons.org/licenses/by-nc-sa" not in html.lower():
            continue
        title = page_title(html)
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if not title:
            continue
        doc = make_document(
            source,
            doc_id=f"LITFL_{_slug_id(slug)}",
            number="LITFL",
            title=title,
            section="ECGs",
            url=url,
            attribution=litfl_attribution(title, page_authors(html), url),
            markdown=html_to_markdown(extract_main_html(html)),
            fetched_at=fetched_at,
        )
        if doc:
            write_document(out_dir, doc)
            docs.append(doc)
    return docs


def write_document(out_dir: Path, doc: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{doc['id']}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_documents(root: Path = GENERAL_REFS_DIR, exclude: frozenset[str] = frozenset()) -> list[dict]:
    docs: list[dict] = []
    if not root.is_dir():
        return docs
    for source_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if source_dir.name in exclude:
            continue
        if source_dir.name not in SOURCES:
            raise ValueError(f"{source_dir}: unknown general source {source_dir.name!r}")
        for path in sorted(source_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("source") != source_dir.name or data.get("source_type") != SOURCE_TYPE:
                raise ValueError(f"{path.name}: not a {source_dir.name} general reference")
            docs.append(data)
    return docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("source", choices=sorted(SOURCES))
    fetch.add_argument("--limit", type=int, default=None, help="stop after N documents (for a trial)")
    fetch.add_argument("--out", type=Path, default=GENERAL_REFS_DIR)
    fetch.add_argument("--keep", action="store_true", help="keep documents from an earlier fetch")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    if args.command == "list":
        for doc in load_documents():
            body = len(doc["content_markdown"])
            print(f"{doc['source']:6} {doc['section']:16} {doc['number']:10} {body:6} {doc['title']}")
        return 0

    out_dir = args.out / args.source
    if out_dir.is_dir() and not args.keep:
        for old in out_dir.glob("*.json"):
            old.unlink()
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    fetcher = Fetcher()
    run = fetch_openrn if args.source == "openrn" else fetch_litfl
    docs = run(fetcher, out_dir, args.limit, fetched_at)
    chars = sum(len(d["content_markdown"]) for d in docs)
    print(json.dumps({"source": args.source, "documents": len(docs), "chars": chars, "out": str(out_dir)}, indent=2))
    return 0 if docs else 1


if __name__ == "__main__":
    sys.exit(main())
