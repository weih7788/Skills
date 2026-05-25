#!/usr/bin/env python3
"""
Migrate local {repo_root}/knowledge/ to an external knowledge root and write knowledge.md.

Steps:
1. Bootstrap external knowledge_root (create directory when path is configured)
2. Copy local knowledge/ content into external root (merge)
3. Write knowledge.md pointing at external root
4. Normalize wiki related_pages / link labels from knowledge/wiki/ to wiki/
5. Run migrate_source_links pass on external wiki
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure
from knowledge_links import (
    MARKDOWN_LINK,
    REF_LINE,
    SOURCE_LINE,
    ref_link,
    resolve_knowledge_ref,
    resolve_related_ref,
    resolve_source_ref,
)
from knowledge_metadata import parse_front_matter
from knowledge_resolver import (
    default_repo_root,
    has_local_knowledge,
    local_knowledge_dir,
    resolve_knowledge_layout,
    write_knowledge_config,
)
from migrate_source_links import migrate_page

KNOWLEDGE_WIKI_PREFIX = "knowledge/wiki/"
WIKI_PREFIX = "wiki/"


def normalize_ref_path(ref: str) -> str:
    if ref.startswith(KNOWLEDGE_WIKI_PREFIX):
        return ref[len("knowledge/") :]
    return ref


def normalize_page_text(text: str) -> tuple[str, int]:
    changes = 0
    new_text = text

    def replace_label(match: re.Match[str]) -> str:
        nonlocal changes
        label = match.group(1)
        target = match.group(2)
        normalized = normalize_ref_path(label)
        if normalized == label:
            return match.group(0)
        changes += 1
        return f"[{normalized}]({target})"

    new_text = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", replace_label, new_text)

    for old_prefix in (KNOWLEDGE_WIKI_PREFIX, "knowledge/raw/"):
        new_prefix = old_prefix[len("knowledge/") :]
        if old_prefix in new_text:
            count = new_text.count(old_prefix)
            new_text = new_text.replace(old_prefix, new_prefix)
            changes += count

    return new_text, changes


def relink_page_content(text: str, page_path: Path, layout) -> tuple[str, int]:
    changes = 0
    new_text = text

    def relink_markdown(match: re.Match[str]) -> str:
        nonlocal changes
        label = match.group(1)
        target = match.group(2)
        try:
            resolve_knowledge_ref(label, layout)
        except (FileNotFoundError, ValueError):
            return match.group(0)
        rebuilt = ref_link(page_path, layout, label)
        rebuilt_match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", rebuilt)
        if not rebuilt_match:
            return match.group(0)
        new_target = rebuilt_match.group(2)
        if new_target == target:
            return match.group(0)
        changes += 1
        return f"[{label}]({new_target})"

    new_text = MARKDOWN_LINK.sub(relink_markdown, new_text)

    try:
        front_matter = parse_front_matter(new_text, page_path)
    except ValueError:
        return new_text, changes

    for line_pattern, prefix_name, field_name, kind, resolver in (
        (SOURCE_LINE, "Source", "source_refs", "source", resolve_source_ref),
        (REF_LINE, "Ref", "related_pages", "related", resolve_related_ref),
    ):
        value = front_matter.get(field_name, [])
        if not isinstance(value, list):
            continue
        for ref in value:
            if not isinstance(ref, str):
                continue
            try:
                resolver(ref, layout)
            except (FileNotFoundError, ValueError):
                continue
            link = ref_link(page_path, layout, ref, kind=kind)
            line_pattern_sub = re.compile(
                rf"^(\s*(?:[-*]\s*)?){prefix_name}:\s*\[{re.escape(ref)}\]\([^)]+\)\s*$",
                re.MULTILINE,
            )
            replacement = rf"\1{prefix_name}: {link}"
            updated, count = line_pattern_sub.subn(replacement, new_text)
            if count:
                new_text = updated
                changes += count

    return new_text, changes


def copy_local_knowledge(local_root: Path, external_root: Path) -> None:
    ensure_knowledge_structure(external_root)
    for item in local_root.iterdir():
        if item.name == "SCHEMA.md":
            continue
        destination = external_root / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def migrate_local_to_external(repo_root: Path, external_root: Path, *, remove_local: bool = False) -> int:
    repo_root = repo_root.resolve()
    external_root = external_root.expanduser().resolve()
    local_root = local_knowledge_dir(repo_root)

    if not has_local_knowledge(repo_root):
        print(f"[ERROR] local knowledge not found or empty: {local_root}")
        return 1

    copy_local_knowledge(local_root, external_root)
    write_knowledge_config(repo_root, external_root)

    layout = resolve_knowledge_layout(repo_root, external_root)
    wiki_root = layout.wiki_root
    if not wiki_root.is_dir():
        print(f"[ERROR] wiki root missing after copy: {wiki_root}")
        return 1

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    normalized_pages = 0
    relinked_pages = 0
    migrated_pages = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        new_text, norm_changes = normalize_page_text(text)
        if norm_changes:
            page.write_text(new_text, encoding="utf-8")
            normalized_pages += 1
        new_text, relink_changes = relink_page_content(page.read_text(encoding="utf-8"), page, layout)
        if relink_changes:
            page.write_text(new_text, encoding="utf-8")
            relinked_pages += 1
        new_text, mig_changes = migrate_page(page, layout)
        if mig_changes:
            page.write_text(new_text, encoding="utf-8")
            migrated_pages += 1

    if remove_local:
        shutil.rmtree(local_root)
        print(f"[OK] removed local knowledge directory: {local_root}")

    print(f"[OK] migrated local knowledge to {external_root}")
    print(f"[OK] wrote {repo_root / 'knowledge.md'}")
    print(f"[OK] normalized {normalized_pages} page(s), relinked {relinked_pages} page(s), migrated links on {migrated_pages} page(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local knowledge/ to an external knowledge root")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        required=True,
        help="External knowledge root absolute path (required; created if missing).",
    )
    parser.add_argument(
        "--remove-local",
        action="store_true",
        help="Delete {repo_root}/knowledge/ after successful migration (use only when user confirms).",
    )
    args = parser.parse_args()
    return migrate_local_to_external(args.repo_root.resolve(), args.knowledge_root, remove_local=args.remove_local)


if __name__ == "__main__":
    sys.exit(main())
