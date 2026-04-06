# CMG Data Completeness Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all remaining data completeness gaps in the CMG pipeline so that all clinical data is extracted, structured, and ingested into ChromaDB.

**Architecture:** Targeted bug fixes to the existing pipeline modules. The core extraction (stages 1-4) works well — 55 of 56 CMGs are extracted. Fixes address: (1) missing CMG 22a due to regex case mismatch, (2) broken dose_lookup matching, (3) MED/CSM section extraction, (4) markdown quality, (5) ChromaDB ingestion, (6) version tracking.

**Tech Stack:** Python 3.10+, pytest, ChromaDB, langchain-text-splitters

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `src/python/pipeline/cmg/extractor.py` | Fix `_CMG_SECTION_RE` for lowercase letter suffixes (e.g. "CMG 22a") |
| Modify | `src/python/pipeline/cmg/content_extractor.py` | Fix `_CMG_SECTION_RE` + extend merge for MED/CSM |
| Modify | `src/python/pipeline/cmg/structurer.py` | Fix dose_lookup matching (content scan, not title) + add MED/CSM support |
| Modify | `src/python/pipeline/cmg/models.py` | Add `source_type` "med" and "csm" to `ExtractionMetadata` |
| Modify | `src/python/pipeline/cmg/template_parser.py` | Improve `html_to_markdown` list formatting |
| Modify | `src/python/pipeline/cmg/chunker.py` | Handle MED/CSM collection ingestion |
| Modify | `src/python/pipeline/cmg/orchestrator.py` | Wire MED/CSM stages |
| Modify | `tests/python/test_cmg_extraction.py` | Tests for CMG 22a regex, MED/CSM extraction |
| Modify | `tests/python/test_cmg_pipeline.py` | Tests for dose matching fix, markdown quality |

---

## Task 1: Fix CMG 22a Regex (Lowercase Letter Suffix)

**Files:**
- Modify: `src/python/pipeline/cmg/extractor.py:21`
- Modify: `src/python/pipeline/cmg/content_extractor.py:25`
- Test: `tests/python/test_cmg_extraction.py`

The regex `^CMG\s+(\d+[A-Z]?)$` only matches uppercase letter suffixes (e.g. "CMG 3A"). CMG 22a has a lowercase "a" and is silently dropped.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py` in `TestSectionClassification`:

```python
def test_classify_lowercase_letter_suffix(self):
    assert _classify_section("CMG 22a") == "Neurology"
    assert _classify_section("CMG 22A") == "Neurology"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py::TestSectionClassification::test_classify_lowercase_letter_suffix -v`
Expected: FAIL (returns "Other" instead of "Neurology")

- [ ] **Step 3: Fix the regex in extractor.py**

Change line 21 of `src/python/pipeline/cmg/extractor.py`:
```python
_CMG_SECTION_RE = re.compile(r"^CMG\s+(\d+[A-Za-z]?)$")
```

Also update `_classify_section` to handle "22a" — the regex on line 101 extracts the number via `re.match(r"(\d+)", m.group(1))` which already works ("22" from "22a"). Add mapping:
```python
22: "Neurology",
```
(Already present — "22" maps to "Neurology", so "22a" will also classify correctly once the regex is fixed.)

- [ ] **Step 4: Fix the regex in content_extractor.py**

Change line 25 of `src/python/pipeline/cmg/content_extractor.py`:
```python
_CMG_SECTION_RE = re.compile(r"^CMG\s+(\d+[A-Za-z]?)$")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py::TestSectionClassification -v`
Expected: ALL PASS

---

## Task 2: Fix Dose Lookup Matching in Structurer

**Files:**
- Modify: `src/python/pipeline/cmg/structurer.py:79-84`
- Test: `tests/python/test_cmg_pipeline.py`

The current matching (`med_name.lower() in title_lower`) checks if a medicine name is a substring of the CMG title. No CMG title contains a medicine name. Fix: scan the body content instead.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_pipeline.py`:

```python
def test_dose_lookup_matches_by_content(tmp_path):
    from pipeline.cmg.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "4",
            "title": "Cardiac Arrest: Adult",
            "section": "Cardiac",
            "spotlightId": "testCardiac",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "# Cardiac Arrest: Adult\n\nAdrenaline 1mg IV every 3-5 minutes.\nAmiodarone 300mg IV bolus.",
        }
    ]
    dose_data = {
        "total_dose_groups": 1,
        "unique_medicines": ["Adrenaline", "Amiodarone"],
        "medicine_count": 2,
        "source_files": [],
        "medicine_index": {
            "Adrenaline": [{"text": "Adrenaline 1mg IV", "dose_values": [{"amount": "1", "unit": "mg"}]}],
            "Amiodarone": [{"text": "Amiodarone 300mg IV", "dose_values": [{"amount": "300", "unit": "mg"}]}],
        },
    }

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)
    with open(raw_dir / "dose_tables.json", "w") as f:
        json.dump(dose_data, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        dose_tables_path=str(raw_dir / "dose_tables.json"),
        output_dir=str(output_dir),
    )

    with open(output_dir / "CMG_4_Cardiac_Arrest__Adult.json") as f:
        cmg = json.load(f)
    assert cmg["dose_lookup"] is not None
    assert "Adrenaline" in cmg["dose_lookup"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_cmg_pipeline.py::test_dose_lookup_matches_by_content -v`
Expected: FAIL (`dose_lookup` is None)

- [ ] **Step 3: Fix structurer.py**

Replace lines 79-84 of `src/python/pipeline/cmg/structurer.py`:

```python
            cmg_dose = None
            content_lower = content_markdown.lower()
            matched_meds = {}
            for med_name, entries in dose_lookup.items():
                if med_name.lower() in content_lower:
                    matched_meds[med_name] = entries
            if matched_meds:
                cmg_dose = matched_meds
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/python/test_cmg_pipeline.py::test_dose_lookup_matches_by_content -v`
Expected: PASS

---

## Task 3: Improve Markdown List Formatting

**Files:**
- Modify: `src/python/pipeline/cmg/template_parser.py:381-402`
- Test: `tests/python/test_cmg_extraction.py`

List items run together: `- Item one.- Item two.` instead of separate lines. The `<li>` → `- ` conversion appends `\n` but adjacent items have no space between the closing `</li>` and opening `<li>`.

- [ ] **Step 1: Write the failing test**

Add to `tests/python/test_cmg_extraction.py` in `TestTemplateParser`:

```python
def test_html_to_markdown_separates_list_items(self):
    html = "<ul><li>Item one</li><li>Item two</li><li>Item three</li></ul>"
    md = html_to_markdown(html)
    lines = [l.strip() for l in md.strip().split("\n") if l.strip()]
    assert len(lines) == 3
    assert lines[0] == "- Item one"
    assert lines[1] == "- Item two"
    assert lines[2] == "- Item three"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py::TestTemplateParser::test_html_to_markdown_separates_list_items -v`
Expected: FAIL (list items concatenated)

- [ ] **Step 3: Fix html_to_markdown in template_parser.py**

Replace lines 381-402 with:

```python
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
    md = re.sub(r"<strong>(.*?)</strong>", r"**\1**", md)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md)
    md = re.sub(r"<br\s*/?>", "\n", md)
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"([.!?])([-])", r"\1\n\2", md)
    return md.strip()
```

Key change: `<li>` now produces `\n- ` (with leading newline) and a post-processing step `([.!?])([-])` adds a newline between a period and a dash (catches run-on items like "one.- two").

- [ ] **Step 4: Run all template parser tests**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py::TestTemplateParser -v`
Expected: ALL PASS

---

## Task 4: Extend Models for MED/CSM Sections

**Files:**
- Modify: `src/python/pipeline/cmg/models.py:41`

Add "med" and "csm" as valid source types.

- [ ] **Step 1: Update ExtractionMetadata**

Change line 42 of `src/python/pipeline/cmg/models.py`:
```python
    source_type: Literal["cmg", "med", "csm"] = "cmg"
```

- [ ] **Step 2: Run existing model tests**

Run: `python3 -m pytest tests/python/test_cmg_pipeline.py::test_pydantic_schema_validation -v`
Expected: PASS

---

## Task 5: Add MED/CSM Section Regex and Classification

**Files:**
- Modify: `src/python/pipeline/cmg/extractor.py`
- Modify: `src/python/pipeline/cmg/content_extractor.py`
- Test: `tests/python/test_cmg_extraction.py`

- [ ] **Step 1: Add section patterns in extractor.py**

After line 22 in `src/python/pipeline/cmg/extractor.py`, add:
```python
_MED_SECTION_RE = re.compile(r"^MED\s+(\d+)$")
_CSM_SECTION_RE = re.compile(r"^CSM\s+(\d+)$")
```

Update `_classify_section` to accept a second parameter for section type, or create a new function:

```python
def classify_entry(section: str) -> tuple:
    m = _CMG_SECTION_RE.match(section)
    if m:
        num = int(re.match(r"(\d+)", m.group(1)).group(1))
        return ("cmg", _classify_section(section))
    if _MED_SECTION_RE.match(section):
        return ("med", "Medicine")
    if _CSM_SECTION_RE.match(section):
        return ("csm", "Clinical Skill")
    return ("other", "Other")
```

- [ ] **Step 2: Add same section patterns in content_extractor.py**

After line 26 in `src/python/pipeline/cmg/content_extractor.py`, add:
```python
_MED_SECTION_RE = re.compile(r"^MED\s+(\d+)$")
_CSM_SECTION_RE = re.compile(r"^CSM\s+(\d+)$")
```

- [ ] **Step 3: Write tests**

Add to `tests/python/test_cmg_extraction.py`:

```python
class TestMEDCSMExtraction:
    def test_med_section_regex(self):
        from pipeline.cmg.extractor import _MED_SECTION_RE
        assert _MED_SECTION_RE.match("MED 01")
        assert _MED_SECTION_RE.match("MED 35")
        assert not _MED_SECTION_RE.match("CMG 1")

    def test_csm_section_regex(self):
        from pipeline.cmg.extractor import _CSM_SECTION_RE
        assert _CSM_SECTION_RE.match("CSM 01")
        assert _CSM_SECTION_RE.match("CSM 99")
        assert not _CSM_SECTION_RE.match("MED 01")
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py::TestMEDCSMExtraction -v`
Expected: ALL PASS

---

## Task 6: Extend Content Extraction and Merge for MED/CSM

**Files:**
- Modify: `src/python/pipeline/cmg/content_extractor.py:274-312`
- Test: `tests/python/test_cmg_extraction.py`

The `merge_navigation_and_content` function currently only processes entries matching `_CMG_SECTION_RE`. Extend it to also process MED and CSM entries.

- [ ] **Step 1: Update `_extract_navigation_titles` to include MED/CSM**

In `content_extractor.py`, update the `is_cmg` field to a more general `entry_type` field. Change lines 106-113:

```python
            section = obj.get("section", "")
            entry_type = "cmg"
            if _MED_SECTION_RE.match(section):
                entry_type = "med"
            elif _CSM_SECTION_RE.match(section):
                entry_type = "csm"
            elif not _CMG_SECTION_RE.match(section):
                entry_type = "other"
            titles.append(
                {
                    "title": title,
                    "section": section,
                    "spotlightId": sid,
                    "route_path": _title_to_path(title),
                    "entry_type": entry_type,
                }
            )
```

Note: This changes the `is_cmg` field used in `extract_content`. Update the `content_map` entries to use `entry_type` instead of `is_cmg`. Update the logging accordingly.

- [ ] **Step 2: Update `merge_navigation_and_content` to include MED/CSM**

In `content_extractor.py`, update the `merge_navigation_and_content` function to process all non-"other" entries. Change the filtering logic around line 287-289:

```python
    for page in nav_data.get("all_pages", []):
        section = page.get("section", "")
        section_match = _CMG_SECTION_RE.match(section) or _MED_SECTION_RE.match(section) or _CSM_SECTION_RE.match(section)
        if not section_match:
            continue
```

And include entry_type in the output:
```python
        entry_type = "cmg"
        if _MED_SECTION_RE.match(section):
            entry_type = "med"
        elif _CSM_SECTION_RE.match(section):
            entry_type = "csm"
        guidelines.append(
            {
                "cmg_number": section.split(" ", 1)[1] if " " in section else "",
                "title": page.get("title", ""),
                "section": _classify_section(section) if _CMG_SECTION_RE.match(section) else ("Medicine" if _MED_SECTION_RE.match(section) else "Clinical Skill"),
                "spotlightId": sid,
                "tags": page.get("tags", []),
                "atp": page.get("atp", []),
                "content_html": content_entry.get("html", ""),
                "content_markdown": content_entry.get("markdown", ""),
                "entry_type": entry_type,
            }
        )
```

- [ ] **Step 3: Write integration test**

Add to `tests/python/test_cmg_extraction.py`:

```python
def test_merge_includes_med_and_csm_entries(self, tmp_path):
    inv_dir = "data/cmgs/investigation/"
    if not os.path.exists(inv_dir):
        pytest.skip("No investigation data")

    from pipeline.cmg.content_extractor import merge_navigation_and_content, extract_content
    from pipeline.cmg.extractor import extract_navigation

    nav_path = str(tmp_path / "nav.json")
    content_path = str(tmp_path / "content.json")
    output_path = str(tmp_path / "guidelines.json")

    extract_navigation(investigation_dir=inv_dir, output_path=nav_path)
    extract_content(investigation_dir=inv_dir, output_path=content_path)
    merge_navigation_and_content(
        nav_path=nav_path,
        content_path=content_path,
        output_path=output_path,
    )

    with open(output_path) as f:
        guidelines = json.load(f)

    entry_types = {g.get("entry_type") for g in guidelines}
    assert "cmg" in entry_types
    med_entries = [g for g in guidelines if g.get("entry_type") == "med"]
    csm_entries = [g for g in guidelines if g.get("entry_type") == "csm"]
    assert len(med_entries) > 0
    assert len(csm_entries) > 0
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/python/test_cmg_extraction.py -v`
Expected: ALL PASS

---

## Task 7: Extend Structurer for MED/CSM

**Files:**
- Modify: `src/python/pipeline/cmg/structurer.py`
- Test: `tests/python/test_cmg_pipeline.py`

Update `structure_guidelines` to output MED/CSM entries to separate directories and use the correct `source_type`.

- [ ] **Step 1: Update structurer.py**

The structurer currently outputs all files to `data/cmgs/structured/`. For MED/CSM entries, output to subdirectories and set `source_type` correctly. Modify the loop in `structure_guidelines`:

After line 52, determine entry type:
```python
            entry_type = raw.get("entry_type", "cmg")
```

Update the output path to use subdirectories for MED/CSM:
```python
            if entry_type == "med":
                entry_output_dir = os.path.join(output_dir, "med")
            elif entry_type == "csm":
                entry_output_dir = os.path.join(output_dir, "csm")
            else:
                entry_output_dir = output_dir
            os.makedirs(entry_output_dir, exist_ok=True)
            output_file = os.path.join(entry_output_dir, f"{cmg.id}.json")
```

Update `ExtractionMetadata` source_type:
```python
                extraction_metadata=ExtractionMetadata(
                    timestamp=datetime.utcnow().isoformat(),
                    source_type=entry_type,
                    agent_version="2.0",
                    content_flag=content_flag,
                ),
```

- [ ] **Step 2: Write test**

Add to `tests/python/test_cmg_pipeline.py`:

```python
def test_structure_handles_med_entries(tmp_path):
    from pipeline.cmg.structurer import structure_guidelines

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    guidelines = [
        {
            "cmg_number": "01",
            "title": "Adrenaline",
            "section": "Medicine",
            "spotlightId": "med01test",
            "tags": [],
            "atp": [],
            "content_html": "",
            "content_markdown": "# Adrenaline\n\nPrimary treatment for anaphylaxis.",
            "entry_type": "med",
        },
    ]

    with open(raw_dir / "guidelines.json", "w") as f:
        json.dump(guidelines, f)

    output_dir = tmp_path / "structured"
    structure_guidelines(
        guidelines_path=str(raw_dir / "guidelines.json"),
        output_dir=str(output_dir),
    )

    med_dir = output_dir / "med"
    assert med_dir.exists()
    files = list(med_dir.glob("*.json"))
    assert len(files) == 1
    with open(files[0]) as f:
        data = json.load(f)
    assert data["extraction_metadata"]["source_type"] == "med"
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/python/test_cmg_pipeline.py -v`
Expected: ALL PASS

---

## Task 8: Extend Chunker for MED/CSM

**Files:**
- Modify: `src/python/pipeline/cmg/chunker.py`

Update `chunk_and_ingest` to scan MED/CSM subdirectories and ingest into separate or unified collections.

- [ ] **Step 1: Update chunker.py**

Modify `chunk_and_ingest` to scan subdirectories:

```python
def chunk_and_ingest(
    structured_dir: str = "data/cmgs/structured/",
    db_path: str = "data/chroma_db/"
):
    json_files = glob.glob(os.path.join(structured_dir, "*.json"))
    json_files.extend(glob.glob(os.path.join(structured_dir, "med", "*.json")))
    json_files.extend(glob.glob(os.path.join(structured_dir, "csm", "*.json")))
    if not json_files:
        logger.warning(f"No structured JSON files found in {structured_dir}")
        return

    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name="cmg_guidelines")
```

The rest of the logic already handles each file generically, so no other changes needed — the `source_type` metadata from the structurer will differentiate entries.

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/python/test_cmg_pipeline.py -v`
Expected: ALL PASS

---

## Task 9: Re-run Full Pipeline

**Files:**
- No code changes — run the orchestrator

After all code fixes are in place, re-run the full pipeline to produce updated data.

- [ ] **Step 1: Run pipeline stages 1-8**

Run:
```bash
python3 -m pipeline.cmg.orchestrator --stages all
```

This will:
1. Re-extract navigation (now finding 56 CMGs including 22a)
2. Re-extract content
3. Re-extract dose tables
4. Merge (now including MED/CSM entries)
5. Structure (now with fixed dose_lookup matching and MED/CSM entries)
6. Skip flowcharts (left as placeholders per user request)
7. Chunk and ingest into ChromaDB
8. Update version tracking

- [ ] **Step 2: Verify output**

```bash
# Check CMG count in guidelines.json
python3 -c "import json; d=json.load(open('data/cmgs/raw/guidelines.json')); print(f'Total entries: {len(d)}'); print(f'CMGs: {sum(1 for g in d if g.get(\"entry_type\",\"cmg\")==\"cmg\")}'); print(f'MEDs: {sum(1 for g in d if g.get(\"entry_type\")==\"med\")}'); print(f'CSMs: {sum(1 for g in d if g.get(\"entry_type\")==\"csm\")}')"

# Check CMG 22a exists
python3 -c "import json; d=json.load(open('data/cmgs/raw/guidelines.json')); matches=[g for g in d if '22a' in g.get('cmg_number','').lower()]; print(f'CMG 22a found: {len(matches)>0}'); print(matches[0]['title'] if matches else 'NOT FOUND')"

# Check structured files
ls data/cmgs/structured/ | wc -l
ls data/cmgs/structured/med/ 2>/dev/null | wc -l
ls data/cmgs/structured/csm/ 2>/dev/null | wc -l

# Check version tracking
cat data/cmgs/version_tracking.csv | wc -l

# Check ChromaDB
python3 -c "import chromadb; c=chromadb.PersistentClient(path='data/chroma_db/'); col=c.get_collection('cmg_guidelines'); print(f'Chunks: {col.count()}')"
```

- [ ] **Step 3: Run all tests**

Run: `python3 -m pytest tests/python/ -v`
Expected: ALL PASS

---

## Task 10: Verify Missing Medicine Doses

**Files:**
- Modify: `src/python/pipeline/cmg/dose_tables.py` (only if additional dose sources are found)

The dose_tables extraction found 20 medicines but 15 are missing from the weight-based calculator. These may exist in other JS chunks as clinical text (not the calculator format).

- [ ] **Step 1: Check what the dose_tables_segmented.json shows for missing medicines**

Run:
```bash
python3 -c "
import json
with open('data/cmgs/raw/dose_tables_segmented.json') as f:
    d = json.load(f)
all_meds = set(d['unique_medicines'])
print(f'Found medicines: {sorted(all_meds)}')
for pf in d['per_file']:
    for dg in pf['dose_groups']:
        text = dg.get('combined_text','')[:200]
        meds = dg.get('medicines',[])
        if not meds:
            print(f'  No medicine label: {pf[\"source_file\"]}: {text}')
"
```

If the missing medicines (salbutamol, fentanyl, etc.) appear in `.EFF()` text but aren't being classified, the `_MEDICINE_KEYWORDS` list in dose_tables.py may need adjustment or the `_is_dose_related` detection threshold may need lowering.

- [ ] **Step 2: If medicines are found, add them to the keyword list and re-run dose extraction**

This step is investigative — the actual fix depends on what's found. If the medicines genuinely don't appear in the JS bundles, this is a data limitation, not a pipeline bug.
