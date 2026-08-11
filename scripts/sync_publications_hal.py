#!/usr/bin/env python3
"""
Sync publications from HAL and/or ORCID into split publication data.

Local YAML data remains the canonical source of truth. External services are
treated as upstream providers whose records are normalized, merged, and then
applied to the local structured data according to explicit precedence rules.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:
    sys.exit("Error: PyYAML is not installed. Run: pip install pyyaml")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cv_data import (
    DEFAULT_BASE_FILE,
    DEFAULT_PUBLICATIONS_FILE,
    LEGACY_CV_FILE,
    assign_publication_indices,
    load_yaml,
    load_cv_data,
    normalize_publication_like_entry,
    publication_payload_from_cv,
    save_yaml,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CV_FILE = LEGACY_CV_FILE
DEFAULT_SYNCED_FILE = DEFAULT_PUBLICATIONS_FILE

SECTION_FIELDS = {
    "journal_articles": [
        "authors",
        "year",
        "title",
        "journal",
        "volume",
        "pages",
        "impact_factor",
        "quartile",
        "doi",
        "url",
    ],
    "book_chapters": [
        "authors",
        "year",
        "title",
        "book",
        "editors",
        "publisher",
        "impact_factor",
        "quartile",
        "doi",
        "url",
    ],
    "under_review_or_in_prep": [
        "authors",
        "year",
        "title",
        "journal",
        "status",
        "doi",
        "url",
    ],
}

BASE_RECORD_DEFAULTS = {
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
    "sync": "auto",
    "publication_type": "",
    "primary_source": "",
    "source_ids": {},
    "last_synced": "",
}

HAL_TYPE_MAP = {
    "ART": ("journal_articles", "journal-article"),
    "COUV": ("book_chapters", "book-chapter"),
    "COMM": ("journal_articles", "conference-paper"),
    "OUV": ("journal_articles", "book"),
    "THESE": ("journal_articles", "thesis"),
    "UNDEFINED": ("journal_articles", "other"),
    "PATENT": ("journal_articles", "other"),
    "REPORT": ("journal_articles", "report"),
}

ORCID_TYPE_MAP = {
    "journal-article": ("journal_articles", "journal-article"),
    "book-chapter": ("book_chapters", "book-chapter"),
    "book-review": ("journal_articles", "other"),
    "book": ("journal_articles", "book"),
    "conference-paper": ("journal_articles", "conference-paper"),
    "conference-abstract": ("journal_articles", "conference-paper"),
    "working-paper": ("under_review_or_in_prep", "preprint"),
    "preprint": ("under_review_or_in_prep", "preprint"),
    "dissertation": ("journal_articles", "thesis"),
    "report": ("journal_articles", "report"),
    "other": ("journal_articles", "other"),
}


@dataclass
class SyncConfig:
    cv_file: Path | None
    base_file: Path
    publications_file: Path
    output_file: Path
    source_mode: str
    hal_id: str
    orcid: str
    apply_changes: bool
    report_file: Path | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cv-file",
        help="Optional legacy mixed CV file (for example data/cv.yaml)",
    )
    parser.add_argument(
        "--base-file",
        default=str(DEFAULT_BASE_FILE),
        help=f"Path to base CV data (default: {DEFAULT_BASE_FILE})",
    )
    parser.add_argument(
        "--publications-file",
        default=str(DEFAULT_PUBLICATIONS_FILE),
        help=f"Path to publication data (default: {DEFAULT_PUBLICATIONS_FILE})",
    )
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_SYNCED_FILE),
        help=(
            "Path for synced publication output "
            f"(default: {DEFAULT_PUBLICATIONS_FILE}). "
            "Use --publications-file or --cv-file value to overwrite canonical input."
        ),
    )
    parser.add_argument(
        "--source-mode",
        choices=["hal_only", "orcid_only", "hal_plus_orcid"],
        help="Override publication_sync.source_mode",
    )
    parser.add_argument("--hal-id", help="Explicit HAL author identifier")
    parser.add_argument("--orcid", help="Explicit ORCID identifier")
    parser.add_argument(
        "--report-file",
        help="Optional markdown report path (written only in apply mode)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="Preview without changing files")
    mode_group.add_argument("--apply", action="store_true", help="Write merged output to --output-file")
    return parser.parse_args(argv)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_doi(value: Any) -> str:
    doi = normalize_text(value).lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    return doi.strip()


def normalize_year(value: Any) -> Any:
    if value in (None, ""):
        return ""
    text = normalize_text(value)
    if re.fullmatch(r"\d{4}", text):
        return int(text)
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else text


def title_year_fingerprint(title: Any, year: Any) -> str:
    title_text = re.sub(r"[^a-z0-9]+", "", normalize_text(title).lower())
    year_text = str(normalize_year(year) or "")
    return f"{title_text}:{year_text}" if title_text else ""


def title_only_fingerprint(title: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(title).lower())


def record_keys(record: dict[str, Any]) -> list[str]:
    keys = []
    doi = normalize_doi(record.get("doi"))
    hal_id = normalize_text(record.get("source_ids", {}).get("hal"))
    fingerprint = title_year_fingerprint(record.get("title"), record.get("year"))
    if doi:
        keys.append(f"doi:{doi}")
    if hal_id:
        keys.append(f"hal:{hal_id}")
    if fingerprint:
        keys.append(f"fingerprint:{fingerprint}")
    return keys


def record_sort_key(record: dict[str, Any]) -> tuple[Any, str, str]:
    year = normalize_year(record.get("year"))
    year_key = year if isinstance(year, int) else -1
    return (-year_key, normalize_text(record.get("title")).lower(), normalize_doi(record.get("doi")))


def default_source_mode(personal: dict[str, Any], publication_sync: dict[str, Any]) -> str:
    configured = normalize_text(publication_sync.get("source_mode"))
    if configured:
        return configured
    has_hal = bool(normalize_text(personal.get("id_hal")))
    has_orcid = bool(normalize_text(personal.get("orcid")))
    if has_hal and has_orcid:
        return "hal_plus_orcid"
    if has_hal:
        return "hal_only"
    if has_orcid:
        return "orcid_only"
    return "hal_plus_orcid"


def build_sync_config(args: argparse.Namespace, cv_data: dict[str, Any]) -> SyncConfig:
    personal = cv_data.get("personal", {}) or {}
    publication_sync = cv_data.get("publication_sync", {}) or {}
    source_mode = args.source_mode or default_source_mode(personal, publication_sync)
    hal_id = normalize_text(args.hal_id or personal.get("id_hal"))
    orcid = normalize_text(args.orcid or personal.get("orcid"))

    if source_mode in {"hal_only", "hal_plus_orcid"} and not hal_id:
        sys.exit("Error: HAL source mode requires --hal-id or personal.id_hal")
    if source_mode in {"orcid_only", "hal_plus_orcid"} and not orcid:
        sys.exit("Error: ORCID source mode requires --orcid or personal.orcid")

    return SyncConfig(
        cv_file=Path(args.cv_file) if args.cv_file else None,
        base_file=Path(args.base_file),
        publications_file=Path(args.publications_file),
        output_file=Path(args.output_file),
        source_mode=source_mode,
        hal_id=hal_id,
        orcid=orcid,
        apply_changes=bool(args.apply),
        report_file=Path(args.report_file) if args.report_file else None,
    )


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        sys.exit(f"Error: HTTP {exc.code} while fetching {url}")
    except URLError as exc:
        sys.exit(f"Error: Could not fetch {url}: {exc.reason}")


def map_hal_type(doc_type: str) -> tuple[str, str]:
    return HAL_TYPE_MAP.get(normalize_text(doc_type).upper(), ("journal_articles", "other"))


def map_orcid_type(work_type: str) -> tuple[str, str]:
    key = normalize_text(work_type).lower()
    return ORCID_TYPE_MAP.get(key, ("journal_articles", key or "other"))


def ensure_record_defaults(record: dict[str, Any], section: str) -> dict[str, Any]:
    normalized = copy.deepcopy(BASE_RECORD_DEFAULTS)
    normalized.update(record)
    normalized["authors"] = list(record.get("authors") or [])
    normalized["editors"] = list(record.get("editors") or [])
    normalized["source_ids"] = dict(record.get("source_ids") or {})
    normalized["section"] = section
    normalized["doi"] = normalize_doi(normalized.get("doi"))
    normalized["title"] = normalize_text(normalized.get("title"))
    normalized["journal"] = normalize_text(normalized.get("journal"))
    normalized["book"] = normalize_text(normalized.get("book"))
    normalized["publisher"] = normalize_text(normalized.get("publisher"))
    normalized["status"] = normalize_text(normalized.get("status"))
    normalized["url"] = normalize_text(normalized.get("url"))
    normalized["volume"] = normalize_text(normalized.get("volume"))
    normalized["pages"] = normalize_text(normalized.get("pages"))
    normalized["primary_source"] = normalize_text(normalized.get("primary_source"))
    normalized["publication_type"] = normalize_text(normalized.get("publication_type"))
    normalized["sync"] = normalize_text(normalized.get("sync") or "auto")
    normalized["year"] = normalize_year(normalized.get("year"))
    return normalized


def normalize_hal_record(doc: dict[str, Any]) -> dict[str, Any]:
    section, publication_type = map_hal_type(doc.get("docType_s"))
    title_candidates = doc.get("title_s") or []
    title = normalize_text(title_candidates[0] if isinstance(title_candidates, list) and title_candidates else title_candidates)
    url = normalize_text(doc.get("uri_s") or "")
    hal_id = normalize_text(doc.get("halId_s") or doc.get("docid") or "")
    year = doc.get("producedDateY_i") or doc.get("publicationDateY_i") or doc.get("year")
    record = {
        "authors": list(doc.get("authFullName_s") or []),
        "year": year,
        "title": title,
        "journal": normalize_text(doc.get("journalTitle_s") or doc.get("conferenceTitle_s") or ""),
        "book": normalize_text(doc.get("bookTitle_s") or ""),
        "publisher": normalize_text(doc.get("publisher_s") or ""),
        "doi": normalize_doi(doc.get("doiId_s") or ""),
        "url": url,
        "sync": "auto",
        "publication_type": publication_type,
        "primary_source": "hal",
        "source_ids": {"hal": hal_id},
    }
    return ensure_record_defaults(record, section)


def normalize_orcid_record(summary: dict[str, Any]) -> dict[str, Any]:
    section, publication_type = map_orcid_type(summary.get("type"))
    title = normalize_text(((summary.get("title") or {}).get("title") or {}).get("value"))
    journal = normalize_text(((summary.get("journal-title") or {}).get("value")) or "")
    publication_date = summary.get("publication-date") or {}
    year = (publication_date.get("year") or {}).get("value")
    external_ids = (summary.get("external-ids") or {}).get("external-id") or []
    doi = ""
    for external_id in external_ids:
        if normalize_text(external_id.get("external-id-type")).lower() == "doi":
            doi = normalize_doi(external_id.get("external-id-value"))
            break
    put_code = normalize_text(summary.get("put-code"))
    url = normalize_text(((summary.get("url") or {}).get("value")) or "")
    record = {
        "authors": [],
        "year": year,
        "title": title,
        "journal": journal,
        "doi": doi,
        "url": url,
        "sync": "auto",
        "publication_type": publication_type,
        "primary_source": "orcid",
        "source_ids": {"orcid_put_code": put_code},
    }
    return ensure_record_defaults(record, section)


def fetch_hal_publications(hal_id: str) -> list[dict[str, Any]]:
    query = quote_plus(f'(authIdHal_s:"{hal_id}" OR idHal_s:"{hal_id}")')
    fields = ",".join(
        [
            "title_s",
            "authFullName_s",
            "producedDateY_i",
            "publicationDateY_i",
            "journalTitle_s",
            "conferenceTitle_s",
            "bookTitle_s",
            "publisher_s",
            "doiId_s",
            "halId_s",
            "docid",
            "docType_s",
            "uri_s",
        ]
    )
    url = f"https://api.archives-ouvertes.fr/search/?q={query}&wt=json&rows=200&fl={fields}"
    payload = fetch_json(url)
    docs = ((payload.get("response") or {}).get("docs")) or []
    records = [normalize_hal_record(doc) for doc in docs]
    return sorted(records, key=record_sort_key)


def fetch_orcid_publications(orcid: str) -> list[dict[str, Any]]:
    url = f"https://pub.orcid.org/v3.0/{orcid}/works"
    payload = fetch_json(url, headers={"Accept": "application/json"})
    groups = payload.get("group") or []
    records = []
    for group in groups:
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        records.append(normalize_orcid_record(summaries[0]))
    return sorted(records, key=record_sort_key)


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if value == []:
        return True
    if value == {}:
        return True
    return False


def merge_upstream_records(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    if not base:
        return copy.deepcopy(incoming)

    merged = copy.deepcopy(base)
    incoming_is_hal = incoming.get("primary_source") == "hal"
    if incoming_is_hal:
        merged["section"] = incoming.get("section", merged.get("section"))
        merged["publication_type"] = incoming.get("publication_type", merged.get("publication_type"))
        merged["primary_source"] = "hal"

    for field in ["authors", "year", "title", "journal", "book", "editors", "publisher", "doi", "url", "volume", "pages", "status"]:
        if incoming_is_hal and not is_empty(incoming.get(field)):
            if field in {"title", "journal", "book", "publisher", "year", "authors"}:
                merged[field] = incoming[field]
                continue
        if is_empty(merged.get(field)) and not is_empty(incoming.get(field)):
            merged[field] = incoming[field]

    merged["source_ids"] = {**dict(base.get("source_ids") or {}), **dict(incoming.get("source_ids") or {})}
    if not merged.get("primary_source"):
        merged["primary_source"] = incoming.get("primary_source", "")
    return ensure_record_defaults(merged, merged.get("section") or incoming.get("section") or "journal_articles")


def merge_external_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_records: list[dict[str, Any]] = []
    key_to_index: dict[str, int] = {}
    for record in sorted(records, key=record_sort_key):
        match_index = None
        for key in record_keys(record):
            if key in key_to_index:
                match_index = key_to_index[key]
                break
        if match_index is None:
            match_index = len(merged_records)
            merged_records.append(copy.deepcopy(record))
        else:
            merged_records[match_index] = merge_upstream_records(merged_records[match_index], record)
        for key in record_keys(merged_records[match_index]):
            key_to_index[key] = match_index
    return sorted(merged_records, key=record_sort_key)


def validate_publication_sections(cv_data: dict[str, Any]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    publications = cv_data.get("publications")
    if publications is None:
        publications = {}
        cv_data["publications"] = publications
    elif not isinstance(publications, dict):
        warnings.append(
            {
                "path": "publications",
                "found": type(publications).__name__,
                "message": "expected mapping; treated as empty mapping",
            }
        )
        publications = {}
        cv_data["publications"] = publications
    for section in SECTION_FIELDS:
        value = publications.get(section)
        if section in publications and value is None:
            warnings.append(
                {
                    "path": f"publications.{section}",
                    "found": "null",
                    "message": "expected list; treated as empty list",
                }
            )
            publications[section] = []
        elif section in publications and not isinstance(value, list):
            warnings.append(
                {
                    "path": f"publications.{section}",
                    "found": type(value).__name__,
                    "message": "expected list; treated as empty list",
                }
            )
            publications[section] = []
    return warnings


def iter_existing_publications(
    cv_data: dict[str, Any],
    data_warnings: list[dict[str, str]] | None = None,
) -> list[tuple[str, int, dict[str, Any]]]:
    publications = cv_data.setdefault("publications", {})
    result = []
    for section in SECTION_FIELDS:
        publications.setdefault(section, [])
        section_records = publications.get(section) or []
        if not isinstance(section_records, list):
            if data_warnings is not None:
                data_warnings.append(
                    {
                        "path": f"publications.{section}",
                        "found": type(section_records).__name__,
                        "message": "expected list; treated as empty list",
                    }
                )
            section_records = []
        for index, record in enumerate(section_records):
            result.append((section, index, ensure_record_defaults(record, section)))
    return result


def manual_override_keys(cv_data: dict[str, Any]) -> set[str]:
    overrides = ((cv_data.get("publication_sync") or {}).get("manual_overrides")) or []
    keys = set()
    for item in overrides:
        if not isinstance(item, dict):
            continue
        doi = normalize_doi(item.get("doi"))
        title = title_year_fingerprint(item.get("title"), item.get("year") or "")
        title_only = title_only_fingerprint(item.get("title"))
        if doi:
            keys.add(f"doi:{doi}")
        if title:
            keys.add(f"fingerprint:{title}")
        if title_only:
            keys.add(f"title:{title_only}")
    return keys


def is_protected_record(record: dict[str, Any], override_keys: set[str]) -> bool:
    if normalize_text(record.get("sync")).lower() == "manual":
        return True
    title_only = title_only_fingerprint(record.get("title"))
    keys = set(record_keys(record))
    if title_only:
        keys.add(f"title:{title_only}")
    return any(key in override_keys for key in keys)


def apply_local_precedence(
    existing: dict[str, Any],
    upstream: dict[str, Any],
    synced_on: str,
) -> tuple[dict[str, Any], list[str]]:
    merged = ensure_record_defaults(copy.deepcopy(existing), existing.get("section", upstream["section"]))
    conflicts = []

    if upstream.get("primary_source") == "hal":
        merged["section"] = upstream["section"]
        merged["publication_type"] = upstream.get("publication_type", merged.get("publication_type"))
        merged["primary_source"] = "hal"
    elif not merged.get("publication_type"):
        merged["publication_type"] = upstream.get("publication_type", "")
        merged["primary_source"] = upstream.get("primary_source", "")

    for field in BASE_RECORD_DEFAULTS:
        if field in {"primary_source", "publication_type", "last_synced", "source_ids", "sync"}:
            continue
        local_value = merged.get(field)
        upstream_value = upstream.get(field)
        if is_empty(local_value) and not is_empty(upstream_value):
            merged[field] = copy.deepcopy(upstream_value)
        elif not is_empty(local_value) and not is_empty(upstream_value) and local_value != upstream_value:
            conflicts.append(field)

    merged["source_ids"] = {**dict(existing.get("source_ids") or {}), **dict(upstream.get("source_ids") or {})}
    merged["sync"] = normalize_text(existing.get("sync") or "auto")
    merged["last_synced"] = synced_on
    return ensure_record_defaults(merged, merged["section"]), sorted(set(conflicts))


def insert_or_replace_record(
    publications: dict[str, Any],
    existing_location: tuple[str, int] | None,
    record: dict[str, Any],
) -> None:
    target_section = record["section"]
    publications.setdefault(target_section, [])
    if existing_location is None:
        publications[target_section].append(prune_record_for_section(record))
        return

    current_section, index = existing_location
    if current_section == target_section:
        publications[target_section][index] = prune_record_for_section(record)
        return

    publications[current_section].pop(index)
    publications[target_section].append(prune_record_for_section(record))


def prune_record_for_section(record: dict[str, Any]) -> dict[str, Any]:
    allowed_fields = set(SECTION_FIELDS[record["section"]]) | {
        "sync",
        "publication_type",
        "primary_source",
        "source_ids",
        "last_synced",
    }
    pruned = {}
    for field in BASE_RECORD_DEFAULTS:
        if field in allowed_fields and not (field == "source_ids" and not record.get(field)):
            value = copy.deepcopy(record.get(field))
            if field == "authors":
                value = list(value or [])
            if field == "editors":
                value = list(value or [])
            pruned[field] = value
    if "source_ids" in allowed_fields and record.get("source_ids"):
        pruned["source_ids"] = dict(record["source_ids"])
    return pruned


PREPRINT_SOURCE_TYPES = {"preprint", "other", "report", "working-paper"}


def classify_and_dedup_preprints(
    publications: dict[str, Any],
) -> list[dict[str, Any]]:
    """Detect duplicate preprint/published pairs and reclassify preprints.

    Policy:
    - If a record in journal_articles has publication_type in PREPRINT_SOURCE_TYPES
      and another record in journal_articles (or under_review_or_in_prep) has the
      same normalized title with publication_type 'journal-article', the first is
      a preprint duplicate.
    - The preprint record is reclassified as 'preprint', moved to
      under_review_or_in_prep, and tagged with 'superseded_by' the DOI/title of
      the published version.
    - Returns a list of dedup actions for the sync report.
    """
    dedup_actions: list[dict[str, Any]] = []
    journal_articles = publications.get("journal_articles") or []
    under_review = publications.get("under_review_or_in_prep") or []

    # Build a lookup of published journal articles by normalized title.
    published_titles: dict[str, dict[str, Any]] = {}
    for rec in journal_articles:
        if normalize_text(rec.get("publication_type")) == "journal-article":
            key = title_only_fingerprint(rec.get("title"))
            if key:
                published_titles[key] = rec

    # Find preprint-type records in journal_articles that match a published title.
    kept: list[dict[str, Any]] = []
    for rec in journal_articles:
        pub_type = normalize_text(rec.get("publication_type"))
        if pub_type in PREPRINT_SOURCE_TYPES:
            key = title_only_fingerprint(rec.get("title"))
            if key and key in published_titles:
                # Reclassify as preprint and move to under_review_or_in_prep.
                preprint_rec = copy.deepcopy(rec)
                preprint_rec["publication_type"] = "preprint"
                preprint_rec["section"] = "under_review_or_in_prep"
                published = published_titles[key]
                preprint_rec["status"] = (
                    f"superseded by published version"
                    + (f" (doi:{published['doi']})" if published.get("doi") else "")
                )
                under_review.append(prune_record_for_section(preprint_rec))
                dedup_actions.append(
                    {
                        "title": normalize_text(rec.get("title")),
                        "action": "reclassified as preprint and moved to under_review_or_in_prep",
                        "superseded_by_doi": normalize_text(published.get("doi")),
                    }
                )
                continue
        kept.append(rec)

    publications["journal_articles"] = kept
    publications["under_review_or_in_prep"] = under_review
    return dedup_actions


def sync_publications(
    cv_data: dict[str, Any],
    hal_records: list[dict[str, Any]] | None = None,
    orcid_records: list[dict[str, Any]] | None = None,
    synced_on: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    synced_on = synced_on or date.today().isoformat()
    data_warnings = validate_publication_sections(cv_data)
    publications = cv_data.setdefault("publications", {})
    for section in SECTION_FIELDS:
        publications.setdefault(section, [])

    upstream_records = merge_external_records((hal_records or []) + (orcid_records or []))
    override_keys = manual_override_keys(cv_data)
    existing_records = iter_existing_publications(cv_data, data_warnings=data_warnings)

    keyed_existing: dict[str, tuple[str, int, dict[str, Any]]] = {}
    for section, index, record in existing_records:
        for key in record_keys(record):
            keyed_existing.setdefault(key, (section, index, record))

    report = {"added": [], "updated": [], "skipped": [], "conflicts": [], "data_warnings": data_warnings}

    for upstream in upstream_records:
        keyed_existing: dict[str, tuple[str, int, dict[str, Any]]] = {}
        for section, index, record in iter_existing_publications(cv_data):
            for key in record_keys(record):
                keyed_existing.setdefault(key, (section, index, record))

        matching = None
        for key in record_keys(upstream):
            if key in keyed_existing:
                matching = keyed_existing[key]
                break

        upstream_override_keys = set(record_keys(upstream))
        title_only = title_only_fingerprint(upstream.get("title"))
        if title_only:
            upstream_override_keys.add(f"title:{title_only}")

        if matching is None and any(key in override_keys for key in upstream_override_keys):
            report["skipped"].append({"title": upstream["title"], "reason": "manual override list"})
            continue

        if matching is None:
            insert_or_replace_record(publications, None, ensure_record_defaults(upstream, upstream["section"]))
            report["added"].append({"title": upstream["title"], "section": upstream["section"]})
            continue

        current_section, current_index, existing = matching
        if is_protected_record(existing, override_keys):
            report["skipped"].append({"title": existing["title"] or upstream["title"], "reason": "manual record"})
            continue

        merged_record, conflicts = apply_local_precedence(existing, upstream, synced_on)
        insert_or_replace_record(publications, (current_section, current_index), merged_record)
        report["updated"].append({"title": merged_record["title"], "section": merged_record["section"]})
        if conflicts:
            report["conflicts"].append({"title": merged_record["title"], "fields": conflicts})

    # Detect and reclassify preprint duplicates of published journal articles.
    dedup_actions = classify_and_dedup_preprints(publications)
    report["deduped_preprints"] = dedup_actions

    normalized_payload = assign_publication_indices(
        publication_payload_from_cv(cv_data),
        reverse_numbering=bool((cv_data.get("cv") or {}).get("pub_reverse_numbering", False)),
    )
    cv_data["publications"] = normalized_payload["publications"]
    cv_data["conference_presentations"] = normalized_payload["conference_presentations"]

    return cv_data, report


def render_report(report: dict[str, Any], config: SyncConfig) -> str:
    deduped = report.get("deduped_preprints") or []
    lines = [
        "# Publication sync report",
        "",
        f"- Mode: `{config.source_mode}`",
        f"- Apply changes: `{str(config.apply_changes).lower()}`",
        f"- Output file: `{config.output_file}`",
        f"- HAL id: `{config.hal_id or 'n/a'}`",
        f"- ORCID: `{config.orcid or 'n/a'}`",
        f"- Added: `{len(report['added'])}`",
        f"- Updated: `{len(report['updated'])}`",
        f"- Skipped: `{len(report['skipped'])}`",
        f"- Conflicts kept local: `{len(report['conflicts'])}`",
        f"- Preprints reclassified: `{len(deduped)}`",
        "",
    ]

    lines.append("## Data warnings")
    if not report.get("data_warnings"):
        lines.extend(["- None", ""])
    else:
        for warning in report["data_warnings"]:
            lines.append(f"- {warning['path']}: found `{warning['found']}`; {warning['message']}")
        lines.append("")

    for heading, items in [
        ("Added", report["added"]),
        ("Updated", report["updated"]),
        ("Skipped", report["skipped"]),
        ("Conflicts", report["conflicts"]),
    ]:
        lines.append(f"## {heading}")
        if not items:
            lines.extend(["- None", ""])
            continue
        for item in items:
            title = normalize_text(item.get("title")) or "(untitled)"
            details = []
            if item.get("section"):
                details.append(item["section"])
            if item.get("reason"):
                details.append(item["reason"])
            if item.get("fields"):
                details.append("fields: " + ", ".join(item["fields"]))
            suffix = f" ({'; '.join(details)})" if details else ""
            lines.append(f"- {title}{suffix}")
        lines.append("")

    lines.append("## Deduped preprints")
    if not deduped:
        lines.extend(["- None", ""])
    else:
        lines.append(
            "These records were reclassified as preprints and moved to "
            "under_review_or_in_prep because a published journal article "
            "with the same title was found."
        )
        lines.append("")
        for item in deduped:
            title = normalize_text(item.get("title")) or "(untitled)"
            doi_info = f" superseded by doi:{item['superseded_by_doi']}" if item.get("superseded_by_doi") else ""
            lines.append(f"- {title}{doi_info}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def gather_upstream_records(config: SyncConfig) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hal_records: list[dict[str, Any]] = []
    orcid_records: list[dict[str, Any]] = []
    if config.source_mode in {"hal_only", "hal_plus_orcid"}:
        hal_records = fetch_hal_publications(config.hal_id)
    if config.source_mode in {"orcid_only", "hal_plus_orcid"}:
        orcid_records = fetch_orcid_publications(config.orcid)
    return hal_records, orcid_records


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.cv_file:
        cv_data = load_yaml(Path(args.cv_file))
    else:
        cv_data = load_cv_data(
            base_file=Path(args.base_file),
            publications_file=Path(args.publications_file),
        )
        cv_data["conference_presentations"] = [
            normalize_publication_like_entry(record, "conference_presentations")
            for record in (cv_data.get("conference_presentations") or [])
        ]
    config = build_sync_config(args, cv_data)
    hal_records, orcid_records = gather_upstream_records(config)
    updated_data, report = sync_publications(
        copy.deepcopy(cv_data),
        hal_records=hal_records,
        orcid_records=orcid_records,
    )
    report_text = render_report(report, config)

    if config.apply_changes:
        synced_header = (
            "# ==============================================================================\n"
            "# cv.synced.yaml — Generated by sync_publications_hal.py\n"
            "#\n"
            "# This file is GENERATED. Do not edit it manually.\n"
            "# Edit your canonical publication data instead, then re-run sync.\n"
            "# ==============================================================================\n"
        )
        publication_output = publication_payload_from_cv(updated_data)
        split_canonical = config.output_file.resolve() == config.publications_file.resolve()
        legacy_canonical = config.cv_file is not None and config.output_file.resolve() == config.cv_file.resolve()
        is_canonical = split_canonical or legacy_canonical
        header = None if is_canonical else synced_header
        save_yaml(
            config.output_file,
            updated_data if legacy_canonical else publication_output,
            header=header,
        )
        if config.report_file:
            config.report_file.parent.mkdir(parents=True, exist_ok=True)
            config.report_file.write_text(report_text, encoding="utf-8")
    elif config.report_file:
        print(f"Note: dry-run mode does not write report files ({config.report_file}).", file=sys.stderr)

    print(report_text)
    if not config.apply_changes:
        print("Dry run completed: no files were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
