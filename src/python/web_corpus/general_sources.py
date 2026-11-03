"""Fetch the general open references (Open RN, LITFL ECG Library) for the web corpus.

Open RN comes from the NCBI Bookshelf open-access bulk download (``pub/litarch``), not the book websites.

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
import csv
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path

from paths import GENERAL_REFS_DIR

SOURCE_TYPE = "general_reference"
USER_AGENT = "StudyBot-corpus-fetch/1.0 (free non-commercial paramedic study app; https://study.paramedtools.com)"
REQUEST_DELAY = 1.0
RETRY_AFTER = 15.0
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
    accession: str
    title: str
    editors: str
    section: str
    chapter_pattern: str
    excluded: tuple[tuple[str, str], ...] = ()


OPENRN_BOOKS = (
    Book("HA", "NBK613078", "Health Alterations", "Kimberly Ernstmeyer and Elizabeth Christman", "Pathophysiology",
         chapter_pattern=r"^(?:[3-9]|1[01])\.\d+$",
         excluded=(("4.3", "Cancer"), ("6.8", "Lung Cancer"), ("8.10", "Urinary Incontinence"),
                   ("8.12", "Benign Prostate Hypertrophy"), ("8.13", "Bladder and Prostate Cancer"), ("10.5", "Amputation"),
                   ("10.7", "Osteoarthritis"), ("10.8", "Osteoporosis"), ("11.12", "Irritable Bowel Syndrome"),
                   ("11.14", "Hernia"))),
    Book("NAS", "NBK594492", "Nursing Advanced Skills", "Kimberly Ernstmeyer and Elizabeth Christman", "ECGs",
         chapter_pattern=r"^7\.[2-4]$"),
)
LITARCH_ROOT = "https://ftp.ncbi.nlm.nih.gov/pub/litarch"
NCBI_BOOKS_ROOT = "https://www.ncbi.nlm.nih.gov/books"
OPENRN_LICENCE_URL = re.compile(r"^https?://creativecommons\.org/licenses/by/4\.0/?$")
LITFL_ROOT = "https://litfl.com"
LITFL_INDEXES = ("/ecg-library/basics/", "/ecg-library/diagnosis/")

EXCLUDED_HEADING = re.compile(
    r"\b(medications?|medicines?|pharmacolog\w*|drugs?|doses?|dosing|treatments?|management|managing|interventions?"
    r"|nursing|nclex|learning activit\w*|learning objectives?|glossary|references?|(?:advanced|further) reading|bibliography"
    r"|patient education|health teaching|care plans?|planning|implementation|evaluation|outcome identification"
    r"|expected outcomes|critical thinking|case stud\w*|clinical judg\w*|checklists?|procedures?|therap\w*|surg\w*"
    r"|related|see also|acknowledg\w*|authors?|credits?|resources|attributions?|licen[cs]e|quiz\w*|prevention"
    r"|precautions|documentation|delegation|safety considerations|associated persons|(?:clinical |ecg )?cases?$|critical care|criteria for \w+ insertion|indications for \w+|deep dive|literature"
    r"|lifestyle|rehabilitation|psychosocial|promotion|watchful waiting|transfusions?)\b",
    re.IGNORECASE,
)
EXCLUDED_CHAPTER = re.compile(
    r"\b(preface|about this book|introduction|learning activit\w*|glossary|appendix|answer key|nursing process"
    r"|references|acknowledg\w*|index|licen[cs]e|version history|review questions|assessment|checklist|spotlight)\b",
    re.IGNORECASE,
)
EXCLUDED_LITFL_SLUG = re.compile(r"(^ecg-library|^top-\d+|quiz|^ecg-case|^ecg-exigency|^category|^tag|^author|^about"
                                 r"|^ecg-exam-template|video-lectures|online-ecg-courses|^super-axis-man|^omi-replacing|^paediatric-ecg-basics)")
LITFL_INDEX_END = re.compile(r"<h[1-6][^>]*>(?:(?!</h).)*?(?:Search the ECG Library|Advanced Reading|Further Reading)", re.S)
LITFL_LICENCE = re.compile(r"<a href=\"https://creativecommons\.org/licenses/by-nc-sa/4\.0/?\"[^>]*rel=\"license\"")

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
_JUNK_LINE = re.compile(r"^(?:image credit|ecg courtesy|(?:many |with )?thanks to\b.*\b(?:ecg|image|tracing)|…\s*more\b|\.\.\.\s*more\b"
                        r"|ecg \d+[a-z]?$)", re.IGNORECASE)
_PMID = re.compile(r"\s*\[PMID:? \d+\]")


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
        if dropping is None and not _JUNK_LINE.match(line.strip()):
            out.append(_PMID.sub("", line))
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
            f"Chippewa Valley Technical College, via NCBI Bookshelf ({url}), licensed under CC BY 4.0. Adapted into quiz "
            f"questions; Australian spelling and terminology applied.")


def litfl_attribution(title: str, authors: str | None, url: str) -> str:
    by = f" by {authors}" if authors else ""
    return (f"\"{title}\"{by}, LITFL ECG Library, Life in the Fast Lane ({url}), licensed under CC BY-NC-SA 4.0. "
            f"Adapted into quiz questions, which are shared under the same licence.")


class Fetcher:
    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self.last = 0.0

    def get(self, url: str, retry_after: float = RETRY_AFTER) -> str:
        wait = self.last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429) or not retry_after:
                raise
        finally:
            self.last = time.monotonic()
        time.sleep(retry_after)
        return self.get(url, retry_after=0)

    def get_bytes(self, url: str) -> bytes:
        wait = self.last + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=300) as res:
                return res.read()
        finally:
            self.last = time.monotonic()


_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_BITS_SKIP = {"fig", "fig-group", "caption", "graphic", "inline-graphic", "media", "boxed-text", "ref-list", "fn-group",
              "fn", "label", "supplementary-material", "table-wrap-foot", "alternatives", "object-id"}
_BITS_HTML = {"p": "p", "list": "ul", "list-item": "li", "table": "table", "thead": "thead", "tbody": "tbody", "tr": "tr",
              "td": "td", "th": "th", "def-list": "ul", "def-item": "li"}
_FIGURE_REF = re.compile(r"\b(?:Figure|Fig\.)\s*\d+(?:\.\d+)*|^(?:View|Watch)\b|YouTube|\bvideos?\b|\b(?:this|the) (?:figure|image)\b"
                         r"|\bimage of\b")
_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}
_ACRONYMS = {"ECG", "ECGS", "IV", "AV", "SA", "QRS", "ST", "PR", "QT"}


def drop_excluded_columns(table: ET.Element) -> None:
    rows = list(table.iter("tr"))
    if not rows or any(cell.get("colspan", "1") != "1" for row in rows for cell in row):
        return
    header = ["".join(cell.itertext()) for cell in rows[0]]
    dropped = {i for i, text in enumerate(header) if EXCLUDED_HEADING.search(text)}
    for row in rows:
        for i, cell in reversed(list(enumerate(list(row)))):
            if i in dropped:
                row.remove(cell)
    for parent in table.iter():
        for row in [r for r in parent if r.tag == "tr" and r is not rows[0]]:
            if len(row) and EXCLUDED_HEADING.search("".join(row[0].itertext())):
                parent.remove(row)


def bits_to_html(elem: ET.Element, depth: int) -> str:
    tag = elem.tag
    if tag == "table":
        drop_excluded_columns(elem)
    if tag in _BITS_SKIP or (tag == "xref" and elem.get("ref-type") == "bibr"):
        return escape(elem.tail or "")
    if tag == "sec":
        title = elem.find("title")
        heading = "".join(title.itertext()).strip() if title is not None else ""
        body = "".join(bits_to_html(c, depth + 1) for c in elem if c.tag != "title")
        level = min(depth, 6)
        head = f"<h{level}>{escape(heading)}</h{level}>" if heading else ""
        return f"<section>{head}{body}</section>" + escape(elem.tail or "")
    if tag == "break":
        return "<br>" + escape(elem.tail or "")
    if tag == "term":
        return escape("".join(elem.itertext()).strip().rstrip(":")) + ": " + escape(elem.tail or "")
    inner = escape(elem.text or "") + "".join(bits_to_html(c, depth) for c in elem)
    html_tag = _BITS_HTML.get(tag)
    wrapped = f"<{html_tag}>{inner}</{html_tag}>" if html_tag else inner
    return wrapped + escape(elem.tail or "")


def drop_figure_references(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        line = re.sub(r"\s*\[\s*(?:\d+(?:\s*[,–-]\s*\d+)*)?\s*\]", "", line)
        line = re.sub(r"([.!?:;])\s*,+", r"\1", re.sub(r",{2,}", "", line))
        line = re.sub(r",+(?=:)", "", line)
        line = re.sub(r"\s*\((?:see |refer to )?[^()]*\b(?:Figure|Fig\.)\s*\d[^()]*\)", "", line, flags=re.I)
        if _FIGURE_REF.search(line):
            marker = re.match(r"^\s*(?:- )?", line).group(0)
            sentences = re.split(r"(?<=[.!?:])\s+", line[len(marker):])
            line = marker + " ".join(s for s in sentences if not _FIGURE_REF.search(s))
            if not line.strip() or line.strip() == "-":
                continue
        lines.append(line)
    return "\n".join(lines)


def tidy_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if not title.isupper() or " " not in title:
        return title
    words = []
    for i, word in enumerate(title.split(" ")):
        if word.rstrip(":") in _ACRONYMS:
            words.append(word)
        elif i and word.lower() in _SMALL_WORDS:
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words)


def book_licence(root: ET.Element) -> str | None:
    licence = root.find(".//book-meta//license")
    return licence.get(_XLINK_HREF) if licence is not None else None


def openrn_sections(xml: bytes, book: Book) -> list[dict]:
    root = ET.fromstring(xml)
    part = root.find(".//book-part")
    if part is None or part.find("body") is None:
        return []
    licence = book_licence(root)
    if not licence or not OPENRN_LICENCE_URL.match(licence):
        raise ValueError(f"{book.title}: licence {licence!r} is not CC BY 4.0")
    book_id = root.findtext(".//book-meta/book-id") or ""
    part_id = part.findtext("book-part-meta/book-part-id") or ""
    sections = []
    for sec in part.find("body").findall("sec"):
        label = (sec.findtext("label") or "").strip()
        title_el = sec.find("title")
        title = tidy_title("".join(title_el.itertext())) if title_el is not None else ""
        if not label or not title or sec.find("sec") is None or not re.match(book.chapter_pattern, label):
            continue
        if any(label == n or title.lower() == t.lower() for n, t in book.excluded):
            continue
        if EXCLUDED_CHAPTER.search(title) or EXCLUDED_HEADING.search(title):
            continue
        html = "".join(bits_to_html(c, 2) for c in sec if c.tag not in ("label", "title"))
        sections.append({
            "label": label,
            "title": title,
            "url": f"{NCBI_BOOKS_ROOT}/n/{book_id}/{part_id}/#{sec.get('id')}",
            "markdown": drop_figure_references(html_to_markdown(html)),
        })
    return sections


def litarch_path(fetcher: Fetcher, accession: str) -> str:
    for row in csv.DictReader(io.StringIO(fetcher.get(f"{LITARCH_ROOT}/file_list.csv"))):
        if row.get("Accession ID") == accession:
            return row["File"]
    raise ValueError(f"{accession} is not in the NCBI Bookshelf open-access set")


def book_chapters(archive: bytes) -> list[bytes]:
    chapters = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            match = re.match(r"ch(\d+)\w*\.nxml$", member.name.rsplit("/", 1)[-1])
            if member.isfile() and match:
                chapters.append((int(match.group(1)), tar.extractfile(member).read()))
    return [xml for _, xml in sorted(chapters)]


def fetch_openrn(fetcher: Fetcher, out_dir: Path, limit: int | None, fetched_at: str) -> list[dict]:
    source = SOURCES["openrn"]
    docs: list[dict] = []
    for book in OPENRN_BOOKS:
        archive = fetcher.get_bytes(f"{LITARCH_ROOT}/{litarch_path(fetcher, book.accession)}")
        for xml in book_chapters(archive):
            for sec in openrn_sections(xml, book):
                if limit is not None and len(docs) >= limit:
                    return docs
                doc = make_document(
                    source,
                    doc_id=f"OPENRN_{book.code}_{sec['label'].replace('.', '_')}_{_slug_id(sec['title'])}",
                    number=f"{book.code} {sec['label']}",
                    title=sec["title"],
                    section=book.section,
                    url=sec["url"],
                    attribution=openrn_attribution(book, f"{sec['label']} {sec['title']}", sec["url"]),
                    markdown=sec["markdown"],
                    fetched_at=fetched_at,
                )
                if doc:
                    write_document(out_dir, doc)
                    docs.append(doc)
    return docs


_MAIN_PATTERNS = (
    re.compile(r"<div[^>]+class=\"[^\"]*\bentry-content\b[^\"]*\"[^>]*>(.*?)<(?:footer|aside[^>]+class=\"[^\"]*\blitfl-cc\b"
               r"|div[^>]+class=\"[^\"]*\b(?:sharedaddy|post-tags|entry-footer|jp-relatedposts|molongui-clearfix|m-a-box)\b)", re.S),
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
    names: list[str] = []
    for content in re.findall(r"<meta name=\"author\" content=\"([^\"]+)\"", html, re.I):
        names.extend(n.strip() for n in re.split(r",|\band\b", unescape(content)))
    names = list(dict.fromkeys(n for n in names if n and n.lower() not in ("litfl", "admin")))
    if len(names) < 2:
        return names[0] if names else None
    return f"{', '.join(names[:-1])} and {names[-1]}"


def promote_bold_paragraphs(html: str) -> str:
    return re.sub(r"<p\b[^>]*>\s*<strong>([^<]{1,80})</strong>\s*</p>", r"<h6>\1</h6>", html)


def litfl_licensed(html: str) -> bool:
    footer = re.search(r"<footer\b", html)
    return bool(footer and LITFL_LICENCE.search(html, footer.start()))


def litfl_links(html: str) -> list[str]:
    links: list[str] = []
    main = extract_main_html(html)
    end = LITFL_INDEX_END.search(main)
    for href in re.findall(r"href=\"(https://litfl\.com/[a-z0-9-]+/)\"", main[:end.start()] if end else main):
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
        if "ECG" not in html or not litfl_licensed(html):
            print(f"skip {url}: no ECG content or no CC BY-NC-SA footer", file=sys.stderr)
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
            markdown=html_to_markdown(promote_bold_paragraphs(extract_main_html(html))),
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
