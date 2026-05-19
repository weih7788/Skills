"""Shared bootstrap helpers for repo-local knowledge/ directories."""

from __future__ import annotations

from pathlib import Path

WIKI_DIRS = (
    "domains",
    "concepts",
    "flows",
    "integrations",
    "data-models",
    "runbooks",
    "decisions",
)

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_TEMPLATE_PATH = SKILL_ROOT / "references" / "schema.md"


def load_schema_template() -> str:
    if not SCHEMA_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"schema template not found: {SCHEMA_TEMPLATE_PATH}")
    return SCHEMA_TEMPLATE_PATH.read_text(encoding="utf-8")


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def ensure_knowledge_structure(repo_root: Path) -> None:
    knowledge_root = repo_root / "knowledge"
    wiki_root = knowledge_root / "wiki"
    raw_root = knowledge_root / "raw"

    for directory in (knowledge_root, wiki_root, raw_root, *(wiki_root / dirname for dirname in WIKI_DIRS)):
        directory.mkdir(parents=True, exist_ok=True)

    write_if_missing(
        knowledge_root / "README.md",
        """# Project Knowledge

This directory contains the project-local LLM wiki.

- `wiki/`: curated project knowledge pages
- `raw/`: index of source artifacts used by the wiki
- `SCHEMA.md`: structure, metadata, citation rules, and templates
""",
    )
    write_if_missing(knowledge_root / "SCHEMA.md", load_schema_template())
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
