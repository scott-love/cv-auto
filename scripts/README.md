# Scripts

Key scripts:

- `extract_from_latex.py` — one-time extraction from a seed LaTeX CV into split YAML files
- `generate_latex.py` — merge split YAML data and render LaTeX
- `sync_publications_hal.py` — sync publication metadata from HAL/ORCID
- `migrate_split_data.py` — split legacy `data/cv.yaml` into `cv.base.yaml` and `publications.yaml`
- `cv_data.py` — shared helpers for loading, merging, and chronological publication indexing
