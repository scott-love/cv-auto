# Academic CV Automation Roadmap

## Overview
Build a free, maintainable workflow for an academic CV that starts from an existing Overleaf LaTeX CV and evolves into a structured, semi-automatic repository-based system.

## Goals
- Use the existing Overleaf CV as a one-time seed.
- Extract CV content into a structured format.
- Keep the CV easy to update manually.
- Synchronize publication data from free sources where possible.
- Avoid paid services and vendor lock-in.
- Preserve a clear, reproducible build process.

## Current source materials
The repository is intended to hold the existing Overleaf CV source files in `source-material/`.
These files are the seed input for the first extraction pass.

## Preferred source priority
1. Existing Overleaf LaTeX source / exported PDF
2. ORCID
3. HAL
4. OpenAlex / Crossref / PubMed / arXiv
5. Google Scholar only as a fallback

## Planned repository structure
A simple structure is preferred:

- `data/`
  - structured CV content
  - publication records
- `templates/`
  - LaTeX templates or partials
- `scripts/`
  - import / sync scripts
  - export / generation scripts
- `docs/`
  - roadmap
  - update instructions
  - data model notes
- `source-material/`
  - imported Overleaf assets
- `build/`
  - generated `.tex`
  - generated `.pdf` if desired

## Phase 1: Extract the current CV into structured data
### Objectives
- Identify every section in the existing LaTeX CV.
- Convert the content into a machine-readable format.
- Preserve manual details that matter for the current CV layout.

### Likely data model
Use a structured format that is easy to edit manually:
- YAML is likely the best default
- JSON is acceptable if better for tooling

### Extraction targets
- personal details
- education
- professional experience
- teaching
- honors and awards
- skills
- languages
- publications
- conference presentations
- any optional or future sections

### Deliverable
A structured CV source file representing the current CV content.

## Phase 2: Generate the LaTeX CV from structured data
### Objectives
- Render the CV from the structured source instead of editing LaTeX manually.
- Keep the current ModernCV look initially, if possible.

### Tasks
- Map data fields to LaTeX template blocks.
- Keep formatting logic in templates, not in data.
- Support section ordering and optional subsections.
- Ensure generated output is reproducible.

### Deliverable
A generated `.tex` file that can be compiled into the existing CV format.

## Phase 3: Publication synchronization
### Objectives
- Import publication metadata from free sources.
- Avoid duplicate or stale records.

### Preferred connectors
- ORCID
- HAL
- OpenAlex
- Crossref
- PubMed / arXiv as needed

### Strategy
- Match records using DOI first when available.
- Fall back to title/author/year matching when necessary.
- Keep uncertain matches for manual review.
- Allow manual overrides for items not captured by public APIs.

### Deliverable
A publication sync script or workflow that updates publication entries semi-automatically.

## Phase 4: Ongoing maintenance
### Objectives
- Make future updates quick and low-risk.
- Keep the workflow transparent.

### Tasks
- Document how to update the structured data manually.
- Document how to run import/sync scripts.
- Add validation for required fields and formats.
- Separate source data from generated output.
- Optionally add PDF generation via GitHub Actions.

### Deliverable
A stable workflow where the CV is easy to maintain without editing the LaTeX by hand.

## Nice-to-have improvements
- BibTeX or citation export
- Multiple CV variants for different applications
- English and French versions
- Automated PDF builds
- An academic profile page or personal website
- A changelog of CV updates
- Support for changing the CV style or theme without rewriting the content
- Additional ModernCV styles or alternative LaTeX templates

## Decisions to make early
- Canonical data format: YAML vs JSON
- Whether to keep the current ModernCV layout or simplify
- Which publication source should be treated as primary
- How to handle incomplete or conflicting publication metadata
- Whether to generate a single CV or multiple variants
- How much style flexibility to build in from the beginning

## Suggested next step
Create the structured CV data model and begin a one-time import from the Overleaf LaTeX source.
