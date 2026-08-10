# cv-auto: Semi-automatic Academic CV Workflow

A free, maintainable workflow for keeping an academic CV up-to-date using **structured data** and **publication sync** from public repositories.

## Overview

This project helps you:

- ✅ **Start from an existing Overleaf/LaTeX CV** (or any moderncv LaTeX source)
- ✅ **Extract CV content once** into structured YAML data
- ✅ **Keep the CV easy to update** by editing YAML or Overleaf (your choice)
- ✅ **Automatically sync publications** from HAL and ORCID
- ✅ **Generate a fresh LaTeX CV** whenever you want
- ✅ **Avoid vendor lock-in** — everything is free, open, and reproducible

## Repository Structure

```
cv-auto/
├── data/
│   ├── cv.yaml              ← Your canonical CV data (hand-edited or auto-generated)
│   └── README.md            ← Data format guide
├── scripts/
│   ├── extract_from_latex.py    ← Parse LaTeX → YAML (Phase 1)
│   ├── generate_latex.py        ← Render YAML → LaTeX (Phase 2)
│   ├── sync_publications_hal.py ← Auto-import publications from HAL/ORCID (Phase 3)
│   └── README.md
├── templates/
│   ├── cv.tex.j2           ← Jinja2 template for CV
│   ├── moderncv.cls        ← moderncv LaTeX class
│   ├── moderncv*.sty       ← Color and style packages
│   └── README.md
├── source-material/
│   ├── cv_7.tex            ← Your original Overleaf LaTeX source
│   ├── pictures/           ← Photo for CV
│   └── *.sty, *.cls        ← Moderncv support files
├── build/
│   └── cv.tex              ← Generated LaTeX (not committed)
├── docs/
│   └── UPDATE_GUIDE.md     ← Detailed update instructions
└── README.md               ← This file
```

## Workflow at a Glance

```
Overleaf/source-material/cv_7.tex
          ↓
    [Phase 1: Extract]
          ↓
    data/cv.yaml ← Edit here manually, or regenerate from LaTeX
          ↓
    [Phase 2: Generate]
          ↓
    build/cv.tex → Compile to PDF
          ↓
    build/cv.pdf
```

**Optional Phase 3: Publication Sync**

```
HAL API / ORCID API
          ↓
    [sync_publications_hal.py]
          ↓
    Merges new publications into data/cv.yaml
    (respects manual entries)
```

---

## Quick Start

### Prerequisites

```bash
pip install jinja2 pyyaml requests
```

(LaTeX distribution optional, but needed to compile PDF)

### 1. Extract from your LaTeX CV

If you have an existing Overleaf CV (moderncv format), parse it once:

```bash
python scripts/extract_from_latex.py \
  --input source-material/cv_7.tex \
  --output data/cv.yaml
```

**Output:**
- `data/cv.yaml` — structured, editable CV data
- Console summary of what was extracted

### 2. Generate LaTeX from your data

Whenever you update `data/cv.yaml`, regenerate the LaTeX:

```bash
python scripts/generate_latex.py \
  --input data/cv.yaml \
  --output build/cv.tex
```

### 3. Compile to PDF (optional)

```bash
cp templates/*.cls templates/*.sty build/
cd build && pdflatex cv.tex
```

This produces `build/cv.pdf`.

### 4. Sync publications from HAL/ORCID (optional)

```bash
python scripts/sync_publications_hal.py \
  --hal-author "scott-love" \
  --orcid "0000-0001-7416-9210" \
  --cv-file data/cv.yaml
```

This script:
- Fetches your publications from HAL and ORCID
- Merges new entries into `data/cv.yaml`
- Preserves any entries you marked as `sync: manual`
- Asks before overwriting existing entries

---

## CV Data Format (`data/cv.yaml`)

The CV data is organized into sections:

```yaml
personal:
  firstname: Scott
  familyname: "Love, PhD"
  email: love.a.scott@gmail.com
  orcid: "0000-0001-7416-9210"  # manual

education:
  - degree: "Ph.D. Psychology"
    institution: "The University of Glasgow"
    # ... more fields

experience:
  research:
    - position: "Chargé de Recherche"
      institution: "INRAE, CNRS, Université de Tours"
      # ...
  teaching:
    - course: "Master 2 — Cognition, neurosciences et psychologie"
      # ...

publications:
  journal_articles:
    - sync: auto   # ← auto-updated by sync script
      authors: [...]
      year: 2024
      title: "..."
      journal: "..."
      # ... more fields
  book_chapters:
    - sync: manual   # ← never overwritten
      # ...
```

### Sync Markers

- **`sync: auto`** — Entry may be updated by sync scripts. Use this for citations fetched from APIs.
- **`sync: manual`** — Entry is hand-maintained. Sync scripts will never overwrite it.

See `data/README.md` for full field documentation.

---

## Updating Your CV

### **Option A: Edit `data/cv.yaml` directly**

Edit the YAML file by hand, then regenerate:

```bash
python scripts/generate_latex.py
```

Good for:
- Quick updates to personal info, experience, awards
- Adding manual overrides to publications

### **Option B: Update Overleaf, re-extract**

Edit your original CV in Overleaf, download as `.tex`, then:

```bash
python scripts/extract_from_latex.py
```

Good for:
- Maintaining a single "pretty" version in Overleaf
- Periodic bulk imports

### **Option C: Sync publications, edit entries**

Auto-import new publications, then refine manually:

```bash
python scripts/sync_publications_hal.py
```

Then edit `data/cv.yaml` as needed.

---

## Configuration

### HAL Author ID

Find your HAL author ID:
1. Go to https://hal.archives-ouvertes.fr/
2. Search for your name
3. Click your profile
4. Your ID is in the URL: `https://hal.archives-ouvertes.fr/search/index/?q=scott-love` → use `scott-love`

Or set it in the script call:
```bash
python scripts/sync_publications_hal.py --hal-author "scott-love"
```

### ORCID

Your ORCID is already in `data/cv.yaml`:
```yaml
personal:
  orcid: "0000-0001-7416-9210"
```

---

## Advanced: Manual Publication Overrides

To **prevent a publication from being updated** by sync scripts, mark it as `manual`:

```yaml
publications:
  journal_articles:
    - sync: manual   # ← Won't be overwritten
      title: "My Paper"
      # Your manual fields
```

To **never sync specific publications**, list their DOIs or titles in the YAML:

```yaml
publication_sync:
  manual_overrides:
    - doi: "10.1234/example"
    - title: "A Paper I Want to Keep Exactly As Is"
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'jinja2'"

Install dependencies:
```bash
pip install jinja2 pyyaml requests
```

### LaTeX extraction produced empty sections

Check that your LaTeX uses `moderncv` syntax:
- `\section{Education}`
- `\cventry{dates}{title}{inst}{loc}{grade}{desc}`
- `\cvitem{label}{text}`

See `scripts/extract_from_latex.py` docstring for supported macros.

### Publication sync fetched too many / too few results

- Check your HAL author ID (should be lowercase with hyphens)
- Check your ORCID is correct
- Manually add/remove entries and mark them `sync: manual` if needed

---

## Project Phases

### Phase 1: Extraction ✅
Extract CV content from LaTeX into structured YAML.

**Status:** Complete  
**Script:** `scripts/extract_from_latex.py`  
**Output:** `data/cv.yaml`

### Phase 2: Generation ✅
Render YAML data into a fresh LaTeX CV using Jinja2.

**Status:** Complete  
**Script:** `scripts/generate_latex.py`  
**Output:** `build/cv.tex`

### Phase 3: Publication Sync 🚧
Auto-sync publications from HAL and ORCID.

**Status:** In progress  
**Script:** `scripts/sync_publications_hal.py`  
**Sources:** HAL (France), ORCID (global)

---

## Design Philosophy

✅ **Free & open** — No paid APIs, no vendor lock-in  
✅ **Transparent** — Everything is YAML and plain Python  
✅ **Reproducible** — Rebuild your CV anytime  
✅ **Flexible** — Manual overrides for anything  
✅ **Maintainable** — Update one place, regenerate everywhere  

---

## License

This project is provided as-is for personal use. The moderncv class and styles are licensed under the LPPL. See individual files for details.

---

## Next Steps

1. **Read** `docs/UPDATE_GUIDE.md` for detailed instructions
2. **Edit** `data/cv.yaml` to customize your CV
3. **Run** `python scripts/sync_publications_hal.py` to auto-import publications
4. **Generate** `build/cv.tex` and compile to PDF
5. **Commit** your changes to GitHub

Happy CV-building! 🚀
