# Update guide

## Source of truth

- Maintain non-publication CV content in `data/cv.base.yaml`
- Maintain publication-like content in `data/publications.yaml`
- Treat Overleaf/LaTeX as a one-time seed input only

## Publication data covered by `data/publications.yaml`

- `publications.journal_articles`
- `publications.book_chapters`
- `publications.under_review_or_in_prep`
- `conference_presentations`

Each entry supports:

```yaml
sync: auto    # or manual
index: 1
```

`conference_presentations` now follows the same shape as the other publication
categories.

## Normal workflow

1. Edit `data/cv.base.yaml` for manual CV content
2. Optionally sync/update `data/publications.yaml`
3. Regenerate LaTeX
4. Compile PDF if needed

## Generate

```bash
python scripts/generate_latex.py \
  --base-file data/cv.base.yaml \
  --publications-file data/publications.yaml \
  --output build/cv.tex
```

Legacy compatibility:

```bash
python scripts/generate_latex.py --input data/cv.yaml
```

## Sync publications

Preview:

```bash
python scripts/sync_publications_hal.py --dry-run
```

Write back to the canonical publication file:

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --publications-file data/publications.yaml \
  --output-file data/publications.yaml
```

Legacy mixed-file input remains available:

```bash
python scripts/sync_publications_hal.py \
  --cv-file data/cv.yaml \
  --dry-run
```

Manual protection rules:

- `sync: manual` blocks overwrite of that record
- `publication_sync.manual_overrides` in `data/cv.base.yaml` protects DOI/title matches

Classification behavior:

- HAL classification checks multiple fields (`docType[_s]`, `subType[_s]`,
  conference/journal titles, communication metadata) before assigning a
  publication section/type.
- Poster-like communications (for example `affiche`, `poster`) are tagged as
  `conference-poster`.
- Unknown or ambiguous HAL records are handled conservatively and are not
  defaulted into `journal_articles`.

Optional classification overrides:

- Use `data/publications_overrides.yml` to force categories by stable id:

```yaml
hal:hal-01234567:
  category: conference_posters
doi:10.1234/example.doi:
  category: journal_articles
```

- Overrides are applied after automatic classification.
- Unknown override categories are ignored and surfaced as warnings.

## Extract from LaTeX seed

```bash
python scripts/extract_from_latex.py \
  --input source-material/cv_full_seed.tex \
  --output-base data/cv.base.yaml \
  --output-publications data/publications.yaml
```

## Migrate from legacy `data/cv.yaml`

```bash
python scripts/migrate_split_data.py \
  --input data/cv.yaml \
  --base-file data/cv.base.yaml \
  --publications-file data/publications.yaml
```

Migration notes:

- `skills` is removed during migration
- publication indices are reassigned centrally
- generation still works with legacy `data/cv.yaml` if needed

## Section order

`cv.section_order` now supports:

- `education`
- `professional_experience`
- `funding`
- `honors_awards`
- `languages`
- `publications`
- `conference_presentations`

`skills` is no longer supported.
