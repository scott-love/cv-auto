#!/usr/bin/env python3
"""
generate_latex.py — Render data/cv.yaml → build/cv.tex using Jinja2.

Usage
-----
    python scripts/generate_latex.py [options]

Options
-------
    --input    PATH   YAML data file       (default: data/cv.yaml)
    --template PATH   Jinja2 template file (default: templates/cv.tex.j2)
    --output   PATH   Output .tex file     (default: build/cv.tex)
    -h, --help        Show this help message

After generating build/cv.tex, copy the moderncv class/style files alongside
it (or into the build/ directory) and compile with:

    cp templates/*.cls templates/*.sty build/
    cd build && pdflatex cv.tex

Requirements
------------
    pip install jinja2 pyyaml
"""

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check — give a friendly message if packages are missing
# ---------------------------------------------------------------------------
try:
    import yaml
except ImportError:
    sys.exit(
        "Error: PyYAML is not installed.  Run:  pip install pyyaml"
    )

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
except ImportError:
    sys.exit(
        "Error: Jinja2 is not installed.  Run:  pip install jinja2"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    """Load and parse a YAML file; raise with a clear message on failure."""
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        sys.exit(f"Error: YAML file not found: {path}")
    except yaml.YAMLError as exc:
        sys.exit(f"Error: Malformed YAML in {path}:\n{exc}")
    if not isinstance(data, dict):
        sys.exit(f"Error: Expected a mapping at the top level of {path}")
    return data


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in a plain-text string."""
    if not isinstance(text, str):
        return text
    # Backslash must be replaced first to avoid double-escaping later replacements.
    text = text.replace("\\", r"\textbackslash{}")
    text = text.replace("&",  r"\&")
    text = text.replace("%",  r"\%")
    text = text.replace("$",  r"\$")
    text = text.replace("#",  r"\#")
    text = text.replace("_",  r"\_")
    text = text.replace("{",  r"\{")
    text = text.replace("}",  r"\}")
    text = text.replace("~",  r"\textasciitilde{}")
    text = text.replace("^",  r"\textasciicircum{}")
    return text


def render_template(template_path: Path, context: dict) -> str:
    """Render a Jinja2 template with the given context dict."""
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["escape_latex"] = escape_latex
    try:
        tmpl = env.get_template(template_path.name)
    except TemplateNotFound:
        sys.exit(f"Error: Template not found: {template_path}")
    try:
        return tmpl.render(**context)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Error: Template rendering failed:\n{exc}")


def write_output(path: Path, content: str) -> None:
    """Create parent directories if needed and write content to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary reporting
# ---------------------------------------------------------------------------

def print_summary(data: dict, output: Path) -> None:
    """Print a human-readable summary of what was rendered."""
    pubs = data.get("publications", {})
    journal_n = len(pubs.get("journal_articles", []) or [])
    chapter_n = len(pubs.get("book_chapters", []) or [])
    review_n = len(pubs.get("under_review_or_in_prep", []) or [])
    conf_n = len(data.get("conference_presentations", []) or [])

    edu_n = len(data.get("education", []) or [])
    exp = data.get("experience", {})
    research_n = len(exp.get("research", []) or [])
    teaching_n = len(exp.get("teaching", []) or [])
    skills_n = len(data.get("skills", {}) or {})
    lang_n = len(data.get("languages", []) or [])
    awards_n = len(data.get("honors_awards", []) or [])

    print("=" * 60)
    print(f"  Generated: {output}")
    print("=" * 60)
    print(f"  Education entries       : {edu_n}")
    print(f"  Research positions      : {research_n}")
    print(f"  Teaching positions      : {teaching_n}")
    print(f"  Honors & Awards         : {awards_n}")
    print(f"  Skill categories        : {skills_n}")
    print(f"  Languages               : {lang_n}")
    print(f"  Journal articles        : {journal_n}")
    print(f"  Book chapters           : {chapter_n}")
    print(f"  Under review / in prep  : {review_n}")
    print(f"  Conference presentations : {conf_n}")
    print("=" * 60)
    print()
    print("To compile to PDF (requires a LaTeX distribution):")
    print(f"  cp templates/*.cls templates/*.sty {output.parent}/")
    print(f"  cd {output.parent} && pdflatex {output.name}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", default="data/cv.yaml", metavar="PATH",
        help="Path to the YAML data file (default: data/cv.yaml)",
    )
    parser.add_argument(
        "--template", default="templates/cv.tex.j2", metavar="PATH",
        help="Path to the Jinja2 template (default: templates/cv.tex.j2)",
    )
    parser.add_argument(
        "--output", default="build/cv.tex", metavar="PATH",
        help="Path for the generated .tex file (default: build/cv.tex)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    input_path = Path(args.input)
    template_path = Path(args.template)
    output_path = Path(args.output)

    print(f"Loading  : {input_path}")
    data = load_yaml(input_path)

    print(f"Template : {template_path}")
    latex = render_template(template_path, data)

    print(f"Writing  : {output_path}")
    write_output(output_path, latex)

    print_summary(data, output_path)


if __name__ == "__main__":
    main()
