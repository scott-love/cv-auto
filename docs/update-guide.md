# Update guide

## Source of truth
The long-term source of truth for the CV should be structured data in `data/`.
The existing Overleaf LaTeX files are only a seed source for the initial import.
Publication sync sources such as HAL and ORCID are upstream providers, not
repository ground truth.

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
2. Optionally sync publications from HAL and/or ORCID into `data/cv.yaml`
3. Review generated LaTeX output in `build/` or equivalent
4. Rebuild the PDF if needed
5. Only edit templates when the layout or style should change

## Manual override policy
If imported publication or CV data is incomplete or incorrect:
- fix it in the structured data
- do not patch generated files by hand
- keep overrides explicit and documented

For publications specifically:
- `sync: manual` entries are never overwritten
- `publication_sync.manual_overrides` can block specific DOI/title matches
- local/manual values win over synced values
- HAL is preferred for publication type/category when sync updates an
  auto-managed record
- ORCID remains optional and mainly fills missing metadata

## Publication sync configuration

`data/cv.yaml` now stores personal identifiers and sync policy together:

```yaml
personal:
  orcid: "0000-0001-7416-9210"
  id_hal: "scott-love"

publication_sync:
  source_mode: hal_plus_orcid  # hal_only | orcid_only | hal_plus_orcid
  sources:
    hal: true
    orcid: true
  manual_overrides: []
```

If `--hal-id` is not passed on the command line, the sync script uses
`personal.id_hal`. If `--orcid` is not passed, it uses `personal.orcid`.

## Publication sync workflow

Preview first:

```bash
python scripts/sync_publications_hal.py --dry-run
```

Use a specific source mode when needed:

```bash
python scripts/sync_publications_hal.py --dry-run --source-mode hal_only
python scripts/sync_publications_hal.py --dry-run --source-mode orcid_only
python scripts/sync_publications_hal.py --dry-run --source-mode hal_plus_orcid
```

Apply changes after review:

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --report-file build/publication-sync-report.md
```

## Good next automation steps
- structured CV schema
- LaTeX generator
- publication import from ORCID / HAL / OpenAlex
- PDF build workflow
