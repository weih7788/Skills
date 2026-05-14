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


def ensure_knowledge_structure(repo_root: Path) -> None:
    knowledge_root = repo_root / "knowledge"
    wiki_root = knowledge_root / "wiki"
    raw_root = knowledge_root / "raw"

    for directory in (
        knowledge_root,
        wiki_root,
        raw_root,
        *(wiki_root / dirname for dirname in TYPE_TO_DIR.values()),
    ):
        directory.mkdir(parents=True, exist_ok=True)

    write_if_missing(
        knowledge_root / "README.md",
        """# Project Knowledge

This directory contains the project-local LLM wiki.

- `wiki/`: curated project knowledge pages
- `raw/`: index of source artifacts used by the wiki
""",
    )
    write_if_missing(
        knowledge_root / "SCHEMA.md",
        """# Knowledge Schema

Wiki pages use YAML front matter with these required keys:

- `title`
- `type`
- `status`
- `owner`
- `last_verified_at`
- `source_refs`
- `related_pages`

`source_refs` and `related_pages` must use paths relative to the project root.
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


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug


def build_content(page_type: str, title: str, owner: str, status: str) -> str:
    today = dt.date.today().isoformat()
    sections = TYPE_TO_SECTIONS[page_type]
    section_text = "\n\n".join(f"## {section}\n" for section in sections)
    return f"""---
title: {title}
type: {page_type}
status: {status}
owner: {owner}
last_verified_at: {today}
source_refs:
related_pages:
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
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    ensure_knowledge_structure(repo_root)
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

    target_file.write_text(build_content(args.page_type, args.title, args.owner, args.status), encoding="utf-8")
    print(f"[OK] created {target_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
