# cv-auto: semi-automatic academic CV workflow

This repository keeps CV data in simple YAML and renders it to LaTeX.

## Current source-of-truth layout

```text
data/
├── cv.base.yaml        # manual canonical CV data (no publications)
├── publications.yaml   # publication-like data managed by sync/manual overrides
└── cv.yaml             # legacy combined file kept for compatibility/migration
```

- `data/cv.base.yaml` is the long-term manual source of truth.
- `data/publications.yaml` stores:
  - `publications.journal_articles`
  - `publications.book_chapters`
  - `publications.under_review_or_in_prep`
  - `conference_presentations`
- Overleaf/LaTeX input is a **one-time seed**, not an ongoing source of truth.

## Publication record model

All publication-like entries support:

```yaml
sync: auto    # or manual
index: 1
```

Conference presentations now use the same `sync` / `index` shape as the other
publication categories.

Indices are assigned centrally by repository scripts using deterministic
chronological ordering from `year`, then `date` when present, with stable text
fallbacks.

## Common commands

### Generate LaTeX from split files

```bash
python scripts/generate_latex.py \
  --base-file data/cv.base.yaml \
  --publications-file data/publications.yaml \
  --output build/cv.tex
```

If split files are absent, generation still falls back to legacy `data/cv.yaml`.

### Sync publications

Preview:

```bash
python scripts/sync_publications_hal.py --dry-run
```

Apply to the canonical publication file:

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --publications-file data/publications.yaml \
  --output-file data/publications.yaml
```

Optional legacy mixed-file mode still works:

```bash
python scripts/sync_publications_hal.py \
  --cv-file data/cv.yaml \
  --dry-run
```

### Extract from a seed LaTeX CV

```bash
python scripts/extract_from_latex.py \
  --input source-material/cv_full_seed.tex \
  --output-base data/cv.base.yaml \
  --output-publications data/publications.yaml
```

Optional legacy combined export:

```bash
python scripts/extract_from_latex.py \
  --input source-material/cv_full_seed.tex \
  --output data/cv.yaml
```

### Migrate an existing legacy `data/cv.yaml`

```bash
python scripts/migrate_split_data.py \
  --input data/cv.yaml \
  --base-file data/cv.base.yaml \
  --publications-file data/publications.yaml
```

## Manual override behavior

- `sync: auto`: sync may update the record
- `sync: manual`: sync must not overwrite the record
- `publication_sync.manual_overrides` in `cv.base.yaml` can additionally protect
  DOI/title matches

## HAL classification and overrides

`scripts/sync_publications_hal.py` now classifies HAL records using multiple HAL
fields (`docType[_s]`, `subType[_s]`, conference/journal titles, and
communication hints) with conservative fallback behavior:

- recognized journal articles remain in `publications.journal_articles`
- recognized book/chapter records go to `publications.book_chapters`
- communications, posters, theses/HDR, reports, patents, and unknown/ambiguous
  records are kept out of `journal_articles` and mapped conservatively to
  `publications.under_review_or_in_prep`
- poster indicators such as `affiche` and `poster` are tagged as
  `conference-poster` publication type

To force a classification without changing code, edit
`data/publications_overrides.yml`:

```yaml
hal:hal-01234567:
  category: conference_posters
doi:10.1234/example.doi:
  category: journal_articles
```

Unknown override categories are ignored with a warning.

## Removed section

The `skills` section has been removed from the data model, template rendering,
generator summary output, and docs.

## Validation

Run the focused test suite with:

```bash
python -m pytest tests/ -q
```
