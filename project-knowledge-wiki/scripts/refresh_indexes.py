#!/usr/bin/env python3
"""
Refresh auto-generated blocks in knowledge index files.
"""

from __future__ import annotations

import argparse
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure
from knowledge_config import STATUS_ORDER, TYPE_TO_DIR
from knowledge_links import ref_link
from knowledge_metadata import read_front_matter
from knowledge_resolver import default_repo_root, resolve_knowledge_layout

START = "<!-- AUTO-GENERATED:START -->"
END = "<!-- AUTO-GENERATED:END -->"
PROJECT_START_TEMPLATE = "<!-- AUTO-GENERATED:START project={project_key} -->"
PROJECT_END_TEMPLATE = "<!-- AUTO-GENERATED:END project={project_key} -->"
DEFAULT_SOURCE_ROOTS = ("docs", "doc", "sql", "scripts", "db", "database", "migrations")
IGNORED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}


@dataclass(frozen=True)
class PageEntry:
    path: Path
    rel: str
    title: str
    status: str
    last_verified_at: str


def replace_block(path: Path, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise ValueError(f"markers not found in {path}")
    before, remainder = text.split(START, 1)
    _, after = remainder.split(END, 1)
    path.write_text(f"{before}{START}\n{content}\n{END}{after}", encoding="utf-8")


def replace_project_block(path: Path, project_key: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = PROJECT_START_TEMPLATE.format(project_key=project_key)
    end = PROJECT_END_TEMPLATE.format(project_key=project_key)
    block = f"{start}\n{content}\n{end}"

    if start in text and end in text:
        before, remainder = text.split(start, 1)
        _old, after = remainder.split(end, 1)
        path.write_text(f"{before}{block}{after}", encoding="utf-8")
        return

    if START in text and END in text:
        before, remainder = text.split(START, 1)
        old, after = remainder.split(END, 1)
        if not old.strip():
            text = f"{before.rstrip()}\n{after.lstrip()}"

    suffix = "" if text.endswith("\n") else "\n"
    section = f"{suffix}\n## Project: {project_key}\n\n{block}\n"
    path.write_text(f"{text}{section}", encoding="utf-8")


def read_page_entry(wiki_root: Path, file_path: Path) -> PageEntry:
    rel = file_path.relative_to(wiki_root).as_posix()
    try:
        front_matter = read_front_matter(file_path)
    except ValueError:
        return PageEntry(file_path, rel, file_path.name, "unknown", "unknown")

    title = front_matter.get("title") or file_path.stem
    status = front_matter.get("status") or "unknown"
    last_verified_at = front_matter.get("last_verified_at") or "unknown"
    return PageEntry(
        file_path,
        rel,
        str(title),
        str(status),
        str(last_verified_at),
    )


def format_page_line(entry: PageEntry) -> str:
    return f"- [{entry.title}](./{entry.rel}) - `{entry.status}` - verified `{entry.last_verified_at}`"


def build_wiki_block(layout) -> str:
    wiki_root = layout.wiki_root
    entries = [
        read_page_entry(wiki_root, path)
        for path in sorted(wiki_root.rglob("*.md"))
        if path.name != "README.md"
    ]
    lines = []

    for page_type, dirname in TYPE_TO_DIR.items():
        typed_entries = [entry for entry in entries if entry.path.parent.name == dirname]
        if not typed_entries:
            continue

        def sort_key(entry: PageEntry) -> tuple[int, str, str]:
            return (STATUS_ORDER.get(entry.status, 99), entry.title.lower(), entry.path.as_posix())

        lines.append(f"## {page_type}")
        lines.extend(format_page_line(entry) for entry in sorted(typed_entries, key=sort_key))
        lines.append("")

    untyped_entries = [entry for entry in entries if entry.path.parent.name not in TYPE_TO_DIR.values()]
    if untyped_entries:
        lines.append("## other")
        lines.extend(format_page_line(entry) for entry in untyped_entries)
        lines.append("")

    return "\n".join(lines)


def git_source_refs(project_root: Path, source_roots: list[str]) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", project_root.as_posix(), "ls-files", "--", *source_roots],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    raw_refs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    refs = []
    for rel in raw_refs:
        path = project_root / rel
        if path.is_file():
            refs.append(rel)
    if raw_refs and not refs:
        return None
    return sorted(set(refs))


def filesystem_source_refs(project_root: Path, source_roots: list[str]) -> list[str]:
    candidates = []
    for root in source_roots:
        base = project_root / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.relative_to(base).parts):
                continue
            if path.is_file():
                candidates.append(path.relative_to(project_root).as_posix())
    return sorted(candidates)


def source_refs_for_layout(layout, source_roots: list[str]) -> list[str]:
    refs = git_source_refs(layout.project_root, source_roots)
    if refs is not None:
        return refs
    return filesystem_source_refs(layout.project_root, source_roots)


def build_raw_block(layout, source_roots: list[str]) -> str:
    raw_index = layout.raw_root / "README.md"
    lines = []
    for rel in source_refs_for_layout(layout, source_roots):
        label = f"{layout.project_key}:{rel}" if layout.is_external else rel
        lines.append(f"- Source: {ref_link(raw_index, layout, label, kind='source')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh knowledge index files")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=None,
        help="Explicit knowledge root. Defaults to knowledge.md config or repo_root/knowledge.",
    )
    parser.add_argument(
        "--source-root",
        action="append",
        default=[],
        help="Project-root relative raw source directory to scan. Repeat for multiple roots.",
    )
    args = parser.parse_args()

    layout = resolve_knowledge_layout(args.repo_root.resolve(), args.knowledge_root)
    source_roots = args.source_root or list(DEFAULT_SOURCE_ROOTS)
    ensure_knowledge_structure(layout.knowledge_root)
    try:
        replace_block(layout.wiki_root / "README.md", build_wiki_block(layout))
        if layout.is_external:
            replace_project_block(layout.raw_root / "README.md", layout.project_key, build_raw_block(layout, source_roots))
        else:
            replace_block(layout.raw_root / "README.md", build_raw_block(layout, source_roots))
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[OK] refreshed knowledge index files under {layout.knowledge_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
