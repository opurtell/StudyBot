# AI Agent Guideline: ACTAS CMG Data Extraction Framework

> **Version:** 1.1 | **Last Updated:** 2024-04-01
> **Purpose:** Comprehensive technical guide for AI agents extracting data from ACTAS Clinical Management Guidelines

> **⚠️ KEY FINDING:** The medicine dose "calculators" in ACTAS CMG are **NOT formula-based calculators**. They are **pre-computed database lookup tables**. See Section 3.1 for details.

---

## Table of Contents

1. [Quick Reference](#1-quick-reference)
2. [Phase 1: Discovery & API Interception](#2-phase-1-discovery--api-interception)
3. [Phase 2: Extracting Complex Data](#3-phase-2-extracting-complex-data)
4. [Phase 3: Data Structuring & Conflict Resolution](#4-phase-3-data-structuring--conflict-resolution)
5. [Phase 4: Validation & Pipeline](#5-phase-4-validation--pipeline)
6. [Code Templates](#6-code-templates)
7. [Error Handling](#7-error-handling)
8. [Implementation Checklist](#8-implementation-checklist)

---

## 1. Quick Reference

### Site URL
```
https://cmg.ambulance.act.gov.au/tabs/guidelines
```

### Core Principle
**Target the "source of truth"** — extract raw JSON data, not rendered HTML. This preserves data hierarchy and reduces processing overhead.

### Target Data Indicators

| Indicator | What to Look For |
|-----------|------------------|
| **Payload Size** | Main JS bundle ~10MB, contains all embedded data |
| **URL Patterns** | `main.*.js` bundle, `MED##` section codes |
| **Data Structure** | Weight bands (3kg-120kg), medicines, indications, pre-computed doses |
| **Load Timing** | Data embedded in JS bundle, loaded on initial page load |
| **App Framework** | Ionic/Angular with Capacitor (SPA) |

### Recommended Tools

| Tool | Language | Primary Use |
|------|----------|-------------|
| **Playwright** | Python/JS | SPA rendering, network interception |
| **BeautifulSoup4** | Python | HTML parsing, legacy page cleaning |
| **Mermaid.js** | JavaScript | Flowchart storage format |
| **Pandas** | Python | Version management, conflict detection, dose table analysis |

> **Note:** Medicine dose "calculators" are actually **database lookups**, not formula calculators. No calculation engine needed.

### Installation
```bash
# Python
pip install playwright beautifulsoup4 pandas
playwright install chromium

# Node.js
npm install playwright mermaid js-yaml
```

---

## 2. Phase 1: Discovery & API Interception

### 2.1 Network Inspection

**Goal:** Identify JSON payloads that serve as the primary data source.

**Strategy:** Use headless browser to monitor XHR/Fetch requests during site initialization.

#### Network Interception Template (Playwright)

```javascript
const { chromium } = require('playwright');

async function interceptNetworkData(targetUrl) {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const capturedData = [];

  // Intercept all network requests
  page.on('response', async (response) => {
    const url = response.url();
    const contentType = response.headers()['content-type'] || '';

    // Filter for JSON responses
    if (contentType.includes('application/json')) {
      try {
        const jsonData = await response.json();
        capturedData.push({
          url: url,
          size: JSON.stringify(jsonData).length,
          data: jsonData
        });
      } catch (e) { console.error('Parse error:', e); }
    }
  });

  await page.goto(targetUrl, { waitUntil: 'networkidle' });
  await browser.close();
  
  // Sort by size to find primary data payload
  return capturedData.sort((a, b) => b.size - a.size);
}

// Usage
interceptNetworkData('https://cmg.actas.example.com').then(data => {
  console.log('Largest payload:', data[0]?.url);
});
```

### 2.2 Asset Crawling (Secondary Method)

If API endpoints are not discoverable, probe common asset paths:

```
/assets/data/guidelines.json
/assets/json/content.json
/data/guidelines.db              # SQLite format
/static/data/clinical-guidelines.json
/build/data.bundle.js            # Embedded in JavaScript
```

#### Asset Probe Script

```python
import requests
from urllib.parse import urljoin

def probe_asset_paths(base_url, paths):
    found_assets = []
    
    for path in paths:
        full_url = urljoin(base_url, path)
        try:
            response = requests.head(full_url, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                size = int(response.headers.get('content-length', 0))
                found_assets.append({
                    'url': full_url,
                    'type': content_type,
                    'size': size
                })
        except requests.RequestException:
            pass
    
    return found_assets

# Common paths to probe
ASSET_PATHS = [
    '/assets/data/guidelines.json',
    '/assets/json/content.json',
    '/data/guidelines.db',
    '/static/data/clinical-guidelines.json',
    '/build/data.bundle.js'
]
```

### 2.3 Identifying the Primary Data Payload

After capturing network traffic, analyze responses to find the guidelines dataset:

```python
def identify_primary_payload(captured_data):
    """
    Analyze captured network data to identify the primary guidelines payload.
    """
    for item in captured_data:
        data = item['data']
        
        # Check for guideline structure indicators
        if isinstance(data, dict):
            # Look for array of guidelines
            for key in ['guidelines', 'data', 'items', 'content']:
                if key in data and isinstance(data[key], list):
                    if len(data[key]) > 10:  # Multiple guidelines
                        return item
        
        # Check if data is directly an array
        if isinstance(data, list) and len(data) > 10:
            # Verify clinical content markers
            sample = data[0] if data else {}
            clinical_markers = ['title', 'section', 'dosage', 'indications', 'id']
            if any(marker in sample for marker in clinical_markers):
                return item
    
    return None
```

---

## 3. Phase 2: Extracting Complex Data

### 3.1 Medicine Dose Data: Database Lookup (NOT Formula Calculators)

> **⚠️ CRITICAL FINDING:** The ACTAS CMG "Medicine Calculator" is **NOT a formula-based calculator**. It is a **pre-computed database lookup table**.

#### Verified Architecture

Through direct investigation of the CMG application at `https://cmg.ambulance.act.gov.au`, the medicine dose system works as follows:

1. **User selects a weight band** from 24 predefined options:
   - Pediatric: 3kg (Newborn), 5kg (3 months), 7kg (6 months), 11kg (1 year), 13kg (2 years), 15kg (3 years), 17kg (4 years), 19kg (5 years), 21kg (6 years), 23kg (7 years), 25kg (8 years), 27kg (9 years), 30kg (10 years), 33kg (11 years), 35kg
   - Adult: 40kg, 45kg, 50kg, 60kg, 70kg, 80kg, 90kg, 100kg, 110kg, 120kg

2. **User selects a medicine** from the list (e.g., Adrenaline, Fentanyl, Morphine, Ketamine, etc.)

3. **User selects an indication** (e.g., for Adrenaline: Anaphylaxis, Cardiac Arrest, Severe Asthma, Severe Upper Airway Swelling)

4. **System returns pre-computed values** including:
   - Dose amount (e.g., "0.25 mg IM")
   - Volume to administer (e.g., "0.25 ml")
   - Administration notes
   - Presentation info (e.g., "1ml ampoule")
   - Formula reference (e.g., "1mg/1ml")

#### Example Lookup Result

For **Weight: 25kg (8 years) → Medicine: Adrenaline → Indication: Anaphylaxis**:

```
Dose: 0.25 mg IM
Volume: 0.25 ml
Notes: Repeat @5/60 if required (max. 3 doses)
Presentation: 1ml ampoule
Formula: 1mg/1ml
```

#### Data Extraction Strategy

Since doses are pre-computed lookups, extract the **complete dose table** from the JavaScript bundle:

```python
# The dose data is embedded in main.js as lookup tables
# Structure: medicine_doses[weight_band][medicine][indication] = dose_info

DOSE_LOOKUP_SCHEMA = {
    "weight_band": "25kg",           # Weight band identifier
    "medicine": "Adrenaline",         # Medicine name
    "indication": "Anaphylaxis",      # Clinical indication
    "route": "IM",                    # Administration route
    "dose_amount": "0.25 mg",         # Pre-computed dose
    "volume": "0.25 ml",              # Volume to administer
    "notes": "Repeat @5/60 if required (max. 3 doses)",
    "presentation": "1ml ampoule",
    "concentration": "1mg/1ml"
}
```

#### Locating Dose Table Data

The dose lookup tables are embedded in the main JavaScript bundle. Search for patterns:

```python
import re

def find_dose_tables(js_content):
    """
    Locate medicine dose lookup tables in the JS bundle.
    
    The data is NOT in calculator functions - it's in lookup table structures.
    """
    # Look for medicine section markers
    medicine_pattern = r'"section":"MED\d+"'
    medicines = re.findall(medicine_pattern, js_content)
    
    # Look for weight band references
    weight_patterns = [
        r'"weight":\s*\d+',           # Direct weight values
        r'"kg":\s*\d+',               # kg values
        r'"band":\s*"[^"]*kg"'        # Weight band strings
    ]
    
    # Look for dose data structures
    dose_indicators = [
        r'"dose":\s*"[^"]*"',         # Dose fields
        r'"volume":\s*"[^"]*"',       # Volume fields
        r'"route":\s*"[A-Z]+"'        # Route (IM, IV, etc.)
    ]
    
    return {
        'medicines': medicines,
        'weights': [re.findall(p, js_content) for p in weight_patterns],
        'doses': [re.findall(p, js_content) for p in dose_indicators]
    }
```

#### Complete Dose Table Extraction

```javascript
// Expected data structure to extract from JS bundle
const doseLookupTable = {
  "weight_bands": [
    { "id": "w3", "weight_kg": 3, "label": "3kg (Newborn)" },
    { "id": "w5", "weight_kg": 5, "label": "5kg (3 months)" },
    { "id": "w70", "weight_kg": 70, "label": "70kg" },
    // ... all 24 weight bands
  ],
  "medicines": [
    {
      "id": "MED03",
      "name": "Adrenaline",
      "indications": ["Anaphylaxis", "Cardiac Arrest", "Severe Asthma", "Severe Upper Airway Swelling"],
      "routes": ["IM", "IV", "Nebulised"]
    },
    // ... all medicines
  ],
  "dose_table": {
    "w25": {  // 25kg weight band
      "Adrenaline": {
        "Anaphylaxis": {
          "IM": { "dose": "0.25 mg", "volume": "0.25 ml", "notes": "Repeat @5/60" }
        },
        "Cardiac Arrest": {
          "IV": { "dose": "0.25 mg", "volume": "2.5 ml", "notes": "Dilute to 10ml" }
        }
      }
    }
    // ... all combinations
  }
};
```

### 3.2 Other Calculators (Scoring Tools)

While medicine doses are lookups, other calculators in the app MAY be formula-based:

| Calculator | Type | Notes |
|------------|------|-------|
| **Medicine Calculator** | Database Lookup | Pre-computed dose tables |
| **APGAR Tool** | Scoring System | Sum of 5 criteria (0-2 each) |
| **CRESST Screening Tool** | Scoring System | Clinical assessment score |
| **NEWS2 Score** | Scoring System | National Early Warning Score |
| **Palliative Care Calculator** | Likely Lookup | Similar to medicine calculator |

For scoring tools like APGAR and NEWS2, extract the scoring criteria:

```python
# Example: NEWS2 scoring criteria extraction
NEWS2_CRITERIA = {
    "respiratory_rate": {
        "ranges": [
            {"min": 0, "max": 8, "score": 3},
            {"min": 9, "max": 11, "score": 1},
            {"min": 12, "max": 20, "score": 0},
            {"min": 21, "max": 24, "score": 2},
            {"min": 25, "max": 999, "score": 3}
        ]
    },
    "oxygen_saturation": {
        "ranges": [
            {"min": 0, "max": 91, "score": 3},
            {"min": 92, "max": 93, "score": 2},
            {"min": 94, "max": 95, "score": 1},
            {"min": 96, "max": 999, "score": 0}
        ]
    }
    # ... additional criteria
}
```

### 3.3 Flowchart Reconstruction

#### SVG Flowchart Processing

```javascript
function svgToMermaid(svgContent) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgContent, 'image/svg+xml');
  const nodes = [];
  const connections = [];

  // Extract text elements with positions
  doc.querySelectorAll('text').forEach((el, idx) => {
    const x = parseFloat(el.getAttribute('x'));
    const y = parseFloat(el.getAttribute('y'));
    nodes.push({
      id: `N${idx}`,
      text: el.textContent.trim(),
      x, y
    });
  });

  // Extract path/line elements for connections
  doc.querySelectorAll('path, line').forEach(el => {
    // Analyze path to determine source and target nodes
    // This requires spatial analysis based on coordinates
  });

  return reconstructFlowchart(nodes, connections);
}

function reconstructFlowchart(nodes, connections) {
  // Sort nodes by Y position (top to bottom flow)
  nodes.sort((a, b) => a.y - b.y);
  
  let mermaidCode = 'graph TD\n';
  
  nodes.forEach((node, idx) => {
    const safeText = node.text.replace(/"/g, "'");
    const shape = isDecisionNode(node.text) ? `{${safeText}}` : `[${safeText}]`;
    mermaidCode += `  ${node.id}${shape}\n`;
  });
  
  connections.forEach(conn => {
    mermaidCode += `  ${conn.source} --> ${conn.target}\n`;
  });
  
  return mermaidCode;
}

function isDecisionNode(text) {
  const decisionIndicators = ['?', 'if', 'then', 'yes', 'no', 'check', 'assess'];
  return decisionIndicators.some(ind => text.toLowerCase().includes(ind));
}
```

#### Image-Based Flowchart Transcription

For flowcharts embedded as images, use Vision LLM:

```python
FLOWCHART_TRANSCRIPTION_PROMPT = """
Analyze this clinical flowchart image and convert it to Mermaid.js format.

Rules:
1. Identify all decision nodes (diamond shapes, questions) - use {} syntax
2. Identify all process nodes (rectangles) - use [] syntax  
3. Identify all terminal nodes (rounded rectangles) - use (()) syntax
4. Map all arrows/connections between nodes
5. Preserve exact clinical text from each node
6. Use clear node IDs (A, B, C, etc.)

Output format:
graph TD
  A[Start] --> B{Assess Patient}
  B -->|Critical| C[Call for Help]
  B -->|Stable| D[Continue Assessment]
  ...

Provide the complete Mermaid.js code.
"""
```

---

## 4. Phase 3: Data Structuring & Conflict Resolution

### 4.1 Ground Truth Schema

All extracted guidelines MUST conform to this schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CMG Guideline Schema",
  "type": "object",
  "required": ["id", "title", "version_date", "content_markdown", "source_url"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^CMG_[0-9]+[A-Z]?_.+$",
      "description": "Unique identifier e.g., CMG_12_Asthma"
    },
    "cmg_number": {
      "type": "string",
      "description": "Original CMG number e.g., 12, 14C, 3A"
    },
    "title": {
      "type": "string",
      "description": "Guideline title"
    },
    "version_date": {
      "type": "string",
      "format": "date",
      "description": "Official version date YYYY-MM-DD"
    },
    "last_modified": {
      "type": "string",
      "format": "date-time",
      "description": "Last modification timestamp"
    },
    "section": {
      "type": "string",
      "enum": ["Respiratory", "Cardiac", "Trauma", "Medical", "Pediatric", "Obstetric", "Other"],
      "description": "Clinical category"
    },
    "content_markdown": {
      "type": "string",
      "description": "Full content in Markdown format"
    },
    "chunks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "type": { "type": "string", "enum": ["dosage", "indications", "contraindications", "procedure", "notes"] },
          "content": { "type": "string" },
          "tokens": { "type": "integer" }
        }
      }
    },
    "dose_lookup": {
      "type": "object",
      "description": "Pre-computed dose lookup table for this medicine (NOT a calculator formula)",
      "properties": {
        "medicine_id": { "type": "string", "description": "e.g., MED03" },
        "weight_bands": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "weight_kg": { "type": "integer" },
              "label": { "type": "string" },
              "indications": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "indication": { "type": "string" },
                    "route": { "type": "string" },
                    "dose": { "type": "string" },
                    "volume": { "type": "string" },
                    "notes": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "flowchart": {
      "type": "string",
      "description": "Mermaid.js flowchart code"
    },
    "tables": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "headers": { "type": "array", "items": { "type": "string" } },
          "rows": { "type": "array", "items": { "type": "array" } },
          "caption": { "type": "string" }
        }
      }
    },
    "source_url": {
      "type": "string",
      "format": "uri"
    },
    "checksum": {
      "type": "string",
      "pattern": "^sha256:[a-f0-9]{64}$"
    },
    "extraction_metadata": {
      "type": "object",
      "properties": {
        "extracted_at": { "type": "string", "format": "date-time" },
        "agent_version": { "type": "string" },
        "source_type": { "type": "string", "enum": ["api", "json_file", "html", "hybrid"] }
      }
    }
  }
}
```

### 4.2 Conflict Detection Algorithm

```python
import hashlib
from datetime import datetime
from typing import List, Dict, Any

def calculate_checksum(data: dict) -> str:
    """Calculate SHA-256 checksum of content."""
    content_str = str(sorted(data.items()))
    return f"sha256:{hashlib.sha256(content_str.encode()).hexdigest()}"

def detect_conflicts(guidelines_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect conflicts between multiple versions of guidelines.
    """
    indexed = {}  # id -> list of versions
    conflicts = []

    # Group by ID
    for g in guidelines_list:
        gid = g.get('id')
        if gid not in indexed:
            indexed[gid] = []
        indexed[gid].append(g)

    # Compare versions
    for gid, versions in indexed.items():
        if len(versions) <= 1:
            continue

        # Check 1: Same date, different content
        dates = [v.get('version_date') for v in versions]
        checksums = [v.get('checksum', calculate_checksum(v)) for v in versions]

        if len(set(dates)) == 1 and len(set(checksums)) > 1:
            conflicts.append({
                'id': gid,
                'type': 'CONTENT_MISMATCH_SAME_DATE',
                'severity': 'HIGH',
                'message': f'Conflict in {gid}: Same version date but different content',
                'sources': [v.get('source_url') for v in versions],
                'action': 'Human review required - clinical data discrepancy'
            })

        # Check 2: Multiple versions, unclear which is current
        elif len(set(dates)) > 1:
            sorted_versions = sorted(versions, key=lambda x: x.get('version_date', ''), reverse=True)
            if sorted_versions[0].get('version_date') == sorted_versions[1].get('version_date'):
                conflicts.append({
                    'id': gid,
                    'type': 'VERSION_AMBIGUITY',
                    'severity': 'MEDIUM',
                    'message': f'Conflict in {gid}: Multiple versions with same date',
                    'sources': [v.get('source_url') for v in versions]
                })

        # Check 3: Checksum mismatch without date info
        elif len(set(checksums)) > 1:
            conflicts.append({
                'id': gid,
                'type': 'CONTENT_VARIATION',
                'severity': 'LOW',
                'message': f'Conflict in {gid}: Content variations detected',
                'sources': [v.get('source_url') for v in versions],
                'action': 'Compare content to determine authoritative version'
            })

    return conflicts

def generate_conflict_report(conflicts: List[Dict]) -> str:
    """Generate human-readable conflict report."""
    if not conflicts:
        return "No conflicts detected."

    report = "# Clinical Data Conflict Report\n\n"
    
    for severity in ['HIGH', 'MEDIUM', 'LOW']:
        severity_conflicts = [c for c in conflicts if c.get('severity') == severity]
        if severity_conflicts:
            report += f"## {severity} Severity ({len(severity_conflicts)} issues)\n\n"
            for c in severity_conflicts:
                report += f"### {c['id']}\n"
                report += f"- **Type:** {c['type']}\n"
                report += f"- **Message:** {c['message']}\n"
                if 'action' in c:
                    report += f"- **Action Required:** {c['action']}\n"
                report += f"- **Sources:**\n"
                for s in c.get('sources', []):
                    report += f"  - {s}\n"
                report += "\n"

    return report
```

### 4.3 Version Tracking with Pandas

```python
import pandas as pd
from datetime import datetime

class GuidelineVersionManager:
    def __init__(self):
        self.df = pd.DataFrame(columns=[
            'id', 'title', 'version_date', 'checksum',
            'source_url', 'extracted_at', 'status'
        ])

    def add_version(self, guideline: dict):
        """Add or update a guideline version."""
        new_row = {
            'id': guideline['id'],
            'title': guideline['title'],
            'version_date': guideline.get('version_date'),
            'checksum': guideline.get('checksum', calculate_checksum(guideline)),
            'source_url': guideline.get('source_url'),
            'extracted_at': datetime.now().isoformat(),
            'status': 'active'
        }
        self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)

    def get_latest(self, guideline_id: str) -> dict:
        """Get the latest version of a guideline."""
        matches = self.df[self.df['id'] == guideline_id]
        if matches.empty:
            return None
        return matches.sort_values('version_date', ascending=False).iloc[0].to_dict()

    def get_history(self, guideline_id: str) -> pd.DataFrame:
        """Get version history for a guideline."""
        return self.df[self.df['id'] == guideline_id].sort_values('version_date')

    def export_tracking_table(self, filepath: str):
        """Export version tracking to CSV."""
        self.df.to_csv(filepath, index=False)
```

---

## 5. Phase 4: Validation & Pipeline

### 5.1 Markdown Conversion Rules

| Element | Conversion Rule |
|---------|-----------------|
| HTML Tables | Convert to pipe-table format with alignment |
| Headings | Normalize to H1 > H2 > H3 hierarchy |
| Clinical Notation | Preserve exactly: `mg/kg`, `mcg/min`, `mmol/L` |
| Lists | Use proper Markdown `- ` or `1. ` syntax |
| Bold/Italic | Convert `<b>` to `**`, `<i>` to `*` |
| Special Characters | Escape: `<` → `\<` when not HTML |

```python
import re
from bs4 import BeautifulSoup

def html_to_markdown(html_content: str) -> str:
    """Convert HTML content to clean Markdown."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Convert tables
    for table in soup.find_all('table'):
        markdown_table = convert_table_to_markdown(table)
        table.replace_with(BeautifulSoup(f'\n{markdown_table}\n', 'html.parser'))
    
    # Convert headings
    for i in range(6, 0, -1):
        for heading in soup.find_all(f'h{i}'):
            heading.string = f"{'#' * i} {heading.get_text()}"
    
    # Convert lists
    for ul in soup.find_all('ul'):
        for li in ul.find_all('li'):
            li.string = f"- {li.get_text()}"
    for ol in soup.find_all('ol'):
        for idx, li in enumerate(ol.find_all('li'), 1):
            li.string = f"{idx}. {li.get_text()}"
    
    # Convert formatting
    for bold in soup.find_all(['b', 'strong']):
        bold.string = f"**{bold.get_text()}**"
    for italic in soup.find_all(['i', 'em']):
        italic.string = f"*{italic.get_text()}*"
    
    return soup.get_text()

def convert_table_to_markdown(table) -> str:
    """Convert HTML table to Markdown pipe table."""
    rows = table.find_all('tr')
    if not rows:
        return ""
    
    # Extract headers
    headers = [th.get_text().strip() for th in rows[0].find_all(['th', 'td'])]
    
    # Build markdown
    md = "| " + " | ".join(headers) + " |\n"
    md += "|" + "|".join(["---"] * len(headers)) + "|\n"
    
    # Add data rows
    for row in rows[1:]:
        cells = [td.get_text().strip() for td in row.find_all('td')]
        if cells:
            md += "| " + " | ".join(cells) + " |\n"
    
    return md
```

### 5.2 Semantic Chunking Strategy

| Chunk Type | Trigger Headers | Max Tokens | Purpose |
|------------|-----------------|------------|---------|
| **Dosage Information** | Dosage, Administration, Dose | 500 | Drug calculation data |
| **Safety Warnings** | Contraindications, Warnings, Precautions | 300 | Critical safety info |
| **Clinical Protocol** | Procedure, Treatment, Management | 1000 | Step-by-step instructions |
| **Reference Data** | Tables, Appendices, References | 800 | Lookup tables |
| **Assessment Criteria** | Indications, Presentation, Diagnosis | 400 | Decision criteria |

```python
from typing import List, Dict
import re

CHUNK_CONFIG = {
    'dosage': {
        'triggers': ['dosage', 'administration', 'dose', 'amount'],
        'max_tokens': 500
    },
    'safety': {
        'triggers': ['contraindications', 'warnings', 'precautions', 'cautions'],
        'max_tokens': 300
    },
    'protocol': {
        'triggers': ['procedure', 'treatment', 'management', 'intervention'],
        'max_tokens': 1000
    },
    'reference': {
        'triggers': ['table', 'appendix', 'reference', 'quick reference'],
        'max_tokens': 800
    },
    'assessment': {
        'triggers': ['indications', 'presentation', 'diagnosis', 'assessment'],
        'max_tokens': 400
    }
}

def estimate_tokens(text: str) -> int:
    """Estimate token count (rough: 1 token ≈ 4 characters)."""
    return len(text) // 4

def chunk_guideline(content: str, guideline_id: str) -> List[Dict]:
    """
    Break guideline into semantic chunks for AI consumption.
    """
    chunks = []
    lines = content.split('\n')
    current_chunk = {'type': 'general', 'content': [], 'tokens': 0}
    chunk_id = 0

    for line in lines:
        # Check for section headers
        header_match = re.match(r'^#+\s+(.+)$', line)
        if header_match:
            header_text = header_match.group(1).lower()
            
            # Determine chunk type from header
            chunk_type = 'general'
            for ctype, config in CHUNK_CONFIG.items():
                if any(trigger in header_text for trigger in config['triggers']):
                    chunk_type = ctype
                    break
            
            # Save previous chunk if has content
            if current_chunk['content']:
                chunks.append({
                    'id': f"{guideline_id}_chunk_{chunk_id}",
                    'type': current_chunk['type'],
                    'content': '\n'.join(current_chunk['content']),
                    'tokens': current_chunk['tokens']
                })
                chunk_id += 1
            
            # Start new chunk
            max_tokens = CHUNK_CONFIG.get(chunk_type, {}).get('max_tokens', 600)
            current_chunk = {
                'type': chunk_type,
                'content': [line],
                'tokens': estimate_tokens(line),
                'max_tokens': max_tokens
            }
        else:
            # Add to current chunk
            line_tokens = estimate_tokens(line)
            
            # Check if we need to split
            if current_chunk['tokens'] + line_tokens > current_chunk.get('max_tokens', 600):
                # Save current chunk and start continuation
                if current_chunk['content']:
                    chunks.append({
                        'id': f"{guideline_id}_chunk_{chunk_id}",
                        'type': current_chunk['type'],
                        'content': '\n'.join(current_chunk['content']),
                        'tokens': current_chunk['tokens']
                    })
                    chunk_id += 1
                
                current_chunk = {
                    'type': current_chunk['type'],
                    'content': [line],
                    'tokens': line_tokens,
                    'max_tokens': current_chunk.get('max_tokens', 600)
                }
            else:
                current_chunk['content'].append(line)
                current_chunk['tokens'] += line_tokens

    # Save final chunk
    if current_chunk['content']:
        chunks.append({
            'id': f"{guideline_id}_chunk_{chunk_id}",
            'type': current_chunk['type'],
            'content': '\n'.join(current_chunk['content']),
            'tokens': current_chunk['tokens']
        })

    return chunks
```

### 5.3 Verification Pass

```python
VERIFICATION_PROMPT = """
You are verifying extracted clinical guideline data against the original source.

Compare the extracted data with the original content and identify:
1. Missing sections or tables
2. Truncated dosage values
3. Lost formatting (tables converted incorrectly)
4. Missing calculator functions
5. Incomplete flowcharts

Original Content:
{original_content}

Extracted Data:
{extracted_data}

Report any discrepancies with severity:
- CRITICAL: Missing dosage/safety information
- HIGH: Incomplete sections
- MEDIUM: Formatting issues
- LOW: Minor text differences

Output format:
## Verification Report
### Critical Issues
- [List or "None"]

### High Priority Issues
- [List or "None"]

### Medium Priority Issues
- [List or "None"]

### Low Priority Issues
- [List or "None"]

### Summary
- Completeness Score: X%
- Recommendation: [PASS/REVIEW/FAIL]
"""

async def run_verification_pass(extracted_data: dict, original_url: str) -> dict:
    """
    Run verification pass comparing extracted data to original source.
    """
    # Fetch original content for comparison
    original_content = await fetch_original_content(original_url)
    
    # Use LLM to compare
    verification_result = await verify_with_llm(
        original_content=original_content,
        extracted_data=extracted_data
    )
    
    return verification_result
```

---

## 6. Code Templates

### 6.1 Complete Extraction Pipeline

```python
#!/usr/bin/env python3
"""
ACTAS CMG Data Extraction Pipeline
Complete template for AI agents
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any
from playwright.async_api import async_playwright

class CMGExtractor:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.raw_data = []
        self.guidelines = []
        self.conflicts = []
        self.chunks = []

    async def run_pipeline(self):
        """Execute complete extraction pipeline."""
        print("Starting CMG extraction pipeline...")
        
        # Phase 1: Discovery
        print("Phase 1: Discovery & API Interception")
        await self.discover_data_sources()
        
        # Phase 2: Extract complex data
        print("Phase 2: Extracting complex data")
        await self.extract_calculators()
        await self.extract_flowcharts()
        
        # Phase 3: Structure and validate
        print("Phase 3: Data structuring & conflict resolution")
        self.normalize_to_schema()
        self.detect_conflicts()
        
        # Phase 4: Validation
        print("Phase 4: Validation & pipeline")
        self.convert_to_markdown()
        self.chunk_content()
        await self.run_verification()
        
        print("Pipeline complete!")
        return self.generate_output()

    async def discover_data_sources(self):
        """Phase 1: Network interception to find data sources."""
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            captured = []
            page.on('response', lambda r: self.capture_response(r, captured))
            
            await page.goto(self.base_url, wait_until='networkidle')
            await browser.close()
            
            self.raw_data = captured

    async def capture_response(self, response, captured_list):
        """Capture JSON responses during page load."""
        if 'application/json' in (response.headers.get('content-type') or ''):
            try:
                data = await response.json()
                captured_list.append({
                    'url': response.url,
                    'size': len(json.dumps(data)),
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass

    async def extract_calculators(self):
        """Phase 2a: Extract calculator logic from JS bundles."""
        # Implementation for calculator extraction
        pass

    async def extract_flowcharts(self):
        """Phase 2b: Extract and convert flowcharts."""
        # Implementation for flowchart extraction
        pass

    def normalize_to_schema(self):
        """Phase 3a: Normalize all data to Ground Truth schema."""
        # Implementation for schema normalization
        pass

    def detect_conflicts(self):
        """Phase 3b: Detect data conflicts."""
        self.conflicts = detect_conflicts(self.guidelines)

    def convert_to_markdown(self):
        """Phase 4a: Convert to Markdown."""
        for g in self.guidelines:
            g['content_markdown'] = html_to_markdown(g.get('content_html', ''))

    def chunk_content(self):
        """Phase 4b: Semantic chunking."""
        for g in self.guidelines:
            g['chunks'] = chunk_guideline(g['content_markdown'], g['id'])

    async def run_verification(self):
        """Phase 4c: Verification pass."""
        for g in self.guidelines:
            g['verification'] = await run_verification_pass(
                g, g.get('source_url')
            )

    def generate_output(self):
        """Generate final output."""
        return {
            'guidelines': self.guidelines,
            'conflicts': self.conflicts,
            'extraction_timestamp': datetime.now().isoformat(),
            'source_url': self.base_url
        }


# Usage
async def main():
    extractor = CMGExtractor('https://cmg.actas.example.com')
    result = await extractor.run_pipeline()
    
    with open('extracted_guidelines.json', 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == '__main__':
    asyncio.run(main())
```

### 6.2 Quick Extraction Script

```python
#!/usr/bin/env python3
"""Quick single-guideline extraction script."""

import sys
from playwright.sync_api import sync_playwright

def extract_single_guideline(url: str) -> dict:
    """Extract a single guideline page."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Capture network data
        data = []
        page.on('response', lambda r: data.append(r) if 'json' in (r.headers.get('content-type') or '') else None)
        
        page.goto(url, wait_until='networkidle')
        
        # Also extract visible content
        content = page.content()
        title = page.title()
        
        browser.close()
        
        return {
            'url': url,
            'title': title,
            'network_data': [r.url for r in data],
            'content_length': len(content)
        }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract.py <url>")
        sys.exit(1)
    
    result = extract_single_guideline(sys.argv[1])
    print(f"Extracted: {result['title']}")
    print(f"Network requests captured: {len(result['network_data'])}")
```

---

## 7. Error Handling

### 7.1 Common Error Scenarios

| Error Type | Recovery Strategy |
|------------|-------------------|
| **Network Timeout** | Retry with exponential backoff (max 3 attempts) |
| **Authentication Required** | Flag for manual intervention, cache partial results |
| **Schema Changed** | Log changes, attempt adaptive parsing, alert admin |
| **Content Unchanged** | Skip processing, update last-checked timestamp |
| **Conflict Detected** | Generate report, quarantine for review |

### 7.2 Error Handler Implementation

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator for retrying operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    delay = base_delay * (2 ** attempt)
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

class ExtractionErrorHandler:
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def log_error(self, error_type: str, message: str, context: dict = None):
        self.errors.append({
            'type': error_type,
            'message': message,
            'context': context,
            'timestamp': datetime.now().isoformat()
        })
        
    def log_warning(self, warning_type: str, message: str):
        self.warnings.append({
            'type': warning_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def has_critical_errors(self) -> bool:
        critical_types = ['AUTH_REQUIRED', 'DATA_CORRUPT', 'SCHEMA_INVALID']
        return any(e['type'] in critical_types for e in self.errors)
    
    def get_report(self) -> str:
        report = "# Extraction Error Report\n\n"
        report += f"Total Errors: {len(self.errors)}\n"
        report += f"Total Warnings: {len(self.warnings)}\n\n"
        
        if self.errors:
            report += "## Errors\n"
            for e in self.errors:
                report += f"- [{e['type']}] {e['message']}\n"
        
        return report
```

---

## 8. Implementation Checklist

### Pre-Extraction
- [ ] Install all required dependencies
- [ ] Configure Playwright with Chromium browser
- [ ] Set up logging and error tracking
- [ ] Verify network access to target URL

### Phase 1: Discovery
- [ ] Initialize headless browser with network monitoring
- [ ] Navigate to target URL
- [ ] Capture all XHR/Fetch requests
- [ ] Identify primary JSON data payload
- [ ] Probe asset directories if API not found
- [ ] Download and save raw data files

### Phase 2: Complex Data Extraction
- [ ] Download JavaScript bundles
- [ ] Search for calculator functions with regex
- [ ] Extract and convert calculator logic to JSON Logic
- [ ] Parse SVG flowcharts to Mermaid.js
- [ ] Transcribe image-based flowcharts with Vision LLM
- [ ] Validate all extracted calculators

### Phase 3: Structuring
- [ ] Normalize all data to Ground Truth schema
- [ ] Calculate checksums for all guidelines
- [ ] Run conflict detection algorithm
- [ ] Generate conflict report if issues found
- [ ] Update version tracking database

### Phase 4: Validation
- [ ] Convert raw content to Markdown
- [ ] Apply semantic chunking
- [ ] Run verification pass against originals
- [ ] Generate completeness scores
- [ ] Create final extraction report

### Post-Extraction
- [ ] Save extracted data to output directory
- [ ] Export version tracking table
- [ ] Archive raw extraction artifacts
- [ ] Clean up temporary files
- [ ] Document any manual interventions required

---

## Appendix: Quick Commands

```bash
# Install dependencies
pip install playwright beautifulsoup4 pandas
playwright install chromium

# Run extraction
python extract_cmg.py --url https://cmg.example.com --output ./data/

# Validate extraction
python validate.py --input ./data/guidelines.json

# Generate conflict report
python conflicts.py --input ./data/guidelines.json --report conflicts.md

# Export to different formats
python export.py --input ./data/guidelines.json --format csv
python export.py --input ./data/guidelines.json --format markdown
```

---

*This guideline is intended for AI agents performing automated data extraction. For human operators, refer to the full Word document version for additional context and explanations.*
