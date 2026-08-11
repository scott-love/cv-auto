import importlib.util
import sys
import tempfile
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CV_DATA_MODULE_PATH = REPO_ROOT / "scripts" / "cv_data.py"
GENERATE_MODULE_PATH = REPO_ROOT / "scripts" / "generate_latex.py"
EXTRACT_MODULE_PATH = REPO_ROOT / "scripts" / "extract_from_latex.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cv_data = load_module("cv_data", CV_DATA_MODULE_PATH)
generate_latex = load_module("generate_latex", GENERATE_MODULE_PATH)
extract_from_latex = load_module("extract_from_latex_for_generation_tests", EXTRACT_MODULE_PATH)


def test_extract_conference_presentations_include_sync():
    lines = [
        r"\section{Conference Presentations}",
        r"\cvitem{7}{Love, S.A., Doe, J. 2024. A conference title. Poster at Big Meeting, Paris, June 10-12}",
    ]
    presentation = extract_from_latex.extract_conference_presentations(lines)[0]
    assert presentation["sync"] == "auto"
    assert presentation["index"] == 7


def test_assign_publication_indices_is_chronological_for_all_sections():
    indexed = cv_data.assign_publication_indices(
        {
            "publications": {
                "journal_articles": [
                    {"title": "Older article", "year": 2022, "sync": "manual"},
                    {"title": "Newer article", "year": 2024},
                ],
                "book_chapters": [
                    {"title": "Chapter B", "year": 2021},
                    {"title": "Chapter A", "year": 2023},
                ],
                "under_review_or_in_prep": [
                    {"title": "Prep B", "year": 2024},
                    {"title": "Prep A", "year": 2025},
                ],
            },
            "conference_presentations": [
                {"title": "Conference B", "year": 2024, "date": "June 10-12"},
                {"title": "Conference A", "year": 2024, "date": "July 27-31", "sync": "manual"},
            ],
        }
    )

    assert [record["title"] for record in indexed["publications"]["journal_articles"]] == [
        "Newer article",
        "Older article",
    ]
    assert [record["index"] for record in indexed["publications"]["journal_articles"]] == [1, 2]
    assert [record["index"] for record in indexed["publications"]["book_chapters"]] == [1, 2]
    assert [record["index"] for record in indexed["publications"]["under_review_or_in_prep"]] == [1, 2]
    assert [record["title"] for record in indexed["conference_presentations"]] == [
        "Conference A",
        "Conference B",
    ]
    assert [record["index"] for record in indexed["conference_presentations"]] == [1, 2]
    assert indexed["conference_presentations"][0]["sync"] == "manual"


def test_generate_latex_merges_split_files_and_omits_skills_section():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        base_file = tmp_path / "cv.base.yaml"
        publications_file = tmp_path / "publications.yaml"
        output_file = tmp_path / "cv.tex"

        base_data = {
            "cv": {
                "theme": {"style": "casual", "color": "blue"},
                "section_order": ["languages", "publications", "conference_presentations"],
                "pub_reverse_numbering": False,
            },
            "personal": {
                "firstname": "Scott",
                "familyname": "Love",
                "title": "",
                "email": "",
                "mobile": "",
                "homepage": "",
                "orcid": "",
                "id_hal": "",
                "photo": "",
            },
            "languages": [{"language": "English", "proficiency": "Native", "scale": ""}],
            "skills": {"deprecated": {"label": "Should not render", "tools": ["X"]}},
        }
        publications_data = {
            "publications": {
                "journal_articles": [
                    {"title": "Recent paper", "year": 2024, "authors": ["Love, S.A."], "journal": "Journal"}
                ],
                "book_chapters": [],
                "under_review_or_in_prep": [],
            },
            "conference_presentations": [
                {
                    "title": "Talk title",
                    "year": 2024,
                    "authors": ["Love, S.A."],
                    "type": "oral",
                    "venue": "Conference",
                }
            ],
        }

        base_file.write_text(yaml.safe_dump(base_data, sort_keys=False), encoding="utf-8")
        publications_file.write_text(yaml.safe_dump(publications_data, sort_keys=False), encoding="utf-8")

        exit_code = generate_latex.main(
            [
                "--base-file",
                str(base_file),
                "--publications-file",
                str(publications_file),
                "--output",
                str(output_file),
            ]
        )

        assert exit_code is None
        rendered = output_file.read_text(encoding="utf-8")
        assert r"\section{Skills}" not in rendered
        assert r"\section{Languages}" in rendered
        assert r"\section{Publications}" in rendered
        assert r"\cvitem{1}{" in rendered
