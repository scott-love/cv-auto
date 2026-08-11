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

spec = importlib.util.spec_from_file_location("sync_publications_hal", MODULE_PATH)
sync_publications_hal = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = sync_publications_hal
spec.loader.exec_module(sync_publications_hal)


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


if __name__ == "__main__":
    unittest.main()
