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


TYPE_TO_DIR = {
    "domain": "domains",
    "concept": "concepts",
    "flow": "flows",
    "integration": "integrations",
    "data-model": "data-models",
    "runbook": "runbooks",
    "decision": "decisions",
}

TYPE_TO_SECTIONS = {
    "domain": ["这是什么", "核心对象", "核心入口", "关键流程", "边界与例外", "风险与待确认项", "Sources"],
    "concept": ["定义", "使用位置", "关键约束", "常见误解", "风险与待确认项", "Sources"],
    "flow": ["触发条件", "流程步骤", "关键落库/调用点", "异常与回退", "Sources"],
    "integration": ["这是什么", "关键依赖", "调用方式", "异常点", "Sources"],
    "data-model": ["定义", "关键字段", "关联关系", "边界与例外", "Sources"],
    "runbook": ["何时执行", "执行步骤", "校验方式", "常见失败点", "Sources"],
    "decision": ["背景", "决策", "原因", "结果", "不做什么", "Sources"],
}


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def is_repo_relative(raw_path: str) -> bool:
    if not raw_path:
        return False
    path = Path(raw_path)
    if path.is_absolute():
        return False
    return not (raw_path.startswith("./") or raw_path.startswith("../") or raw_path.startswith("/"))


def yaml_list(values: list[str]) -> str:
    if not values:
        return ""
    return "\n".join(f"  - {value}" for value in values)


def build_content(
    page_type: str,
    title: str,
    owner: str,
    status: str,
    source_refs: list[str],
    related_pages: list[str],
) -> str:
    today = dt.date.today().isoformat()
    sections = TYPE_TO_SECTIONS[page_type]
    section_text = "\n\n".join(f"## {section}\n" for section in sections)
    source_ref_text = yaml_list(source_refs)
    related_page_text = yaml_list(related_pages)
    return f"""---
title: {title}
type: {page_type}
status: {status}
owner: {owner}
last_verified_at: {today}
source_refs:
{source_ref_text}
related_pages:
{related_page_text}
---

{section_text}
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
        help="Repo-root relative source path. Repeat for multiple sources.",
    )
    parser.add_argument(
        "--related-page",
        action="append",
        default=[],
        help="Repo-root relative related wiki page path. Repeat for multiple pages.",
    )
    parser.add_argument(
        "--allow-empty-source-refs",
        action="store_true",
        help="Create a draft without source_refs. The page will not pass lint until sources are added.",
    )
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    ensure_knowledge_structure(repo_root)

    if not args.source_ref and not args.allow_empty_source_refs:
        print("[ERROR] at least one --source-ref is required; use --allow-empty-source-refs for scratch drafts")
        return 1

    for field_name, values in (("--source-ref", args.source_ref), ("--related-page", args.related_page)):
        for value in values:
            if not is_repo_relative(value):
                print(f"[ERROR] {field_name} must be repo-root relative without ./ or ../: {value}")
                return 1
            if not (repo_root / value).exists():
                print(f"[ERROR] {field_name} path does not exist: {value}")
                return 1

    slug = args.slug or slugify(args.title)
    if not slug:
        print("[ERROR] failed to build slug")
        return 1

    target_dir = repo_root / "knowledge" / "wiki" / TYPE_TO_DIR[args.page_type]
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{slug}.md"

    if target_file.exists():
        print(f"[ERROR] page already exists: {target_file}")
        return 1

    target_file.write_text(
        build_content(args.page_type, args.title, args.owner, args.status, args.source_ref, args.related_page),
        encoding="utf-8",
    )
    print(f"[OK] created {target_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
