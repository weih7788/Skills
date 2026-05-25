#!/usr/bin/env python3
"""
Create a new knowledge wiki page from a simple template.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure
from knowledge_config import TYPE_TO_DIR, TYPE_TO_SECTIONS
from knowledge_links import is_repo_relative, ref_link, resolve_related_ref, resolve_source_ref
from knowledge_resolver import default_repo_root, resolve_knowledge_layout


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "\n" + "\n".join(f"  - {value}" for value in values)


def yaml_list_field(key: str, values: list[str]) -> str:
    rendered = yaml_list(values)
    if rendered.startswith("\n"):
        return f"{key}:{rendered}"
    return f"{key}: {rendered}"


def source_section(page_path: Path, layout, source_refs: list[str]) -> str:
    if not source_refs:
        return ""
    links = "\n".join(f"- Source: {ref_link(page_path, layout, source_ref, kind='source')}" for source_ref in source_refs)
    return f"\n{links}"


def related_pages_section(page_path: Path, layout, related_pages: list[str]) -> str:
    if not related_pages:
        return ""
    links = "\n".join(f"- Ref: {ref_link(page_path, layout, related_page, kind='related')}" for related_page in related_pages)
    return f"\n\n## Related Pages\n\n{links}"


def build_content(
    page_path: Path,
    layout,
    page_type: str,
    title: str,
    owner: str,
    status: str,
    source_refs: list[str],
    related_pages: list[str],
) -> str:
    today = dt.date.today().isoformat()
    sections = TYPE_TO_SECTIONS[page_type]
    rendered_sections = []
    for section in sections:
        body = source_section(page_path, layout, source_refs) if section == "Sources" else ""
        rendered_sections.append(f"## {section}\n{body}")
    section_text = "\n\n".join(rendered_sections)
    related_pages_text = related_pages_section(page_path, layout, related_pages)
    source_ref_text = yaml_list_field("source_refs", source_refs)
    related_page_front_matter = yaml_list_field("related_pages", related_pages)
    return f"""---
title: {title}
type: {page_type}
status: {status}
owner: {owner}
last_verified_at: {today}
{source_ref_text}
{related_page_front_matter}
---

{section_text}
{related_pages_text}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new knowledge wiki page")
    parser.add_argument("page_type", choices=sorted(TYPE_TO_DIR.keys()))
    parser.add_argument("title")
    parser.add_argument("--slug")
    parser.add_argument("--owner", default="engineering")
    parser.add_argument("--status", choices=["draft", "reviewed", "canonical"], default="draft")
    parser.add_argument(
        "--source-ref",
        action="append",
        default=[],
        help="Relative source path (project repo or knowledge wiki). Repeat for multiple sources.",
    )
    parser.add_argument(
        "--related-page",
        action="append",
        default=[],
        help="Relative related wiki page path. Repeat for multiple pages.",
    )
    parser.add_argument(
        "--allow-empty-source-refs",
        action="store_true",
        help="Create a draft without source_refs. The page will not pass lint until sources are added.",
    )
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

    if not args.source_ref and not args.allow_empty_source_refs:
        print("[ERROR] at least one --source-ref is required; use --allow-empty-source-refs for scratch drafts")
        return 1

    for field_name, values, resolver in (
        ("--source-ref", args.source_ref, resolve_source_ref),
        ("--related-page", args.related_page, resolve_related_ref),
    ):
        for value in values:
            if not is_repo_relative(value):
                print(f"[ERROR] {field_name} must be relative without ./ or ../: {value}")
                return 1
            try:
                resolver(value, layout)
            except FileNotFoundError:
                print(f"[ERROR] {field_name} path does not exist: {value}")
                return 1
            except ValueError as exc:
                print(f"[ERROR] {field_name} invalid path: {exc}")
                return 1

    slug = args.slug or slugify(args.title)
    if not slug:
        print("[ERROR] failed to build slug")
        return 1

    target_dir = layout.wiki_root / TYPE_TO_DIR[args.page_type]
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{slug}.md"

    if target_file.exists():
        print(f"[ERROR] page already exists: {target_file}")
        return 1

    target_file.write_text(
        build_content(
            target_file,
            layout,
            args.page_type,
            args.title,
            args.owner,
            args.status,
            args.source_ref,
            args.related_page,
        ),
        encoding="utf-8",
    )
    print(f"[OK] created {target_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
