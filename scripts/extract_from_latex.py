#!/usr/bin/env python3
"""
extract_from_latex.py
=====================
Parses the existing LaTeX CV (source-material/cv_7.tex) and writes a
populated data/cv.yaml file.

Usage
-----
    python scripts/extract_from_latex.py [--input PATH] [--output PATH]

Defaults
--------
    --input   source-material/cv_7.tex
    --output  data/cv.yaml

The script can be safely re-run after editing the LaTeX source; it always
writes a fresh output file.

Design notes
------------
- Pure Python 3; no external dependencies.
- Regex-based parsing of moderncv LaTeX macros.
- LaTeX helper functions strip common commands (\\emph, \\textbf, \\textsc,
  \\LaTeX, \\textasciitilde, etc.) so extracted text is plain.
- Each extracted section is reported to stdout so the user can verify quality.
- Publications receive a  sync: auto  marker; book chapters and unpublished
  items receive  sync: manual.
"""

import argparse
import os
import re
import sys
from textwrap import indent

# ---------------------------------------------------------------------------
# Paths (relative to the repository root, which we auto-detect)
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_INPUT = os.path.join(REPO_ROOT, "source-material", "cv_7.tex")
DEFAULT_OUTPUT = os.path.join(REPO_ROOT, "data", "cv.yaml")


# ---------------------------------------------------------------------------
# LaTeX text helpers
# ---------------------------------------------------------------------------

def clean_latex(text: str, keep_textit_marker: bool = False) -> str:
    """Remove common LaTeX markup and return plain text.

    If keep_textit_marker is True, \\textit{...} and \\emph{...} are replaced
    with «...» so callers can detect the italic span boundary (useful for
    extracting publication journal names that appear in italic).
    """
    if not text:
        return ""
    # Remove comment lines
    text = re.sub(r"%.*", "", text)
    # \textbf{...} → contents
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    # \textit{...} or \emph{...} → use marker or strip
    if keep_textit_marker:
        text = re.sub(r"\\(?:textit|emph)\{([^}]*)\}", r"«\1»", text)
    else:
        text = re.sub(r"\\(?:textit|emph)\{([^}]*)\}", r"\1", text)
    # \textsc{...} → contents
    text = re.sub(r"\\textsc\{([^}]*)\}", r"\1", text)
    # \LaTeX → LaTeX
    text = text.replace(r"\LaTeX", "LaTeX")
    # \textasciitilde → ~
    text = text.replace(r"\textasciitilde", "~")
    # \& → &
    text = text.replace(r"\&", "&")
    # Remove remaining \command (without braces)
    text = re.sub(r"\\[a-zA-Z]+\b\*?", "", text)
    # Remove stray braces
    text = text.replace("{", "").replace("}", "")
    # Normalise whitespace
    text = " ".join(text.split())
    return text.strip()


def yaml_str(value: str, indent_level: int = 0) -> str:
    """Return a YAML-safe string scalar, quoting if necessary."""
    if not value:
        return '""'
    # Characters that require quoting
    if any(c in value for c in (':', '#', '[', ']', '{', '}', ',', '&', '*',
                                '?', '|', '-', '<', '>', '=', '!', '%', '@',
                                '`', "'", '"', '\n')):
        # Use double-quote style, escaping internal double quotes
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value


def yaml_block_str(value: str, base_indent: int = 2) -> str:
    """Format a potentially long string as a YAML block scalar (>-)."""
    if not value:
        return '""'
    if len(value) < 60 and '\n' not in value:
        return yaml_str(value)
    pad = " " * (base_indent + 2)
    wrapped = indent(value, pad)
    return f">-\n{wrapped}"


# ---------------------------------------------------------------------------
# Low-level LaTeX macro parsers
# ---------------------------------------------------------------------------

def parse_cventry(line: str):
    """
    Parse \\cventry{dates}{title}{institution}{location}{grade}{desc}.
    Returns a dict or None.
    """
    m = re.match(
        r"\\cventry\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}",
        line.strip(),
    )
    if not m:
        return None
    return {
        "dates": clean_latex(m.group(1)),
        "title": clean_latex(m.group(2)),
        "institution": clean_latex(m.group(3)),
        "location": clean_latex(m.group(4)),
        "grade": clean_latex(m.group(5)),
        "description": clean_latex(m.group(6)),
    }


def parse_cvitem(line: str):
    """
    Parse \\cvitem{label}{text}.
    Returns (label, text) or None.
    """
    m = re.match(r"\\cvitem\{([^}]*)\}\{(.*)\}", line.strip())
    if not m:
        return None
    return clean_latex(m.group(1)), clean_latex(m.group(2))


def parse_cvitemwithcomment(line: str):
    """
    Parse \\cvitemwithcomment{label}{text}{comment}.
    Returns (label, text, comment) or None.
    """
    m = re.match(
        r"\\cvitemwithcomment\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}", line.strip()
    )
    if not m:
        return None
    return (
        clean_latex(m.group(1)),
        clean_latex(m.group(2)),
        clean_latex(m.group(3)),
    )


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def split_dates(date_str: str):
    """
    Split a date range like '2007 -- 2011' or 'Nov. 2017 -- present'.
    Returns (start, end).
    """
    parts = re.split(r"\s*--\s*", date_str, maxsplit=1)
    start = parts[0].strip() if parts else date_str
    end = parts[1].strip() if len(parts) > 1 else start
    return start, end


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def extract_personal(lines: list) -> dict:
    """Extract personal/header information from preamble."""
    personal = {
        "firstname": "",
        "familyname": "",
        "title": "",
        "email": "",
        "orcid": "",
        "id_hal": "",
        "photo": "",
        "homepage": "",
        "mobile": "",
    }
    for line in lines:
        line = line.strip()
        m = re.match(r"\\firstname\{([^}]*)\}", line)
        if m:
            personal["firstname"] = clean_latex(m.group(1))
        m = re.match(r"\\familyname\{([^}]*)\}", line)
        if m:
            personal["familyname"] = clean_latex(m.group(1))
        m = re.match(r"\\title\{([^}]*)\}", line)
        if m:
            personal["title"] = clean_latex(m.group(1))
        m = re.match(r"\\email\{([^}]*)\}", line)
        if m:
            personal["email"] = m.group(1).strip()
        # ORCID / HAL may be in a commented \extrainfo line
        m = re.search(r"ORCID:\s*(?:orcid\.org/)?([\d-]+)", line)
        if m:
            personal["orcid"] = m.group(1).strip()
        m = re.search(r"HAL:\s*(?:hal\.science/)?([A-Za-z0-9-]+)", line)
        if m:
            personal["id_hal"] = m.group(1).strip()
        m = re.match(r"\\photo\[.*?\]\[.*?\]\{([^}]*)\}", line)
        if m:
            personal["photo"] = m.group(1).strip()
        m = re.match(r"\\mobile\{([^}]*)\}", line)
        if m:
            personal["mobile"] = m.group(1).strip()
        m = re.match(r"\\homepage\{([^}]*)\}", line)
        if m:
            personal["homepage"] = m.group(1).strip()
    return personal


def extract_section_lines(lines: list, section_name: str) -> list:
    """
    Return the raw lines belonging to a LaTeX \\section{section_name} block,
    stopping at the next \\section.
    Matching is case-insensitive and strips common LaTeX escapes.
    """
    in_section = False
    collected = []
    pattern = re.compile(
        r"\\section\{" + re.escape(section_name) + r"\}", re.IGNORECASE
    )
    next_section = re.compile(r"\\section\{", re.IGNORECASE)

    for line in lines:
        if pattern.search(line):
            in_section = True
            continue
        if in_section:
            if next_section.search(line) and not pattern.search(line):
                break
            collected.append(line)
    return collected


def extract_education(lines: list) -> list:
    """Parse the Education section."""
    edu_lines = extract_section_lines(lines, "Education")
    entries = []
    current = None
    pending_items = {}
    # Institution and country come from \subsection{Name, Country}
    institution_ctx = ""
    country_ctx = ""

    def flush():
        if current is not None:
            # Attach accumulated cvitem data
            entry = dict(current)
            entry["thesis_title"] = pending_items.get("Title", "")
            entry["supervisor"] = pending_items.get("Supervisor", "")
            entry["description"] = pending_items.get("Description", "")
            entries.append(entry)

    for line in edu_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        # \subsection sets institution context for subsequent \cventry items
        m = re.match(r"\\subsection\{([^}]*)\}", line_s)
        if m:
            sub_text = clean_latex(m.group(1))
            # Convention: "Institution Name, Country"
            if "," in sub_text:
                institution_ctx, country_ctx = (
                    p.strip() for p in sub_text.rsplit(",", 1)
                )
            else:
                institution_ctx = sub_text
                country_ctx = ""
            continue
        # New \cventry resets state
        cv = parse_cventry(line_s)
        if cv:
            flush()
            pending_items = {}
            start, end = split_dates(cv["dates"])
            current = {
                "degree": cv["title"],
                # Use subsection context if cventry fields are blank
                "institution": cv["institution"] or institution_ctx,
                "country": cv["location"] or country_ctx,
                "start": start,
                "end": end,
                "honours": cv["grade"] or cv["description"],
            }
            continue
        item = parse_cvitem(line_s)
        if item and current is not None:
            pending_items[item[0]] = item[1]

    flush()
    return entries


def extract_experience(lines: list) -> dict:
    """Parse the Professional Experience section, split by subsection."""
    exp_lines = extract_section_lines(lines, "Professional Experience")
    research = []
    teaching = []
    current_subsection = "research"
    current = None
    pending_items = {}

    def flush():
        if current is None:
            return
        entry = dict(current)
        entry["supervisor"] = pending_items.get("Supervisor", "")
        entry["team"] = pending_items.get("Team", "")
        entry["description"] = pending_items.get("Description", "")
        if current_subsection == "teaching":
            teaching.append(entry)
        else:
            research.append(entry)

    for line in exp_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        # Subsection boundary
        m = re.match(r"\\subsection\{([^}]*)\}", line_s)
        if m:
            flush()
            current = None
            pending_items = {}
            sub = clean_latex(m.group(1)).lower()
            current_subsection = "teaching" if "teach" in sub else "research"
            continue
        cv = parse_cventry(line_s)
        if cv:
            flush()
            pending_items = {}
            start, end = split_dates(cv["dates"])
            if current_subsection == "teaching":
                current = {
                    "course": cv["title"],
                    "institution": cv["institution"],
                    "country": cv["location"],
                    "start": start,
                    "end": end,
                    "notes": cv["grade"] or cv["description"],
                }
            else:
                current = {
                    "position": cv["title"],
                    "institution": cv["institution"],
                    "country": cv["location"],
                    "start": start,
                    "end": end,
                }
            continue
        item = parse_cvitem(line_s)
        if item and current is not None:
            pending_items[item[0]] = item[1]

    flush()
    return {"research": research, "teaching": teaching}


def extract_awards(lines: list) -> list:
    """Parse the Honors & Awards section."""
    award_lines = extract_section_lines(lines, r"Honors \& Awards")
    # Also try without backslash escape
    if not award_lines:
        award_lines = extract_section_lines(lines, "Honors & Awards")
    awards = []
    for line in award_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        item = parse_cvitem(line_s)
        if item:
            awards.append({"year": item[0], "award": item[1]})
    return awards


def extract_skills(lines: list) -> dict:
    """Parse the Skills section."""
    skill_lines = extract_section_lines(lines, "Skills")
    skills = {}
    label_map = {
        "f/mri": ("fmri", "f/MRI"),
        "eeg": ("eeg", "EEG"),
        "programming": ("programming", "Programming"),
        "software": ("software", "Software"),
    }
    for line in skill_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        item = parse_cvitem(line_s)
        if item:
            key_raw = item[0].lower()
            key, label = label_map.get(key_raw, (key_raw.replace("/", "_"), item[0]))
            tool_str = item[1]
            tools = [t.strip() for t in tool_str.split(",") if t.strip()]
            skills[key] = {"label": label, "tools": tools}
    return skills


def extract_languages(lines: list) -> list:
    """Parse the Languages section."""
    lang_lines = extract_section_lines(lines, "Languages")
    languages = []
    for line in lang_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        item = parse_cvitemwithcomment(line_s)
        if item:
            languages.append({
                "language": item[0],
                "proficiency": item[1],
                "scale": item[2],
            })
    return languages


def parse_authors_citation(authors_str: str) -> list:
    """
    Parse an author string in 'LastName, F.I., NextLast, G.H., ...' format
    into a list of 'LastName, F.I.' strings.

    The regex detects author boundaries by looking for a comma followed by a
    space and then a new last-name token (starts with an uppercase letter and
    contains at least two characters without being purely initials).
    """
    authors_str = authors_str.strip().rstrip(",. ")
    if not authors_str:
        return []

    # Split on ', ' that is followed by an uppercase word (a new surname),
    # i.e. not just a single-letter initial like 'F.' or a hyphenated
    # initial like 'M-C.' after a comma.
    # A surname-start is: capital letter then ≥1 lowercase letter (no hyphen
    # immediately after the first capital, so 'M-C.' is kept with its surname).
    parts = re.split(r",\s+(?=[A-Z][a-zÀ-ÿ])", authors_str)

    authors = []
    for part in parts:
        author = part.strip().rstrip(",")
        if author:
            authors.append(author)
    return authors


def extract_publications(lines: list) -> dict:
    """
    Parse the Publications section.
    Returns dict with keys: journal_articles, book_chapters,
    under_review_or_in_prep.
    """
    pub_lines = extract_section_lines(lines, "Publications")

    journal_articles = []
    book_chapters = []
    under_review = []
    current_sub = None

    for line in pub_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        m = re.match(r"\\subsection\{([^}]*)\}", line_s)
        if m:
            sub = clean_latex(m.group(1)).lower()
            if "peer" in sub or "article" in sub or "journal" in sub:
                current_sub = "journal"
            elif "book" in sub or "chapter" in sub:
                current_sub = "chapter"
            elif "review" in sub or "prep" in sub or "preparation" in sub:
                current_sub = "under_review"
            else:
                current_sub = None
            continue

        # Each publication is a \cvitem{label}{citation text}
        m_item = re.match(r"\\cvitem\{([^}]*)\}\{(.*)\}$", line_s)
        if not m_item:
            # Handle multi-line items (simplified: skip)
            continue

        label = clean_latex(m_item.group(1))
        raw_text = m_item.group(2)

        # Extract IF and quartile from label e.g. "IF = 6.4 (Q1)"
        impact_factor = ""
        quartile = ""
        m_if = re.match(r"IF\s*=\s*([\d.]+)\s*\(?(Q\d)?\)?", label, re.IGNORECASE)
        if m_if:
            impact_factor = float(m_if.group(1))
            quartile = m_if.group(2) or ""

        citation = clean_latex(raw_text)  # noqa: F841 (used for type detection below)

        stub = _build_pub_stub(raw_text, impact_factor, quartile, current_sub)

        if current_sub == "journal":
            journal_articles.append(stub)
        elif current_sub == "chapter":
            book_chapters.append(stub)
        elif current_sub == "under_review":
            under_review.append(stub)

    return {
        "journal_articles": journal_articles,
        "book_chapters": book_chapters,
        "under_review_or_in_prep": under_review,
    }


def _parse_authors_year(citation: str):
    """
    Attempt to split a citation into (authors_list, year, remainder).
    Format is typically: "Author A., Author B., ... YEAR. Title. Journal..."
    """
    # Find the year (4-digit number 19xx or 20xx)
    m = re.search(r"\b((?:19|20)\d{2})\b\.?", citation)
    if not m:
        return [], "", citation
    year_pos = m.start()
    year = m.group(1)
    authors_str = citation[:year_pos].rstrip(" ,.")
    remainder = citation[m.end():].lstrip(" .,").strip()
    authors = parse_authors_citation(authors_str)
    return authors, year, remainder


def _build_pub_stub(raw_text: str, impact_factor, quartile: str,
                    pub_type: str) -> dict:
    """Build a minimal publication stub dict from raw citation text.

    raw_text should be the unprocessed LaTeX text of the citation body so that
    we can use the textit marker trick to separate title from journal name.
    """
    sync = "manual" if pub_type in ("chapter", "under_review") else "auto"

    # First pass: clean with textit marker so italic spans (usually the
    # journal name) are wrapped in « … » and can be detected.
    marked = clean_latex(raw_text, keep_textit_marker=True)

    # Extract journal/venue from «...» marker if present
    journal = ""
    m_italic = re.search(r"«([^»]+)»", marked)
    if m_italic:
        journal = m_italic.group(1).strip()
        # Remove the «...» span from the string used for title extraction
        marked_no_journal = (
            marked[: m_italic.start()].rstrip(" ,") + " "
            + marked[m_italic.end():].lstrip(" ,")
        ).strip()
    else:
        marked_no_journal = marked

    # Now work on fully cleaned text (no markers) for author/year/title
    citation = re.sub(r"«[^»]*»", "", marked).strip()
    citation = " ".join(citation.split())

    authors, year, remainder = _parse_authors_year(
        re.sub(r"«[^»]*»", "", marked_no_journal)
    )

    # Title is the text from the start of remainder up to the first «
    # (journal marker) or the first sentence boundary.
    title = ""
    m_title = re.match(r"^([^.]+(?:\([^)]*\)[^.]*)?\.?)", remainder)
    if m_title:
        title = m_title.group(1).rstrip(". ")

    # If title ends with the journal name (no marker was found), strip it
    # — leave it blank and let the user fill it in.
    title = re.sub(r"\s+$", "", title)

    stub = {
        "sync": f"{sync}   # {'auto-sync' if sync == 'auto' else 'manual'}",
        "authors": authors,
        "year": int(year) if year else "",
        "title": title,
        "impact_factor": impact_factor,
        "quartile": quartile,
        "doi": "",
        "url": "",
    }
    if pub_type == "journal":
        stub["journal"] = journal
        stub["volume"] = ""
        stub["pages"] = ""
    elif pub_type == "chapter":
        stub["book"] = journal  # often the book title is in italic
        stub["editors"] = []
        stub["publisher"] = ""
    elif pub_type == "under_review":
        stub["status"] = "under review"
        stub["journal"] = journal

    return stub


def extract_conference_presentations(lines: list) -> list:
    """Parse the Conference Presentations section."""
    conf_lines = extract_section_lines(lines, "Conference Presentations")
    presentations = []

    for line in conf_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("%"):
            continue
        m_item = re.match(r"\\cvitem\{(\d+)\}\{(.*)\}$", line_s)
        if not m_item:
            continue
        index = int(m_item.group(1))
        raw_text = m_item.group(2)
        citation = clean_latex(raw_text)

        # Detect presentation type
        ptype = "poster"
        if re.search(r"oral presentation", citation, re.IGNORECASE):
            ptype = "oral"

        authors, year, remainder = _parse_authors_year(citation)
        title = ""
        m_title = re.match(r"^([^.]+(?:\([^)]*\)[^.]*)?\.)", remainder)
        if m_title:
            title = m_title.group(1).rstrip(".")

        presentations.append({
            "index": index,
            "authors": authors,
            "year": int(year) if year else "",
            "title": title,
            "venue": "",   # hard to parse reliably; populate manually
            "location": "",
            "date": "",
            "type": ptype,
        })
    return presentations


# ---------------------------------------------------------------------------
# YAML serialisation helpers
# ---------------------------------------------------------------------------

def _yaml_authors(authors: list, indent_spaces: int = 6) -> str:
    if not authors:
        return " []"
    pad = " " * indent_spaces
    lines = [f"\n{pad}- {yaml_str(a)}" for a in authors]
    return "".join(lines)


def _yaml_list_of_str(items: list, indent_spaces: int = 6) -> str:
    if not items:
        return " []"
    pad = " " * indent_spaces
    lines = [f"\n{pad}- {yaml_str(str(i))}" for i in items]
    return "".join(lines)


def serialise_personal(p: dict) -> str:
    empty = '""'
    return (
        "personal:\n"
        f"  firstname: {yaml_str(p['firstname'])}\n"
        f"  familyname: {yaml_str(p['familyname'])}\n"
        f"  title: {yaml_str(p['title'])}\n"
        f"  email: {p['email'] or empty}\n"
        f"  orcid: {yaml_str(p['orcid']) if p['orcid'] else empty}  # manual\n"
        f"  id_hal: {yaml_str(p['id_hal']) if p['id_hal'] else empty}  # manual\n"
        f"  photo: {p['photo'] or empty}\n"
        f"  homepage: {yaml_str(p['homepage']) if p['homepage'] else empty}\n"
        f"  mobile: {yaml_str(p['mobile']) if p['mobile'] else empty}\n"
    )


def serialise_education(entries: list) -> str:
    if not entries:
        return "education: []\n"
    out = ["education:"]
    for e in entries:
        out.append(f"  - degree: {yaml_str(e.get('degree', ''))}")
        out.append(f"    institution: {yaml_str(e.get('institution', ''))}")
        out.append(f"    country: {yaml_str(e.get('country', ''))}")
        out.append(f"    start: {e.get('start', '')}")
        out.append(f"    end: {e.get('end', '')}")
        out.append(f"    honours: {yaml_str(e.get('honours', ''))}")
        out.append(f"    thesis_title: {yaml_str(e.get('thesis_title', ''))}")
        out.append(f"    supervisor: {yaml_str(e.get('supervisor', ''))}")
        out.append(f"    description: {yaml_str(e.get('description', ''))}")
        out.append("")
    return "\n".join(out) + "\n"


def serialise_experience(exp: dict) -> str:
    out = ["experience:"]
    out.append("  research:")
    for e in exp.get("research", []):
        out.append(f"    - position: {yaml_str(e.get('position', ''))}")
        out.append(f"      institution: {yaml_str(e.get('institution', ''))}")
        out.append(f"      country: {yaml_str(e.get('country', ''))}")
        out.append(f"      start: {yaml_str(str(e.get('start', '')))}")
        out.append(f"      end: {yaml_str(str(e.get('end', '')))}")
        out.append(f"      supervisor: {yaml_str(e.get('supervisor', ''))}")
        out.append(f"      team: {yaml_str(e.get('team', ''))}")
        out.append(f"      description: {yaml_str(e.get('description', ''))}")
        out.append("")
    out.append("  teaching:")
    for e in exp.get("teaching", []):
        out.append(f"    - course: {yaml_str(e.get('course', e.get('position', '')))}")
        out.append(f"      institution: {yaml_str(e.get('institution', ''))}")
        out.append(f"      country: {yaml_str(e.get('country', ''))}")
        start = e.get("start", "")
        end = e.get("end", "")
        if start == end or not end:
            out.append(f"      year: {yaml_str(str(start))}")
        else:
            out.append(f"      start: {yaml_str(str(start))}")
            out.append(f"      end: {yaml_str(str(end))}")
        out.append(f"      notes: {yaml_str(e.get('notes', ''))}")
        out.append("")
    return "\n".join(out) + "\n"


def _serialise_pub(p: dict, base_indent: int = 4) -> list:
    pad = " " * base_indent
    empty = '""'
    lines = []
    sync_val = p.get("sync", "auto   # auto-sync")
    lines.append(f"{pad}- sync: {sync_val}")
    # Authors
    authors = p.get("authors", [])
    if authors:
        lines.append(f"{pad}  authors:")
        for a in authors:
            lines.append(f"{pad}    - {yaml_str(a)}")
    else:
        lines.append(f"{pad}  authors: []")
    lines.append(f"{pad}  year: {p.get('year', '') or empty}")
    lines.append(f"{pad}  title: {yaml_str(p.get('title', ''))}")
    if "journal" in p:
        lines.append(f"{pad}  journal: {yaml_str(p.get('journal', ''))}")
    if "volume" in p:
        lines.append(f"{pad}  volume: {yaml_str(str(p.get('volume', '')) )}")
    if "issue" in p:
        lines.append(f"{pad}  issue: {yaml_str(str(p.get('issue', '')))}")
    if "pages" in p:
        lines.append(f"{pad}  pages: {yaml_str(str(p.get('pages', '')))}")
    if "book" in p:
        lines.append(f"{pad}  book: {yaml_str(p.get('book', ''))}")
    if "editors" in p:
        editors = p.get("editors", [])
        if editors:
            lines.append(f"{pad}  editors:")
            for ed in editors:
                lines.append(f"{pad}    - {yaml_str(ed)}")
        else:
            lines.append(f"{pad}  editors: []")
    if "publisher" in p:
        lines.append(f"{pad}  publisher: {yaml_str(p.get('publisher', ''))}")
    if "status" in p:
        lines.append(f"{pad}  status: {yaml_str(p.get('status', ''))}")
    if p.get("impact_factor") not in ("", None):
        lines.append(f"{pad}  impact_factor: {p['impact_factor']}")
    else:
        lines.append(f"{pad}  impact_factor: \"\"")
    if p.get("quartile"):
        lines.append(f"{pad}  quartile: {p['quartile']}")
    else:
        lines.append(f"{pad}  quartile: \"\"")
    lines.append(f"{pad}  doi: \"\"")
    lines.append(f"{pad}  url: \"\"")
    lines.append("")
    return lines


def serialise_publications(pubs: dict) -> str:
    out = ["publications:"]
    out.append("  journal_articles:")
    for p in pubs.get("journal_articles", []):
        out.extend(_serialise_pub(p, base_indent=4))
    out.append("  book_chapters:")
    for p in pubs.get("book_chapters", []):
        out.extend(_serialise_pub(p, base_indent=4))
    out.append("  under_review_or_in_prep:")
    for p in pubs.get("under_review_or_in_prep", []):
        out.extend(_serialise_pub(p, base_indent=4))
    return "\n".join(out) + "\n"


def serialise_conference_presentations(presentations: list) -> str:
    if not presentations:
        return "conference_presentations: []\n"
    out = ["conference_presentations:"]
    for p in presentations:
        out.append(f"  - index: {p['index']}")
        authors = p.get("authors", [])
        if authors:
            out.append("    authors:")
            for a in authors:
                out.append(f"      - {yaml_str(a)}")
        else:
            out.append("    authors: []")
        out.append(f"    year: {p.get('year', '')}")
        out.append(f"    title: {yaml_str(p.get('title', ''))}")
        out.append(f"    venue: {yaml_str(p.get('venue', ''))}")
        out.append(f"    location: {yaml_str(p.get('location', ''))}")
        out.append(f"    date: {yaml_str(p.get('date', ''))}")
        out.append(f"    type: {p.get('type', 'poster')}")
        out.append("")
    return "\n".join(out) + "\n"


def serialise_skills(skills: dict) -> str:
    if not skills:
        return "skills: {}\n"
    out = ["skills:"]
    for key, val in skills.items():
        out.append(f"  {key}:")
        out.append(f"    label: {yaml_str(val.get('label', key))}")
        tools = val.get("tools", [])
        if tools:
            out.append("    tools:")
            for t in tools:
                out.append(f"      - {yaml_str(t)}")
        else:
            out.append("    tools: []")
        out.append("")
    return "\n".join(out) + "\n"


def serialise_languages(langs: list) -> str:
    if not langs:
        return "languages: []\n"
    out = ["languages:"]
    for l in langs:
        out.append(f"  - language: {yaml_str(l['language'])}")
        out.append(f"    proficiency: {yaml_str(l['proficiency'])}")
        out.append(f"    scale: {yaml_str(l.get('scale', ''))}")
        out.append("")
    return "\n".join(out) + "\n"


def serialise_awards(awards: list) -> str:
    if not awards:
        return "honors_awards: []\n"
    out = ["honors_awards:"]
    for a in awards:
        out.append(f"  - year: {a['year']}")
        out.append(f"    award: {yaml_str(a['award'])}")
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

HEADER = """\
# ==============================================================================
# cv.yaml — Structured CV data for Scott A. Love
# Generated by scripts/extract_from_latex.py
# ==============================================================================
#
# EDITING GUIDE
# -------------
# - Fields marked "# auto-sync" are candidates for automatic update via API
#   scripts (e.g. ORCID / OpenAlex). Edit with care; changes may be overwritten
#   on the next sync unless you also set  sync: manual  on that entry.
# - Fields marked "# manual" are always preserved by automation scripts.
# - Leave optional fields blank ("") or remove them if not applicable.
# - Dates: use ISO format YYYY-MM-DD where possible; plain years are fine.
# ==============================================================================

# CV rendering metadata
cv:
  language: "en"
  style: "moderncv"
  theme:
    style: "casual"
    color: "blue"
  generated_from: "overleaf_seed"

# Publication sync configuration
publication_sync:
  # Local YAML data stays canonical; sync sources are upstream providers only.
  source_mode: hal_plus_orcid  # hal_only | orcid_only | hal_plus_orcid
  sources:
    hal: true
    orcid: true
  # Publications whose DOI or title matches an entry here are treated as
  # 'manual' and will never be overwritten by the sync scripts.
  manual_overrides: []

"""

SECTION_SEPARATOR = "\n# {line}\n# {title}\n# {line}\n".format


def build_yaml(personal, education, experience, publications,
               conference_presentations, skills, languages, awards) -> str:
    parts = [HEADER]

    parts.append(
        SECTION_SEPARATOR(
            line="-" * 78, title="PERSONAL INFORMATION"
        ) + "\n"
    )
    parts.append(serialise_personal(personal) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="EDUCATION") + "\n"
    )
    parts.append(serialise_education(education) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="PROFESSIONAL EXPERIENCE") + "\n"
    )
    parts.append(serialise_experience(experience) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="PUBLICATIONS") + "\n"
        + "# sync: auto   — entry may be updated by sync_publications.py\n"
        + "# sync: manual — entry is hand-maintained; "
          "automation will not overwrite it\n\n"
    )
    parts.append(serialise_publications(publications) + "\n")

    parts.append(
        SECTION_SEPARATOR(
            line="-" * 78, title="CONFERENCE PRESENTATIONS"
        ) + "\n"
    )
    parts.append(serialise_conference_presentations(conference_presentations) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="SKILLS") + "\n"
    )
    parts.append(serialise_skills(skills) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="LANGUAGES") + "\n"
    )
    parts.append(serialise_languages(languages) + "\n")

    parts.append(
        SECTION_SEPARATOR(line="-" * 78, title="HONORS & AWARDS") + "\n"
    )
    parts.append(serialise_awards(awards) + "\n")

    return "".join(parts)


def report(label: str, count: int) -> None:
    """Print extraction summary line."""
    print(f"  {label:<35} {count:>4} item(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Extract CV data from LaTeX source and write cv.yaml"
    )
    parser.add_argument(
        "--input", default=DEFAULT_INPUT,
        help=f"Path to LaTeX CV source (default: {DEFAULT_INPUT})"
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output path for cv.yaml (default: {DEFAULT_OUTPUT})"
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== CV Extraction from LaTeX ===")
    print(f"Input : {input_path}")
    print(f"Output: {output_path}")
    print()

    with open(input_path, encoding="utf-8") as fh:
        raw = fh.read()

    # Split into lines; keep original indexing for debugging
    lines = raw.splitlines()

    # ---- Extract each section ----
    personal = extract_personal(lines)
    education = extract_education(lines)
    experience = extract_experience(lines)
    publications = extract_publications(lines)
    conference_presentations = extract_conference_presentations(lines)
    skills = extract_skills(lines)
    languages = extract_languages(lines)
    awards = extract_awards(lines)

    # ---- Report ----
    print("Extraction summary:")
    report("Personal fields populated",
           sum(1 for v in personal.values() if v))
    report("Education entries", len(education))
    report("Research experience entries", len(experience.get("research", [])))
    report("Teaching entries", len(experience.get("teaching", [])))
    report("Journal articles", len(publications.get("journal_articles", [])))
    report("Book chapters", len(publications.get("book_chapters", [])))
    report("Under review / in prep", len(publications.get("under_review_or_in_prep", [])))
    report("Conference presentations", len(conference_presentations))
    report("Skill categories", len(skills))
    report("Languages", len(languages))
    report("Honors & awards", len(awards))

    # ---- Write output ----
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    yaml_content = build_yaml(
        personal, education, experience, publications,
        conference_presentations, skills, languages, awards
    )

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(yaml_content)

    print(f"\nWrote {len(yaml_content):,} bytes to {output_path}")
    print("\nNOTE: Review the output file carefully — especially:")
    print("  • Publication journal/venue fields (left blank; enhance via sync)")
    print("  • Conference presentation venue/location/date fields")
    print("  • ORCID (check it matches your profile)")
    print("  • Any multi-line LaTeX that may not have parsed cleanly")
    print()


if __name__ == "__main__":
    main()
