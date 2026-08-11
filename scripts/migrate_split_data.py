#!/usr/bin/env python3
"""Split a legacy data/cv.yaml file into cv.base.yaml and publications.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cv_data import (
    DEFAULT_BASE_FILE,
    DEFAULT_PUBLICATIONS_FILE,
    LEGACY_CV_FILE,
    load_yaml,
    save_yaml,
    split_cv_data,
)


BASE_HEADER = """\
# ==============================================================================
# cv.base.yaml — Canonical manually maintained CV data
# Migrated from legacy data/cv.yaml
# ==============================================================================
"""

PUBLICATIONS_HEADER = """\
# ==============================================================================
# publications.yaml — Publication-focused CV data
# Migrated from legacy data/cv.yaml
# ==============================================================================
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(LEGACY_CV_FILE),
        help=f"Path to legacy mixed CV YAML (default: {LEGACY_CV_FILE})",
    )
    parser.add_argument(
        "--base-file",
        default=str(DEFAULT_BASE_FILE),
        help=f"Path for cv.base.yaml output (default: {DEFAULT_BASE_FILE})",
    )
    parser.add_argument(
        "--publications-file",
        default=str(DEFAULT_PUBLICATIONS_FILE),
        help=f"Path for publications.yaml output (default: {DEFAULT_PUBLICATIONS_FILE})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = Path(args.input)
    base_file = Path(args.base_file)
    publications_file = Path(args.publications_file)

    legacy_data = load_yaml(source)
    base_data, publications_data = split_cv_data(legacy_data)
    save_yaml(base_file, base_data, header=BASE_HEADER)
    save_yaml(publications_file, publications_data, header=PUBLICATIONS_HEADER)

    print(f"Migrated {source} into:")
    print(f"  - {base_file}")
    print(f"  - {publications_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
