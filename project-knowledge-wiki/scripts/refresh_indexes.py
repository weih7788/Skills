#!/usr/bin/env python3
"""
Refresh auto-generated blocks in knowledge index files.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure

START = "<!-- AUTO-GENERATED:START -->"
END = "<!-- AUTO-GENERATED:END -->"


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


def build_wiki_block(repo_root: Path) -> str:
    wiki_root = repo_root / "knowledge" / "wiki"
    files = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    lines = []
    for file_path in files:
        rel = file_path.relative_to(wiki_root).as_posix()
        lines.append(f"- [{file_path.name}](./{rel})")
    return "\n".join(lines)


def build_raw_block(repo_root: Path) -> str:
    raw_index = repo_root / "knowledge" / "raw" / "README.md"
    candidates = []
    for root in ("docs", "doc"):
        base = repo_root / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                rel = path.relative_to(repo_root).as_posix()
                candidates.append(rel)

    lines = []
    for rel in candidates:
        target = os.path.relpath(repo_root / rel, raw_index.parent).replace(os.sep, "/")
        lines.append(f"- [{Path(rel).name}]({target})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh knowledge index files")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    ensure_knowledge_structure(repo_root)
    try:
        replace_block(repo_root / "knowledge" / "wiki" / "README.md", build_wiki_block(repo_root))
        replace_block(repo_root / "knowledge" / "raw" / "README.md", build_raw_block(repo_root))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print("[OK] refreshed knowledge index files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
