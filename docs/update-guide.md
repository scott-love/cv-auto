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

Publication sections under `publications` are expected to be lists
(`journal_articles`, `book_chapters`, `under_review_or_in_prep`). If a section
is `null` or another type, sync now auto-recovers by treating it as an empty
list and reports a warning in the sync output.

## Publication sync workflow

Sync reads `data/cv.yaml` (the canonical source) and writes merged output to a
**separate file** (`data/cv.synced.yaml`) by default. The canonical file is never
overwritten automatically, so your hand-written comments and edits are preserved.

Preview first (no files changed):

```bash
python scripts/sync_publications_hal.py --dry-run
```

Use a specific source mode when needed:

```bash
python scripts/sync_publications_hal.py --dry-run --source-mode hal_only
python scripts/sync_publications_hal.py --dry-run --source-mode orcid_only
python scripts/sync_publications_hal.py --dry-run --source-mode hal_plus_orcid
```

Apply changes to the default synced output file (`data/cv.synced.yaml`):

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --report-file build/publication-sync-report.md
```

The file `data/cv.synced.yaml` is generated and carries a header comment
indicating it is auto-generated — do not edit it manually.

To explicitly overwrite the canonical file (use with care):

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --output-file data/cv.yaml \
  --report-file build/publication-sync-report.md
```

To write to a custom path:

```bash
python scripts/sync_publications_hal.py \
  --apply \
  --output-file data/my-review.yaml
```

### CLI options

| Option | Default | Description |
|---|---|---|
| `--cv-file` | `data/cv.yaml` | Canonical input file |
| `--output-file` | `data/cv.synced.yaml` | Where merged output is written |
| `--source-mode` | from config | `hal_only` / `orcid_only` / `hal_plus_orcid` |
| `--hal-id` | from `personal.id_hal` | HAL author identifier |
| `--orcid` | from `personal.orcid` | ORCID identifier |
| `--report-file` | none | Markdown report path (apply mode only) |
| `--dry-run` | — | Preview without writing files |
| `--apply` | — | Write output to `--output-file` |

### Preprint dedup policy

After merging, the sync script detects records in `journal_articles` whose
`publication_type` indicates a preprint/non-final version (e.g. `other`,
`report`, `preprint`) and whose title exactly matches an existing
`journal-article` record. These duplicate preprint records are automatically:

- reclassified to `publication_type: preprint`
- moved to `under_review_or_in_prep`
- tagged with a `status` field noting which published DOI supersedes them

This prevents a Zenodo preprint from appearing as a duplicate journal article.
The sync report includes a **Deduped preprints** section listing all such actions.

## Funding section

Funding entries are stored under the `funding` key as a list:

```yaml
funding:
  - years: "2021 - 2024"
    description: >-
      ANR JCJC – (SheepVoicefMRI) Neuroimagerie fonctionnelle des mécanismes
      de la perception des voix chez le mouton. 200k€. Coordination : S. Love.
  - years: "2024 - 2026"
    description: >-
      American NIH - Towards High-Resolution Neuro-Behavioral Quantification …
```

This section is extracted from `\section{Funding}` in the seed LaTeX.  Multi-line
`\cvitem` entries are joined automatically during extraction.

## Section ordering

The order in which sections appear in the generated CV is controlled by
`cv.section_order` in `data/cv.yaml`:

```yaml
cv:
  section_order:
    - education
    - professional_experience
    - funding
    - honors_awards
    - skills
    - languages
    - publications
    - conference_presentations
```

Supported section keys: `education`, `professional_experience`, `funding`,
`honors_awards`, `skills`, `languages`, `publications`,
`conference_presentations`.

If `section_order` is absent the default order above is used (backward
compatible with existing `cv.yaml` files that predate this key).

To reorder, simply rearrange the list.  To hide a section, remove it from the
list.

## Reverse publication numbering

Set `cv.pub_reverse_numbering: true` to display the highest number next to the
most recent publication (matching common academic CV conventions):

```yaml
cv:
  pub_reverse_numbering: true   # newest entry gets the highest label
```

Applies to journal articles, book chapters, under-review items, and conference
presentations.  Default is `false` (chronological forward numbering).


- structured CV schema
- LaTeX generator
- publication import from ORCID / HAL / OpenAlex
- PDF build workflow
