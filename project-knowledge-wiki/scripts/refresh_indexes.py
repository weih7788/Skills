#!/usr/bin/env python3
"""
Refresh auto-generated blocks in knowledge index files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure
from knowledge_config import STATUS_ORDER, TYPE_TO_DIR
from knowledge_links import repo_ref_link
from knowledge_metadata import read_front_matter

START = "<!-- AUTO-GENERATED:START -->"
END = "<!-- AUTO-GENERATED:END -->"
DEFAULT_SOURCE_ROOTS = ("docs", "doc", "sql", "scripts", "db", "database", "migrations")


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


def replace_block(path: Path, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise ValueError(f"markers not found in {path}")
    before, remainder = text.split(START, 1)
    _, after = remainder.split(END, 1)
    path.write_text(f"{before}{START}\n{content}\n{END}{after}", encoding="utf-8")


def format_page_line(wiki_root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(wiki_root).as_posix()
    try:
        front_matter = read_front_matter(file_path)
    except ValueError:
        return f"- [{file_path.name}](./{rel})"

    title = front_matter.get("title") or file_path.stem
    status = front_matter.get("status") or "unknown"
    last_verified_at = front_matter.get("last_verified_at") or "unknown"
    return f"- [{title}](./{rel}) - `{status}` - verified `{last_verified_at}`"


def build_wiki_block(repo_root: Path) -> str:
    wiki_root = repo_root / "knowledge" / "wiki"
    files = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    lines = []

    for page_type, dirname in TYPE_TO_DIR.items():
        typed_files = [path for path in files if path.parent.name == dirname]
        if not typed_files:
            continue

        def sort_key(path: Path) -> tuple[int, str, str]:
            try:
                front_matter = read_front_matter(path)
            except ValueError:
                return (99, path.name, path.as_posix())
            status = str(front_matter.get("status", ""))
            title = str(front_matter.get("title", path.stem))
            return (STATUS_ORDER.get(status, 99), title.lower(), path.as_posix())

        lines.append(f"## {page_type}")
        lines.extend(format_page_line(wiki_root, path) for path in sorted(typed_files, key=sort_key))
        lines.append("")

    untyped_files = [path for path in files if path.parent.name not in TYPE_TO_DIR.values()]
    if untyped_files:
        lines.append("## other")
        lines.extend(format_page_line(wiki_root, path) for path in untyped_files)
        lines.append("")

    return "\n".join(lines)


def build_raw_block(repo_root: Path, source_roots: list[str]) -> str:
    raw_index = repo_root / "knowledge" / "raw" / "README.md"
    candidates = []
    for root in source_roots:
        base = repo_root / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(repo_root).as_posix()
                candidates.append(rel)

    lines = []
    for rel in candidates:
        lines.append(f"- {repo_ref_link(raw_index, repo_root, rel)}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh knowledge index files")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--source-root",
        action="append",
        default=[],
        help="Repo-root relative raw source directory to scan. Repeat for multiple roots.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    source_roots = args.source_root or list(DEFAULT_SOURCE_ROOTS)
    ensure_knowledge_structure(repo_root)
    try:
        replace_block(repo_root / "knowledge" / "wiki" / "README.md", build_wiki_block(repo_root))
        replace_block(repo_root / "knowledge" / "raw" / "README.md", build_raw_block(repo_root, source_roots))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print("[OK] refreshed knowledge index files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
