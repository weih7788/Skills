#!/usr/bin/env python3
"""
Ensure every source_refs / related_pages front-matter item has a jumpable body link
with repo-root relative label. Appends missing Source:/Ref: lines to Sources /
Related Pages sections (creates sections when absent).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from knowledge_links import collect_valid_body_links, repo_ref_link
from knowledge_metadata import parse_front_matter
from migrate_source_links import migrate_page


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


SOURCES_HEADING = re.compile(r"^##\s+Sources\s*$", re.MULTILINE)
RELATED_HEADING = re.compile(r"^##\s+Related Pages\s*$", re.MULTILINE)


def split_body_sections(body: str) -> tuple[str, str | None, str | None]:
    """Return (prefix, sources_block, related_block) where blocks include heading."""
    sources_match = SOURCES_HEADING.search(body)
    related_match = RELATED_HEADING.search(body)

    if not sources_match and not related_match:
        return body.rstrip(), None, None

    first_idx = min(
        i for i in (sources_match.start() if sources_match else len(body), related_match.start() if related_match else len(body))
    )
    prefix = body[:first_idx].rstrip()

    sources_block = None
    related_block = None
    tail = body[first_idx:]

    if sources_match and related_match:
        if sources_match.start() < related_match.start():
            sources_block = tail[: related_match.start() - sources_match.start()].rstrip()
            related_block = tail[related_match.start() - sources_match.start() :].rstrip()
        else:
            related_block = tail[: sources_match.start() - related_match.start()].rstrip()
            sources_block = tail[sources_match.start() - related_match.start() :].rstrip()
    elif sources_match:
        sources_block = tail.rstrip()
    else:
        related_block = tail.rstrip()

    return prefix, sources_block, related_block


def append_lines(block: str | None, heading: str, prefix: str, new_lines: list[str]) -> str:
    if not new_lines:
        return block or ""
    entries = "\n".join(new_lines)
    if block:
        return f"{block.rstrip()}\n{entries}\n"
    return f"{heading}\n\n{entries}\n"


def fix_page(page_path: Path, repo_root: Path, *, write: bool = True) -> int:
    original_text = page_path.read_text(encoding="utf-8")
    text, migrate_changes = migrate_page(page_path, repo_root)
    try:
        front_matter = parse_front_matter(text, page_path)
    except ValueError:
        return migrate_changes

    source_refs = [str(x) for x in front_matter.get("source_refs", []) if isinstance(x, str)]
    related_pages = [str(x) for x in front_matter.get("related_pages", []) if isinstance(x, str)]

    body_links, _ = collect_valid_body_links(text, page_path, repo_root)
    missing_sources = [ref for ref in source_refs if ref not in body_links]
    missing_related = [ref for ref in related_pages if ref not in body_links]

    if not missing_sources and not missing_related:
        if migrate_changes and write:
            page_path.write_text(text, encoding="utf-8")
        elif not write:
            page_path.write_text(original_text, encoding="utf-8")
        return migrate_changes

    if text.startswith("---"):
        end = text.find("\n---\n", 4)
        header = text[: end + 5]
        body = text[end + 5 :]
    else:
        header = ""
        body = text

    prefix, sources_block, related_block = split_body_sections(body)

    source_lines = [
        f"Source: {repo_ref_link(page_path, repo_root, ref)}"
        for ref in missing_sources
    ]
    ref_lines = [f"Ref: {repo_ref_link(page_path, repo_root, ref)}" for ref in missing_related]

    sources_block = append_lines(sources_block, "## Sources", "Source:", source_lines)
    related_block = append_lines(related_block, "## Related Pages", "Ref:", ref_lines)

    new_body = prefix
    if sources_block:
        new_body = f"{new_body}\n\n{sources_block}".rstrip()
    if related_block:
        new_body = f"{new_body}\n\n{related_block}".rstrip()
    new_body = new_body + "\n"

    new_text = header + new_body
    if write:
        page_path.write_text(new_text, encoding="utf-8")
    else:
        page_path.write_text(original_text, encoding="utf-8")
    return migrate_changes + len(missing_sources) + len(missing_related)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fix missing wiki source_refs / related_pages body links")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    wiki_root = repo_root / "knowledge" / "wiki"
    if not wiki_root.exists():
        print(f"[ERROR] wiki root not found: {wiki_root}")
        return 1

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    updated = 0
    total_changes = 0

    for page in pages:
        changes = fix_page(page, repo_root, write=not args.dry_run)
        if changes:
            updated += 1
            total_changes += changes
            action = "would update" if args.dry_run else "updated"
            print(f"[OK] {action} {page} ({changes} change(s))")

    summary = "would change" if args.dry_run else "changed"
    print(f"[OK] fix {summary} {updated} page(s), {total_changes} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
