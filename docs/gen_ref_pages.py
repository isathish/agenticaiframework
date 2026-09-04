"""Generate the API reference pages from the package source.

Run by the ``gen-files`` MkDocs plugin at build time. One page is emitted per
public module under ``agenticaiframework/``; ``literate-nav`` reads the
generated ``SUMMARY.md`` to build the sidebar.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

PACKAGE = "agenticaiframework"
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / PACKAGE

# Sub-packages that are implementation detail, not public SDK surface.
EXCLUDED_PACKAGES = {"_internal", "__pycache__"}

nav = mkdocs_gen_files.Nav()

for path in sorted(SRC.rglob("*.py")):
    module_path = path.relative_to(ROOT).with_suffix("")
    parts = list(module_path.parts)

    if any(part in EXCLUDED_PACKAGES for part in parts):
        continue
    if any(part.startswith("_") and part != "__init__" for part in parts[1:]):
        continue

    doc_path = path.relative_to(ROOT).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")

    identifier = ".".join(parts)
    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"---\ntitle: {identifier}\n---\n\n")
        fd.write(f"# `{identifier}`\n\n")
        fd.write(f"::: {identifier}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to(ROOT))

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
