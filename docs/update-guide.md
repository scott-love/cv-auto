# Update guide

## Source of truth
The long-term source of truth for the CV should be structured data in `data/`.
The existing Overleaf LaTeX files are only a seed source for the initial import.

## Where to put source material
Place imported Overleaf files, PDFs, exports, and reference snapshots in `source-material/`.

Suggested contents:
- original `.tex` files
- `.sty` files
- `.cls` files
- exported PDF
- notes about what was imported and from where

## How updates should work
1. Update structured data in `data/`
2. Review generated LaTeX output in `build/` or equivalent
3. Rebuild the PDF if needed
4. Only edit templates when the layout or style should change

## Manual override policy
If imported publication or CV data is incomplete or incorrect:
- fix it in the structured data
- do not patch generated files by hand
- keep overrides explicit and documented

## Good next automation steps
- structured CV schema
- LaTeX generator
- publication import from ORCID / HAL / OpenAlex
- PDF build workflow
