"""Generate the API reference pages automatically."""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()  # type: ignore[attr-defined]

root = Path(".")

for path in sorted(root.glob("*.py")):
    module_name = path.stem
    doc_path = Path("api", f"{module_name}.md")

    # Nav paths are relative to the SUMMARY.md location (api/)
    nav[module_name] = f"{module_name}.md"

    with mkdocs_gen_files.open(doc_path, "w") as fd:
        fd.write(f"# {module_name}\n\n::: {module_name}\n")

    mkdocs_gen_files.set_edit_path(doc_path, path)

with mkdocs_gen_files.open("api/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
