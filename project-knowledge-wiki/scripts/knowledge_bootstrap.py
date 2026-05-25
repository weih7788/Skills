"""Shared bootstrap helpers for repo-local knowledge/ directories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from knowledge_resolver import default_repo_root, resolve_knowledge_layout

WIKI_DIRS = (
    "domains",
    "concepts",
    "flows",
    "integrations",
    "data-models",
    "runbooks",
    "decisions",
)

def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def ensure_knowledge_structure(knowledge_root: Path, *, create_root: bool = True) -> None:
    if knowledge_root.is_dir():
        pass
    elif create_root:
        knowledge_root.mkdir(parents=True, exist_ok=True)
    else:
        raise FileNotFoundError(f"knowledge root does not exist: {knowledge_root}")

    wiki_root = knowledge_root / "wiki"
    raw_root = knowledge_root / "raw"

    for directory in (knowledge_root, wiki_root, raw_root, *(wiki_root / dirname for dirname in WIKI_DIRS)):
        directory.mkdir(parents=True, exist_ok=True)

    write_if_missing(
        knowledge_root / "README.md",
        """# Project Knowledge

This directory contains the project-local LLM wiki (Markdown pages and indexes only).

- `wiki/`: curated project knowledge pages
- `raw/`: index of source artifacts used by the wiki

Maintenance scripts (bootstrap, lint, migrate, etc.) live in the skill install directory, not here.
Schema rules live in the skill's references/schema.md and are not copied into this knowledge root.
""",
    )
    write_if_missing(
        wiki_root / "README.md",
        """# Wiki Index

<!-- AUTO-GENERATED:START -->
<!-- AUTO-GENERATED:END -->
""",
    )
    write_if_missing(
        raw_root / "README.md",
        """# Raw Source Index

<!-- AUTO-GENERATED:START -->
<!-- AUTO-GENERATED:END -->
""",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the minimal knowledge/ structure")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=None,
        help="Explicit knowledge root. Defaults to knowledge.md config or repo_root/knowledge.",
    )
    args = parser.parse_args()

    layout = resolve_knowledge_layout(args.repo_root.resolve(), args.knowledge_root)
    ensure_knowledge_structure(layout.knowledge_root)
    if layout.is_external:
        print(f"[OK] ensured knowledge structure under {layout.knowledge_root} (external, via knowledge.md)")
    else:
        print(f"[OK] ensured knowledge structure under {layout.knowledge_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
