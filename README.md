# cv-auto

Free, semi-automatic workflow for maintaining an academic CV.

## Goals
- Seed from an existing Overleaf/LaTeX CV
- Extract CV content into structured data once
- Keep manual updates simple and transparent
- Sync publications from free sources where possible
- Avoid paid services and vendor lock-in

## Repository layout
- `data/` — structured CV source data
- `templates/` — LaTeX templates and partials
- `scripts/` — import, sync, and generation scripts
- `docs/` — roadmap and update instructions
- `source-material/` — imported Overleaf source files and exports
- `build/` — generated output (ignored or regenerated as needed)

## Next steps
1. Add the existing Overleaf CV source to `source-material/`
2. Convert the CV into structured data in `data/`
3. Add a generator to produce LaTeX from the structured data
4. Add publication sync support for ORCID, HAL, and OpenAlex/Crossref
5. Document the manual override workflow
