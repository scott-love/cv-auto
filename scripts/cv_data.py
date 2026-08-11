#!/usr/bin/env python3
"""Shared CV data loading, splitting, and publication indexing helpers."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("Error: PyYAML is not installed. Run: pip install pyyaml")


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_FILE = REPO_ROOT / "data" / "cv.base.yaml"
DEFAULT_PUBLICATIONS_FILE = REPO_ROOT / "data" / "publications.yaml"
LEGACY_CV_FILE = REPO_ROOT / "data" / "cv.yaml"

PUBLICATION_SECTIONS = (
    "journal_articles",
    "book_chapters",
    "under_review_or_in_prep",
)
PUBLICATION_LIKE_SECTIONS = PUBLICATION_SECTIONS + ("conference_presentations",)
DEFAULT_SECTION_ORDER = [
    "education",
    "professional_experience",
    "funding",
    "honors_awards",
    "languages",
    "publications",
    "conference_presentations",
]

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping or exit with a clear message."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError:
        sys.exit(f"Error: YAML file not found: {path}")
    except yaml.YAMLError as exc:
        sys.exit(f"Error: Malformed YAML in {path}:\n{exc}")
    if data is None:
        return {}
    if not isinstance(data, dict):
        sys.exit(f"Error: Expected a mapping at the top level of {path}")
    return data


def save_yaml(path: Path, data: dict[str, Any], header: str | None = None) -> None:
    """Write YAML with optional header comment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        if header:
            handle.write(header)
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_year(value: Any) -> Any:
    if value in (None, ""):
        return ""
    text = normalize_text(value)
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else text


def publication_like_entry_defaults(section: str) -> dict[str, Any]:
    base = {"sync": "auto", "index": 0}
    if section == "conference_presentations":
        base.update(
            {
                "authors": [],
                "year": "",
                "title": "",
                "type": "poster",
                "venue": "",
                "location": "",
                "date": "",
            }
        )
        return base
    base.update(
        {
            "authors": [],
            "year": "",
            "title": "",
            "journal": "",
            "book": "",
            "editors": [],
            "publisher": "",
            "status": "",
            "volume": "",
            "pages": "",
            "impact_factor": "",
            "quartile": "",
            "doi": "",
            "url": "",
            "publication_type": "",
            "primary_source": "",
            "source_ids": {},
            "last_synced": "",
        }
    )
    return base


def normalize_publication_like_entry(record: dict[str, Any], section: str) -> dict[str, Any]:
    normalized = copy.deepcopy(publication_like_entry_defaults(section))
    normalized.update(record or {})
    normalized["authors"] = list((record or {}).get("authors") or [])
    normalized["sync"] = normalize_text(normalized.get("sync") or "auto") or "auto"
    normalized["index"] = int(normalized.get("index") or 0)
    normalized["year"] = normalize_year(normalized.get("year"))
    normalized["title"] = normalize_text(normalized.get("title"))
    if section == "conference_presentations":
        normalized["type"] = normalize_text(normalized.get("type") or "poster") or "poster"
        normalized["venue"] = normalize_text(normalized.get("venue"))
        normalized["location"] = normalize_text(normalized.get("location"))
        normalized["date"] = normalize_text(normalized.get("date"))
        return normalized

    normalized["editors"] = list((record or {}).get("editors") or [])
    normalized["journal"] = normalize_text(normalized.get("journal"))
    normalized["book"] = normalize_text(normalized.get("book"))
    normalized["publisher"] = normalize_text(normalized.get("publisher"))
    normalized["status"] = normalize_text(normalized.get("status"))
    normalized["volume"] = normalize_text(normalized.get("volume"))
    normalized["pages"] = normalize_text(normalized.get("pages"))
    normalized["impact_factor"] = normalize_text(normalized.get("impact_factor"))
    normalized["quartile"] = normalize_text(normalized.get("quartile"))
    normalized["doi"] = normalize_text(normalized.get("doi"))
    normalized["url"] = normalize_text(normalized.get("url"))
    normalized["publication_type"] = normalize_text(normalized.get("publication_type"))
    normalized["primary_source"] = normalize_text(normalized.get("primary_source"))
    normalized["source_ids"] = dict((record or {}).get("source_ids") or {})
    normalized["last_synced"] = normalize_text(normalized.get("last_synced"))
    if not normalized["last_synced"]:
        normalized.pop("last_synced", None)
    return normalized


def _date_parts(record: dict[str, Any]) -> tuple[int, int, str]:
    date_text = normalize_text(record.get("date"))
    if not date_text:
        return 0, 0, ""
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", date_text)
    if iso_match:
        return int(iso_match.group(2)), int(iso_match.group(3)), date_text.lower()
    month_match = re.search(
        r"\b("
        + "|".join(MONTHS)
        + r")\b(?:\s+(\d{1,2}))?",
        date_text,
        re.IGNORECASE,
    )
    if not month_match:
        return 0, 0, date_text.lower()
    month = MONTHS[month_match.group(1).lower()]
    day = int(month_match.group(2) or 0)
    return month, day, date_text.lower()


def publication_sort_key(record: dict[str, Any], section: str) -> tuple[Any, ...]:
    year = normalize_year(record.get("year"))
    year_key = year if isinstance(year, int) else -1
    month_key, day_key, date_text = _date_parts(record)
    venue_key = normalize_text(
        record.get("venue") or record.get("journal") or record.get("book") or record.get("publisher")
    ).lower()
    title_key = normalize_text(record.get("title")).lower()
    type_key = normalize_text(record.get("type") or record.get("publication_type")).lower()
    return (-year_key, -month_key, -day_key, title_key, venue_key, date_text, type_key, section)


def _normalize_publication_payload(publications_data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"publications": {}, "conference_presentations": []}
    publications = publications_data.get("publications")
    if not isinstance(publications, dict):
        publications = {}
    for section in PUBLICATION_SECTIONS:
        records = publications.get(section) or []
        if not isinstance(records, list):
            records = []
        normalized["publications"][section] = [
            normalize_publication_like_entry(record, section) for record in records
        ]
    conference_records = publications_data.get("conference_presentations") or []
    if not isinstance(conference_records, list):
        conference_records = []
    normalized["conference_presentations"] = [
        normalize_publication_like_entry(record, "conference_presentations")
        for record in conference_records
    ]
    return normalized


def assign_publication_indices(
    publications_data: dict[str, Any],
    reverse_numbering: bool = False,
) -> dict[str, Any]:
    """Sort publication-like sections deterministically and assign index values."""
    normalized = _normalize_publication_payload(publications_data)
    for section in PUBLICATION_SECTIONS:
        records = sorted(
            normalized["publications"][section],
            key=lambda record: publication_sort_key(record, section),
        )
        count = len(records)
        for offset, record in enumerate(records, start=1):
            record["index"] = count - offset + 1 if reverse_numbering else offset
        normalized["publications"][section] = records

    conferences = sorted(
        normalized["conference_presentations"],
        key=lambda record: publication_sort_key(record, "conference_presentations"),
    )
    count = len(conferences)
    for offset, record in enumerate(conferences, start=1):
        record["index"] = count - offset + 1 if reverse_numbering else offset
    normalized["conference_presentations"] = conferences
    return normalized


def split_cv_data(cv_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a legacy mixed CV mapping into base data and publication data."""
    merged = copy.deepcopy(cv_data or {})
    merged.pop("skills", None)

    base = copy.deepcopy(merged)
    publications_data = {
        "publications": copy.deepcopy(base.pop("publications", {}) or {}),
        "conference_presentations": copy.deepcopy(base.pop("conference_presentations", []) or []),
    }
    base.setdefault("cv", {})
    base["cv"].setdefault("section_order", list(DEFAULT_SECTION_ORDER))
    base["cv"]["section_order"] = [
        section for section in base["cv"].get("section_order", []) if section != "skills"
    ] or list(DEFAULT_SECTION_ORDER)
    base.setdefault("funding", [])
    normalized_publications = assign_publication_indices(
        publications_data,
        reverse_numbering=bool((base.get("cv") or {}).get("pub_reverse_numbering", False)),
    )
    return base, normalized_publications


def merge_cv_data(base_data: dict[str, Any] | None, publications_data: dict[str, Any] | None) -> dict[str, Any]:
    """Merge split base/publication files into a single renderable mapping."""
    merged = copy.deepcopy(base_data or {})
    merged.pop("skills", None)
    merged.setdefault("cv", {})
    section_order = merged["cv"].get("section_order") or list(DEFAULT_SECTION_ORDER)
    merged["cv"]["section_order"] = [section for section in section_order if section != "skills"] or list(
        DEFAULT_SECTION_ORDER
    )
    merged.setdefault("funding", [])

    normalized_publications = assign_publication_indices(
        publications_data or {},
        reverse_numbering=bool((merged.get("cv") or {}).get("pub_reverse_numbering", False)),
    )
    merged["publications"] = normalized_publications["publications"]
    merged["conference_presentations"] = normalized_publications["conference_presentations"]
    return merged


def load_cv_data(
    input_path: Path | None = None,
    base_file: Path | None = None,
    publications_file: Path | None = None,
) -> dict[str, Any]:
    """Load CV data from either legacy or split-file layouts."""
    if input_path is not None:
        base, publications = split_cv_data(load_yaml(input_path))
        return merge_cv_data(base, publications)

    base_path = base_file or DEFAULT_BASE_FILE
    publications_path = publications_file or DEFAULT_PUBLICATIONS_FILE

    if base_path.exists() or publications_path.exists():
        base_data = load_yaml(base_path) if base_path.exists() else {}
        publications_data = load_yaml(publications_path) if publications_path.exists() else {}
        return merge_cv_data(base_data, publications_data)

    if LEGACY_CV_FILE.exists():
        base, publications = split_cv_data(load_yaml(LEGACY_CV_FILE))
        return merge_cv_data(base, publications)

    sys.exit(
        "Error: Could not find split CV data files "
        f"({base_path}, {publications_path}) or legacy file {LEGACY_CV_FILE}"
    )


def publication_payload_from_cv(cv_data: dict[str, Any]) -> dict[str, Any]:
    """Extract publication-focused data from a merged CV mapping."""
    _, publications = split_cv_data(cv_data)
    return publications
