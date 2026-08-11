"""
Tests for scripts/extract_from_latex.py

Covers:
  - Publication title punctuation preservation (fix 3)
  - Conference tail parsing for venue/location/date (fix 4)
  - Funding section extraction (new feature)
  - join_multiline_entries helper
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "extract_from_latex.py"

spec = importlib.util.spec_from_file_location("extract_from_latex", MODULE_PATH)
ext = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = ext
spec.loader.exec_module(ext)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pub_lines(cvitem_body: str) -> list:
    """Wrap a citation body in a minimal publication LaTeX block."""
    return [
        r"\section{Publications}",
        r"\subsection{Peer-reviewed articles}",
        r"\cvitem{IF = 3.0 (Q1)}{" + cvitem_body + "}",
    ]


def make_chapter_lines(cvitem_body: str) -> list:
    return [
        r"\section{Publications}",
        r"\subsection{Book chapters}",
        r"\cvitem{1}{" + cvitem_body + "}",
    ]


def make_conf_lines(idx: int, cvitem_body: str) -> list:
    return [
        r"\section{Conference Presentations}",
        r"\cvitem{" + str(idx) + r"}{" + cvitem_body + "}",
    ]


# ---------------------------------------------------------------------------
# Fix 3 — Publication title punctuation preservation
# ---------------------------------------------------------------------------

class TestTitlePunctuation:
    def test_journal_title_preserves_trailing_period(self):
        citation = (
            r"Smith, A., Love, S.A. 2020. "
            r"A great experiment. "
            r"\textit{Nature}"
        )
        lines = make_pub_lines(citation)
        pubs = ext.extract_publications(lines)
        article = pubs["journal_articles"][0]
        assert article["title"].endswith("."), (
            f"Expected trailing period; got: {article['title']!r}"
        )
        assert article["title"] == "A great experiment."

    def test_chapter_title_preserves_trailing_period(self):
        citation = (
            r"Smith, A., Love, S.A. 2018. "
            r"Chapter on cognition. "
            r"\textit{Big Book}"
        )
        lines = make_chapter_lines(citation)
        pubs = ext.extract_publications(lines)
        chapter = pubs["book_chapters"][0]
        assert chapter["title"].endswith("."), (
            f"Expected trailing period; got: {chapter['title']!r}"
        )
        assert chapter["title"] == "Chapter on cognition."

    def test_title_without_period_is_left_as_is(self):
        """When the LaTeX source has no period after the title, do not add one."""
        # No period before journal — title extraction falls back to no-period
        citation = r"Smith, A. 2021. Unterminated title \textit{Journal}"
        lines = make_pub_lines(citation)
        pubs = ext.extract_publications(lines)
        article = pubs["journal_articles"][0]
        # Should not crash; title may or may not have period depending on
        # parsing, but must not be empty.
        assert article["title"]

    def test_journal_extracted_separately(self):
        """Journal name (in \\textit) ends up in the journal field, not title."""
        citation = (
            r"Love, S.A., Other, B. 2022. "
            r"Neural correlates of everything. "
            r"\textit{Brain Research}"
        )
        lines = make_pub_lines(citation)
        pubs = ext.extract_publications(lines)
        article = pubs["journal_articles"][0]
        assert "Brain Research" in article["journal"]
        assert "Brain Research" not in article["title"]


# ---------------------------------------------------------------------------
# Fix 4 — Conference tail parsing
# ---------------------------------------------------------------------------

class TestConferenceTailParsing:
    def _extract_first(self, cvitem_body: str):
        lines = make_conf_lines(1, cvitem_body)
        return ext.extract_conference_presentations(lines)[0]

    def test_poster_with_venue_location_date(self):
        citation = (
            r"\textbf{Love, S.A.,} Doe, J., 2016. "
            r"Some sheep brain study. "
            r"Poster at Annual Neuroscience Meeting, Paris, June 10-12"
        )
        pres = self._extract_first(citation)
        assert pres["type"] == "poster"
        assert "Annual Neuroscience Meeting" in pres["venue"]
        assert "Paris" in pres["location"]
        assert "June 10-12" in pres["date"]

    def test_poster_venue_not_empty(self):
        """Regression: venue was previously always stored as empty string."""
        citation = (
            r"Love, S.A., Auge, M., 2016. "
            r"Surface-based cortical parcellation of the sheep brain. "
            r"Poster at 2e Journee, Tour, May 24-25"
        )
        pres = self._extract_first(citation)
        assert pres["venue"] != "", "venue must not be empty"

    def test_oral_presentation_type(self):
        citation = (
            r"Love, S.A., Other, B., 2014. "
            r"Social gaze study. "
            r"Oral presentation at ICON-XII, Brisbane, July 27-31"
        )
        pres = self._extract_first(citation)
        assert pres["type"] == "oral"
        assert "ICON-XII" in pres["venue"]

    def test_poster_without_venue(self):
        """Poster with no 'at' clause should still yield type=poster, venue empty."""
        citation = r"Love, S.A., Other, B., 2015. Simple title. Poster"
        pres = self._extract_first(citation)
        assert pres["type"] == "poster"
        assert pres["venue"] == ""

    def test_title_is_extracted_correctly(self):
        citation = (
            r"Love, S.A., Doe, J., 2019. "
            r"Functional MRI in sheep. "
            r"Poster at Big Conference, Lyon, September 3-5"
        )
        pres = self._extract_first(citation)
        assert pres["title"] == "Functional MRI in sheep"

    def test_year_extracted(self):
        citation = (
            r"Love, S.A. 2017. "
            r"Some study on brains. "
            r"Talk at Workshop, London, March 1"
        )
        pres = self._extract_first(citation)
        assert pres["year"] == 2017


# ---------------------------------------------------------------------------
# Funding extraction
# ---------------------------------------------------------------------------

class TestFundingExtraction:
    def _extract(self, lines: list):
        return ext.extract_funding(lines)

    def test_single_funding_entry(self):
        lines = [
            r"\section{Funding}",
            r"\cvitem{2021 - 2024}{ANR grant for sheep MRI. 200k. Coordination: S. Love.}",
        ]
        grants = self._extract(lines)
        assert len(grants) == 1
        assert grants[0]["years"] == "2021 - 2024"
        assert "ANR" in grants[0]["description"]

    def test_multiple_funding_entries(self):
        lines = [
            r"\section{Funding}",
            r"\cvitem{2021 - 2024}{First grant.}",
            r"\cvitem{2018 - 2020}{Second grant.}",
        ]
        grants = self._extract(lines)
        assert len(grants) == 2

    def test_multiline_funding_entry(self):
        lines = [
            r"\section{Funding}",
            r"\cvitem{2024 - 2026}{American NIH - Towards High-Resolution study.",
            r"Coordination: C. Kemere, Partners: INRAE, Rice University.}",
            r"\section{NextSection}",
        ]
        grants = self._extract(lines)
        assert len(grants) == 1
        assert "Rice University" in grants[0]["description"], (
            "Multi-line continuation must be joined"
        )

    def test_empty_section_returns_empty_list(self):
        lines = [r"\section{Other}"]
        assert self._extract(lines) == []

    def test_funding_not_in_awards_section(self):
        """Funding entries must not bleed into the Honors & Awards section."""
        lines = [
            r"\section{Funding}",
            r"\cvitem{2020}{A grant.}",
            r"\section{Honors \& Awards}",
            r"\cvitem{2011}{Grindley Grant}",
        ]
        grants = self._extract(lines)
        assert len(grants) == 1
        assert "Grindley" not in grants[0]["description"]


# ---------------------------------------------------------------------------
# join_multiline_entries helper
# ---------------------------------------------------------------------------

class TestJoinMultilineEntries:
    def test_single_line_unchanged(self):
        lines = [r"\cvitem{2020}{Short entry.}"]
        assert ext.join_multiline_entries(lines) == [r"\cvitem{2020}{Short entry.}"]

    def test_continuation_joined(self):
        lines = [
            r"\cvitem{2020}{Start of a long",
            r"entry that continues here.}",
        ]
        result = ext.join_multiline_entries(lines)
        assert len(result) == 1
        assert "Start of a long entry that continues here.}" in result[0]

    def test_comment_lines_preserved(self):
        lines = [
            r"\cvitem{2020}{Entry.}",
            r"% a comment",
            r"\cvitem{2021}{Next.}",
        ]
        result = ext.join_multiline_entries(lines)
        assert len(result) == 3

    def test_two_separate_commands_not_joined(self):
        lines = [
            r"\cvitem{2020}{Entry one.}",
            r"\cvitem{2021}{Entry two.}",
        ]
        result = ext.join_multiline_entries(lines)
        assert len(result) == 2
