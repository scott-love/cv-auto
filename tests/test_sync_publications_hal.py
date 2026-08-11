import copy
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "sync_publications_hal.py"
EXTRACT_MODULE_PATH = REPO_ROOT / "scripts" / "extract_from_latex.py"

spec = importlib.util.spec_from_file_location("sync_publications_hal", MODULE_PATH)
sync_publications_hal = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = sync_publications_hal
spec.loader.exec_module(sync_publications_hal)

extract_spec = importlib.util.spec_from_file_location("extract_from_latex", EXTRACT_MODULE_PATH)
extract_from_latex = importlib.util.module_from_spec(extract_spec)
assert extract_spec.loader is not None
sys.modules[extract_spec.name] = extract_from_latex
extract_spec.loader.exec_module(extract_from_latex)


def normalized_record(section, **kwargs):
    return sync_publications_hal.ensure_record_defaults(kwargs, section)


class SyncPublicationsHalTests(unittest.TestCase):
    def sample_cv(self):
        return {
            "personal": {"id_hal": "scott-love", "orcid": "0000-0001-7416-9210"},
            "publication_sync": {
                "source_mode": "hal_plus_orcid",
                "sources": {"hal": True, "orcid": True},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [
                    {
                        "sync": "auto",
                        "authors": ["Local, A."],
                        "year": 2024,
                        "title": "Local curated title",
                        "journal": "",
                        "volume": "",
                        "pages": "",
                        "impact_factor": "",
                        "quartile": "",
                        "doi": "",
                        "url": "",
                        "source_ids": {"hal": "hal-123"},
                    },
                    {
                        "sync": "manual",
                        "authors": ["Local, A."],
                        "year": 2023,
                        "title": "Protected publication",
                        "journal": "Existing Journal",
                        "volume": "",
                        "pages": "",
                        "impact_factor": "",
                        "quartile": "",
                        "doi": "",
                        "url": "",
                        "source_ids": {"hal": "hal-999"},
                    },
                ],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }

    def test_sync_merges_hal_and_orcid_with_local_precedence(self):
        cv_data = self.sample_cv()
        hal_records = [
            normalized_record(
                "journal_articles",
                authors=["HAL, Author"],
                year=2024,
                title="HAL imported title",
                journal="HAL Journal",
                doi="10.1000/example",
                url="https://hal.example/hal-123",
                publication_type="journal-article",
                primary_source="hal",
                source_ids={"hal": "hal-123"},
            ),
            normalized_record(
                "journal_articles",
                authors=["HAL, Author"],
                year=2023,
                title="Protected publication",
                journal="Replacement Journal",
                publication_type="journal-article",
                primary_source="hal",
                source_ids={"hal": "hal-999"},
            ),
        ]
        orcid_records = [
            normalized_record(
                "journal_articles",
                authors=[],
                year=2024,
                title="ORCID imported title",
                journal="",
                doi="10.1000/example",
                url="https://orcid.example/work/123",
                publication_type="journal-article",
                primary_source="orcid",
                source_ids={"orcid_put_code": "123"},
            ),
            normalized_record(
                "journal_articles",
                authors=[],
                year=2022,
                title="ORCID only paper",
                journal="ORCID Journal",
                doi="10.1000/new",
                url="https://orcid.example/work/999",
                publication_type="journal-article",
                primary_source="orcid",
                source_ids={"orcid_put_code": "999"},
            ),
        ]

        updated, report = sync_publications_hal.sync_publications(
            copy.deepcopy(cv_data),
            hal_records=hal_records,
            orcid_records=orcid_records,
            synced_on="2026-08-11",
        )

        publications = updated["publications"]["journal_articles"]
        updated_existing = publications[0]
        protected = publications[1]
        added = publications[2]

        self.assertEqual(updated_existing["title"], "Local curated title")
        self.assertEqual(updated_existing["journal"], "HAL Journal")
        self.assertEqual(updated_existing["doi"], "10.1000/example")
        self.assertEqual(updated_existing["url"], "https://hal.example/hal-123")
        self.assertEqual(updated_existing["primary_source"], "hal")
        self.assertEqual(updated_existing["publication_type"], "journal-article")
        self.assertEqual(updated_existing["last_synced"], "2026-08-11")
        self.assertEqual(updated_existing["source_ids"]["orcid_put_code"], "123")

        self.assertEqual(protected["journal"], "Existing Journal")
        self.assertNotIn("last_synced", protected)

        self.assertEqual(added["title"], "ORCID only paper")
        self.assertEqual(added["primary_source"], "orcid")

        self.assertEqual(len(report["added"]), 1)
        self.assertEqual(len(report["updated"]), 1)
        self.assertEqual(len(report["skipped"]), 1)
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertEqual(report["conflicts"][0]["fields"], ["authors", "title"])

    def test_main_dry_run_uses_personal_hal_id_without_writing_file(self):
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": "0000-0001-7416-9210"},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }
        hal_fixture = [
            normalized_record(
                "journal_articles",
                authors=["HAL, Author"],
                year=2026,
                title="New HAL record",
                journal="HAL Journal",
                doi="10.1000/dry-run",
                url="https://hal.example/new",
                publication_type="journal-article",
                primary_source="hal",
                source_ids={"hal": "hal-555"},
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            cv_file = Path(tmp_dir) / "cv.yaml"
            cv_file.write_text(yaml.safe_dump(cv_data, sort_keys=False), encoding="utf-8")
            original = cv_file.read_text(encoding="utf-8")

            output = io.StringIO()
            with mock.patch.object(sync_publications_hal, "fetch_hal_publications", return_value=hal_fixture) as fetch_hal:
                with redirect_stdout(output):
                    exit_code = sync_publications_hal.main(
                        ["--cv-file", str(cv_file), "--dry-run", "--source-mode", "hal_only"]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(cv_file.read_text(encoding="utf-8"), original)
            fetch_hal.assert_called_once_with("scott-love")
            rendered = output.getvalue()
            self.assertIn("- Mode: `hal_only`", rendered)
            self.assertIn("- Added: `1`", rendered)
            self.assertIn("Dry run completed: no files were changed.", rendered)

    def test_main_dry_run_handles_malformed_publication_sections(self):
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": "0000-0001-7416-9210"},
            "publication_sync": {
                "source_mode": "hal_plus_orcid",
                "sources": {"hal": True, "orcid": True},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": None,
                "book_chapters": "invalid",
                "under_review_or_in_prep": [],
            },
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            cv_file = Path(tmp_dir) / "cv.yaml"
            cv_file.write_text(yaml.safe_dump(cv_data, sort_keys=False), encoding="utf-8")
            original = cv_file.read_text(encoding="utf-8")

            output = io.StringIO()
            with mock.patch.object(sync_publications_hal, "fetch_hal_publications", return_value=[]):
                with mock.patch.object(sync_publications_hal, "fetch_orcid_publications", return_value=[]):
                    with redirect_stdout(output):
                        exit_code = sync_publications_hal.main(
                            [
                                "--cv-file",
                                str(cv_file),
                                "--dry-run",
                                "--source-mode",
                                "hal_plus_orcid",
                            ]
                        )

            self.assertEqual(exit_code, 0)
            self.assertEqual(cv_file.read_text(encoding="utf-8"), original)
            rendered = output.getvalue()
            self.assertIn("## Data warnings", rendered)
            self.assertIn("- publications.journal_articles: found `null`; expected list; treated as empty list", rendered)
            self.assertIn("- publications.book_chapters: found `str`; expected list; treated as empty list", rendered)
            self.assertIn("Dry run completed: no files were changed.", rendered)


class HalBackfillTests(unittest.TestCase):
    """Tests for B: HAL backfill of missing local fields."""

    def test_hal_backfills_empty_volume_and_pages(self):
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": ""},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [
                    {
                        "sync": "auto",
                        "authors": ["Love, S."],
                        "year": 2022,
                        "title": "Test paper",
                        "journal": "Test Journal",
                        "volume": "",
                        "pages": "",
                        "doi": "10.1000/test",
                        "url": "",
                        "source_ids": {"hal": "hal-abc"},
                    }
                ],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }
        hal_record = normalized_record(
            "journal_articles",
            authors=["Love, Scott"],
            year=2022,
            title="Test paper",
            journal="Test Journal",
            volume="5",
            pages="100-110",
            doi="10.1000/test",
            publication_type="journal-article",
            primary_source="hal",
            source_ids={"hal": "hal-abc"},
        )
        updated, report = sync_publications_hal.sync_publications(
            copy.deepcopy(cv_data),
            hal_records=[hal_record],
            synced_on="2026-08-11",
        )
        article = updated["publications"]["journal_articles"][0]
        self.assertEqual(article["volume"], "5")
        self.assertEqual(article["pages"], "100-110")
        # Local journal should be preserved (not overwritten by HAL since HAL takes precedence for journal)
        self.assertEqual(article["journal"], "Test Journal")

    def test_hal_backfill_does_not_overwrite_existing_local_values(self):
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": ""},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [
                    {
                        "sync": "auto",
                        "authors": ["Love, S."],
                        "year": 2022,
                        "title": "Test paper",
                        "journal": "My Local Journal",
                        "volume": "3",
                        "pages": "50-60",
                        "doi": "10.1000/test",
                        "url": "",
                        "source_ids": {"hal": "hal-abc"},
                    }
                ],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }
        hal_record = normalized_record(
            "journal_articles",
            authors=["Love, Scott"],
            year=2022,
            title="Test paper",
            journal="HAL Journal Name",
            volume="99",
            pages="999-1000",
            doi="10.1000/test",
            publication_type="journal-article",
            primary_source="hal",
            source_ids={"hal": "hal-abc"},
        )
        updated, report = sync_publications_hal.sync_publications(
            copy.deepcopy(cv_data),
            hal_records=[hal_record],
            synced_on="2026-08-11",
        )
        article = updated["publications"]["journal_articles"][0]
        # volume and pages set locally should not be overwritten
        self.assertEqual(article["volume"], "3")
        self.assertEqual(article["pages"], "50-60")
        # conflicts should be reported for volume and pages
        conflict_titles = [c["title"] for c in report["conflicts"]]
        self.assertIn("Test paper", conflict_titles)


class HalClassificationTests(unittest.TestCase):
    def test_hal_article_stays_journal_article(self):
        record = sync_publications_hal.normalize_hal_record(
            {
                "docType_s": "ART",
                "title_s": ["Journal publication"],
                "journalTitle_s": "Journal of Testing",
                "halId_s": "hal-art-1",
            }
        )
        self.assertEqual(record["section"], "journal_articles")
        self.assertEqual(record["publication_type"], "journal-article")

    def test_hal_french_poster_is_not_journal_article(self):
        record = sync_publications_hal.normalize_hal_record(
            {
                "docType_s": "COMM",
                "subType_s": "Affiche",
                "title_s": ["Développer un protocole d'entraînement pour réaliser des IRMf sans anesthésie et sans contrainte avec des agneaux"],
                "conferenceTitle_s": "Congrès test",
                "halId_s": "hal-poster-1",
            }
        )
        self.assertEqual(record["section"], "under_review_or_in_prep")
        self.assertEqual(record["publication_type"], "conference-poster")

    def test_hal_unknown_type_falls_back_conservatively(self):
        record = sync_publications_hal.normalize_hal_record(
            {
                "docType_s": "UNDEFINED",
                "title_s": ["Unknown publication kind"],
                "halId_s": "hal-unknown-1",
            }
        )
        self.assertEqual(record["section"], "under_review_or_in_prep")
        self.assertEqual(record["publication_type"], "other")

    def test_hal_override_applies_after_auto_classification(self):
        cv_data = {
            "publication_sync": {"manual_overrides": []},
            "publications": {"journal_articles": [], "book_chapters": [], "under_review_or_in_prep": []},
        }
        hal_record = sync_publications_hal.normalize_hal_record(
            {
                "docType_s": "ART",
                "title_s": ["Auto classified as journal"],
                "journalTitle_s": "Journal of Testing",
                "halId_s": "hal-override-1",
            }
        )

        updated, report = sync_publications_hal.sync_publications(
            copy.deepcopy(cv_data),
            hal_records=[hal_record],
            publication_overrides={"hal:hal-override-1": "conference_posters"},
            synced_on="2026-08-11",
        )
        self.assertEqual(len(updated["publications"]["journal_articles"]), 0)
        self.assertEqual(len(updated["publications"]["under_review_or_in_prep"]), 1)
        overridden = updated["publications"]["under_review_or_in_prep"][0]
        self.assertEqual(overridden["publication_type"], "conference-poster")
        self.assertEqual(len(report["applied_overrides"]), 1)

    def test_unknown_override_category_is_warned_and_ignored(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            overrides_file = Path(tmp_dir) / "publications_overrides.yml"
            overrides_file.write_text(
                "hal:hal-override-1:\n"
                "  category: made_up_category\n",
                encoding="utf-8",
            )
            overrides, warnings = sync_publications_hal.load_publication_overrides(overrides_file)
        self.assertEqual(overrides, {})
        self.assertEqual(len(warnings), 1)
        self.assertIn("unknown override category", warnings[0]["message"])


class PreprintDedupTests(unittest.TestCase):
    """Tests for D: Preprint vs published dedup/classification."""

    def test_preprint_duplicate_reclassified_and_moved(self):
        """A preprint-type record with same title as journal article is reclassified."""
        publications = {
            "journal_articles": [
                {
                    "sync": "auto",
                    "authors": ["Love, S."],
                    "year": 2022,
                    "title": "Great neuroscience paper",
                    "journal": "Nature Neuroscience",
                    "volume": "5",
                    "pages": "100-110",
                    "doi": "10.1000/published",
                    "url": "",
                    "publication_type": "journal-article",
                    "primary_source": "hal",
                    "source_ids": {"hal": "hal-pub"},
                    "last_synced": "2026-08-11",
                },
                {
                    "sync": "auto",
                    "authors": ["Love, S."],
                    "year": 2022,
                    "title": "Great neuroscience paper",
                    "journal": "",
                    "volume": "",
                    "pages": "",
                    "doi": "",
                    "url": "https://zenodo.org/record/123",
                    "publication_type": "other",
                    "primary_source": "hal",
                    "source_ids": {"hal": "hal-preprint"},
                    "last_synced": "2026-08-11",
                },
            ],
            "book_chapters": [],
            "under_review_or_in_prep": [],
        }
        dedup_actions = sync_publications_hal.classify_and_dedup_preprints(publications)
        self.assertEqual(len(dedup_actions), 1)
        self.assertIn("Great neuroscience paper", dedup_actions[0]["title"])
        self.assertEqual(dedup_actions[0]["superseded_by_doi"], "10.1000/published")
        # Should have only 1 journal article left (the published one)
        self.assertEqual(len(publications["journal_articles"]), 1)
        self.assertEqual(publications["journal_articles"][0]["publication_type"], "journal-article")
        # Preprint should be moved to under_review_or_in_prep
        self.assertEqual(len(publications["under_review_or_in_prep"]), 1)
        preprint = publications["under_review_or_in_prep"][0]
        self.assertEqual(preprint["publication_type"], "preprint")
        self.assertIn("superseded", preprint["status"])

    def test_non_duplicate_records_not_affected(self):
        """Records with unique titles are not affected by dedup."""
        publications = {
            "journal_articles": [
                {
                    "sync": "auto",
                    "authors": ["Love, S."],
                    "year": 2022,
                    "title": "Unique paper A",
                    "journal": "Journal A",
                    "doi": "10.1000/a",
                    "publication_type": "journal-article",
                    "source_ids": {},
                },
                {
                    "sync": "auto",
                    "authors": ["Love, S."],
                    "year": 2021,
                    "title": "Unique paper B",
                    "journal": "Journal B",
                    "doi": "10.1000/b",
                    "publication_type": "journal-article",
                    "source_ids": {},
                },
            ],
            "book_chapters": [],
            "under_review_or_in_prep": [],
        }
        dedup_actions = sync_publications_hal.classify_and_dedup_preprints(publications)
        self.assertEqual(len(dedup_actions), 0)
        self.assertEqual(len(publications["journal_articles"]), 2)
        self.assertEqual(len(publications["under_review_or_in_prep"]), 0)


class SyncOutputFileTests(unittest.TestCase):
    """Tests for C: Sync output to new file, not overwriting canonical cv.yaml."""

    def test_apply_writes_to_output_file_not_cv_file(self):
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": ""},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }
        hal_fixture = [
            normalized_record(
                "journal_articles",
                authors=["Love, Scott"],
                year=2026,
                title="New HAL paper",
                journal="HAL Journal",
                doi="10.1000/hal-new",
                publication_type="journal-article",
                primary_source="hal",
                source_ids={"hal": "hal-new"},
            )
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            cv_file = Path(tmp_dir) / "cv.yaml"
            output_file = Path(tmp_dir) / "cv.synced.yaml"
            cv_file.write_text(yaml.safe_dump(cv_data, sort_keys=False), encoding="utf-8")
            original_cv = cv_file.read_text(encoding="utf-8")

            with mock.patch.object(sync_publications_hal, "fetch_hal_publications", return_value=hal_fixture):
                exit_code = sync_publications_hal.main(
                    [
                        "--cv-file", str(cv_file),
                        "--output-file", str(output_file),
                        "--apply",
                        "--source-mode", "hal_only",
                    ]
                )

            self.assertEqual(exit_code, 0)
            # Canonical cv.yaml must NOT be changed
            self.assertEqual(cv_file.read_text(encoding="utf-8"), original_cv)
            # Output file must exist and contain the new publication
            self.assertTrue(output_file.exists())
            synced_content = output_file.read_text(encoding="utf-8")
            self.assertIn("New HAL paper", synced_content)
            # Output file should have the generated header comment
            self.assertIn("# cv.synced.yaml", synced_content)

    def test_apply_to_canonical_has_no_generated_header(self):
        """When output-file equals cv-file, no generated header is written."""
        cv_data = {
            "personal": {"id_hal": "scott-love", "orcid": ""},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
            "publications": {
                "journal_articles": [],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            cv_file = Path(tmp_dir) / "cv.yaml"
            cv_file.write_text(yaml.safe_dump(cv_data, sort_keys=False), encoding="utf-8")

            with mock.patch.object(sync_publications_hal, "fetch_hal_publications", return_value=[]):
                exit_code = sync_publications_hal.main(
                    [
                        "--cv-file", str(cv_file),
                        "--output-file", str(cv_file),
                        "--apply",
                        "--source-mode", "hal_only",
                    ]
                )

            self.assertEqual(exit_code, 0)
            content = cv_file.read_text(encoding="utf-8")
            self.assertNotIn("# cv.synced.yaml", content)


class SplitFileSyncTests(unittest.TestCase):
    def test_apply_updates_publications_file_in_split_mode(self):
        base_data = {
            "cv": {"pub_reverse_numbering": False},
            "personal": {"id_hal": "scott-love", "orcid": ""},
            "publication_sync": {
                "source_mode": "hal_only",
                "sources": {"hal": True, "orcid": False},
                "manual_overrides": [],
            },
        }
        publications_data = {
            "publications": {
                "journal_articles": [],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
            "conference_presentations": [
                {
                    "sync": "manual",
                    "authors": ["Love, S."],
                    "year": 2024,
                    "title": "Existing talk",
                    "venue": "Conference",
                    "type": "oral",
                }
            ],
        }
        hal_fixture = [
            normalized_record(
                "journal_articles",
                authors=["Love, Scott"],
                year=2026,
                title="Split mode paper",
                journal="HAL Journal",
                doi="10.1000/split",
                publication_type="journal-article",
                primary_source="hal",
                source_ids={"hal": "hal-split"},
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_file = Path(tmp_dir) / "cv.base.yaml"
            publications_file = Path(tmp_dir) / "publications.yaml"
            base_file.write_text(yaml.safe_dump(base_data, sort_keys=False), encoding="utf-8")
            publications_file.write_text(yaml.safe_dump(publications_data, sort_keys=False), encoding="utf-8")

            with mock.patch.object(sync_publications_hal, "fetch_hal_publications", return_value=hal_fixture):
                exit_code = sync_publications_hal.main(
                    [
                        "--base-file",
                        str(base_file),
                        "--publications-file",
                        str(publications_file),
                        "--output-file",
                        str(publications_file),
                        "--apply",
                        "--source-mode",
                        "hal_only",
                    ]
                )

            self.assertEqual(exit_code, 0)
            updated = yaml.safe_load(publications_file.read_text(encoding="utf-8"))
            self.assertEqual(updated["publications"]["journal_articles"][0]["title"], "Split mode paper")
            self.assertEqual(updated["conference_presentations"][0]["sync"], "manual")
            self.assertIn("index", updated["conference_presentations"][0])


class HyphenatedAuthorParsingTests(unittest.TestCase):
    """Tests for A: Fix author parsing for hyphenated initials."""

    def test_hyphenated_initial_not_split(self):
        """'Blache, M-C.' should be one author, not two."""
        authors_str = "Love, S., Blache, M-C., Dupont, J-M."
        result = extract_from_latex.parse_authors_citation(authors_str)
        # Note: trailing period on the last author is stripped by the parser (existing behavior).
        self.assertEqual(result, ["Love, S.", "Blache, M-C.", "Dupont, J-M"])

    def test_standard_authors_still_split_correctly(self):
        """Standard author strings continue to split correctly."""
        authors_str = "Love, S., Smith, J., Jones, A."
        result = extract_from_latex.parse_authors_citation(authors_str)
        # Trailing period on last author is stripped (existing behavior).
        self.assertEqual(result, ["Love, S.", "Smith, J.", "Jones, A"])

    def test_single_author(self):
        authors_str = "Blache, M-C."
        result = extract_from_latex.parse_authors_citation(authors_str)
        self.assertEqual(result, ["Blache, M-C"])

    def test_mixed_normal_and_hyphenated(self):
        authors_str = "Martin, A., Blache, M-C., Bernard, F."
        result = extract_from_latex.parse_authors_citation(authors_str)
        # Trailing period on last author is stripped (existing behavior).
        self.assertEqual(result, ["Martin, A.", "Blache, M-C.", "Bernard, F"])


if __name__ == "__main__":
    unittest.main()