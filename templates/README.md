# Template files

This directory contains the Jinja2 template and the moderncv LaTeX class/style files used to
generate the CV from split YAML data (`data/cv.base.yaml` + `data/publications.yaml`)
or, for legacy compatibility, from `data/cv.yaml`.

## Files

| File | Purpose |
|------|---------|
| `cv.tex.j2` | Jinja2 template — rendered by `scripts/generate_latex.py` into `build/cv.tex` |
| `moderncv.cls` | moderncv document class |
| `moderncvstyle*.sty` | Style variants: casual, classic, oldstyle, banking, empty |
| `moderncvcolor*.sty` | Colour variants: blue, black, grey, orange, purple, red |
| `moderncvcompatibility.sty` | Compatibility shim for older moderncv macros |
| `tweaklist.sty` | Helper package bundled with moderncv |

## moderncv version and licence

**Version:** 1.2.0 (released 2012-10-31)  
**Author:** Xavier Danaux <xdanaux@gmail.com>  
**Licence:** LaTeX Project Public Licence v1.3c — <http://www.latex-project.org/lppl/>

The class and style files are unchanged copies from `source-material/` (originally obtained
via Overleaf / LaTeXTemplates.com).
