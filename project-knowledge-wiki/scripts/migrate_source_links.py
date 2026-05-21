#!/usr/bin/env python3
"""
Migrate knowledge wiki pages to the repo-root relative markdown link label format.

Updates:
- Markdown link labels from filename-only to repo-root relative paths
- Source: lines that use plain text repo-relative paths
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from knowledge_links import (
    MARKDOWN_LINK,
    REF_LINE,
    SOURCE_LINE,
    is_external_link,
    is_repo_relative,
    normalize_markdown_link_target,
    repo_ref_link,
    resolve_markdown_link,
    to_repo_ref,
)


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


def migrate_link_labels(text: str, page_path: Path, repo_root: Path) -> tuple[str, int]:
    changes = 0

    def replace_link(match: re.Match[str]) -> str:
        nonlocal changes
        label = match.group(1)
        target = match.group(2)
        normalized = normalize_markdown_link_target(target)
        if not normalized or is_external_link(normalized) or Path(normalized).is_absolute():
            return match.group(0)
        resolved = resolve_markdown_link(page_path, normalized)
        if not resolved.exists():
            return match.group(0)
        try:
            expected_label = to_repo_ref(repo_root, resolved)
        except ValueError:
            return match.group(0)
        if label == expected_label:
            return match.group(0)
        changes += 1
        return f"[{expected_label}]({target})"

    return MARKDOWN_LINK.sub(replace_link, text), changes


def migrate_prefixed_lines(
    text: str,
    page_path: Path,
    repo_root: Path,
    line_pattern: re.Pattern[str],
    prefix_name: str,
) -> tuple[str, int]:
    changes = 0

    def replace_line(match: re.Match[str]) -> str:
        nonlocal changes
        prefix = match.group(1)
        content = match.group(2).strip()
        if MARKDOWN_LINK.search(content):
            return match.group(0)

        path_match = re.match(r"^(`?)([^`\s]+)\1(?:\s+(.*))?$", content)
        if not path_match:
            return match.group(0)

        repo_ref = path_match.group(2)
        suffix = path_match.group(3) or ""
        if not is_repo_relative(repo_ref):
            return match.group(0)
        resolved = (repo_root / repo_ref).resolve()
        if not resolved.exists():
            return match.group(0)

        link = repo_ref_link(page_path, repo_root, repo_ref)
        if suffix:
            link = f"{link} {suffix}"
        changes += 1
        return f"{prefix}{prefix_name}: {link}"

    return line_pattern.sub(replace_line, text), changes


def migrate_page(page_path: Path, repo_root: Path) -> tuple[str, int]:
    text = page_path.read_text(encoding="utf-8")
    text, link_changes = migrate_link_labels(text, page_path, repo_root)
    text, source_changes = migrate_prefixed_lines(text, page_path, repo_root, SOURCE_LINE, "Source")
    text, ref_changes = migrate_prefixed_lines(text, page_path, repo_root, REF_LINE, "Ref")
    return text, link_changes + source_changes + ref_changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate wiki source links to repo-root relative labels")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    wiki_root = repo_root / "knowledge" / "wiki"
    if not wiki_root.exists():
        print(f"[ERROR] wiki root not found: {wiki_root}")
        return 1

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    updated_pages = 0
    total_changes = 0

    for page in pages:
        new_text, changes = migrate_page(page, repo_root)
        if changes == 0:
            continue
        updated_pages += 1
        total_changes += changes
        action = "would update" if args.dry_run else "updated"
        print(f"[OK] {action} {page} ({changes} change(s))")
        if not args.dry_run:
            page.write_text(new_text, encoding="utf-8")

    if updated_pages == 0:
        print(f"[OK] no migration needed for {len(pages)} page(s)")
        return 0

    summary = "would change" if args.dry_run else "changed"
    print(f"[OK] migration {summary} {updated_pages} page(s), {total_changes} replacement(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
