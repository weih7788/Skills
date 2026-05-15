#!/usr/bin/env python3
"""
Validate the repo-local knowledge wiki.

Checks:
- front matter presence
- required metadata keys
- allowed type/status values
- repo-root relative source_refs and related_pages
- referenced files/directories exist
- last_verified_at format
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path


ALLOWED_TYPES = {"domain", "concept", "flow", "integration", "data-model", "runbook", "decision"}
ALLOWED_STATUS = {"draft", "reviewed", "canonical"}
REQUIRED_KEYS = {
    "title",
    "type",
    "status",
    "owner",
    "last_verified_at",
    "source_refs",
    "related_pages",
}

WIKI_DIRS = ("domains", "concepts", "flows", "integrations", "data-models", "runbooks", "decisions")


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


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


def parse_front_matter(text: str, path: Path) -> dict[str, object]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing YAML front matter")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValueError(f"{path}: unterminated YAML front matter")

    data: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in lines[1:end_index]:
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - "):
            if current_list_key is None:
                raise ValueError(f"{path}: list item without a parent key")
            data.setdefault(current_list_key, [])
            assert isinstance(data[current_list_key], list)
            data[current_list_key].append(raw_line[4:].strip())
            continue
        if ":" not in raw_line:
            raise ValueError(f"{path}: invalid front matter line: {raw_line}")

        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = value
            current_list_key = None
        else:
            data[key] = []
            current_list_key = key

    return data


def is_repo_relative(raw_path: str) -> bool:
    if not raw_path:
        return False
    path = Path(raw_path)
    if path.is_absolute():
        return False
    if raw_path.startswith("./") or raw_path.startswith("../") or raw_path.startswith("/"):
        return False
    return True


def is_external_link(target: str) -> bool:
    return (
        "://" in target
        or target.startswith("#")
        or target.startswith("mailto:")
        or target.startswith("tel:")
    )


def normalize_markdown_link_target(target: str) -> str:
    target = target.strip().strip("<>")
    if "#" in target:
        target = target.split("#", 1)[0]
    return target


def markdown_links(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
    return [(match.group(1), match.group(2)) for match in pattern.finditer(text)]


def resolve_markdown_link(page_path: Path, target: str) -> Path:
    return (page_path.parent / target).resolve()


def is_path_like_label(label: str) -> bool:
    return "/" in label or bool(Path(label).suffix)


def validate_page(page_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    text = page_path.read_text(encoding="utf-8")

    try:
        front_matter = parse_front_matter(text, page_path)
    except ValueError as exc:
        return [str(exc)]

    missing = sorted(REQUIRED_KEYS - set(front_matter.keys()))
    if missing:
        errors.append(f"{page_path}: missing keys: {', '.join(missing)}")
        return errors

    page_type = str(front_matter["type"])
    if page_type not in ALLOWED_TYPES:
        errors.append(f"{page_path}: invalid type '{page_type}'")

    status = str(front_matter["status"])
    if status not in ALLOWED_STATUS:
        errors.append(f"{page_path}: invalid status '{status}'")

    last_verified_at = str(front_matter["last_verified_at"])
    try:
        dt.datetime.strptime(last_verified_at, "%Y-%m-%d")
    except ValueError:
        errors.append(f"{page_path}: invalid last_verified_at '{last_verified_at}'")

    for field_name in ("source_refs", "related_pages"):
        value = front_matter[field_name]
        if not isinstance(value, list):
            errors.append(f"{page_path}: {field_name} must be a list")
            continue
        if field_name == "source_refs" and not value:
            errors.append(f"{page_path}: source_refs must not be empty")
        for item in value:
            if not is_repo_relative(item):
                errors.append(f"{page_path}: {field_name} contains non repo-relative path '{item}'")
                continue
            if not (repo_root / item).exists():
                errors.append(f"{page_path}: {field_name} path does not exist '{item}'")

    for label, target in markdown_links(text):
        normalized = normalize_markdown_link_target(target)
        if not normalized or is_external_link(normalized):
            continue
        if Path(normalized).is_absolute():
            errors.append(f"{page_path}: markdown link target must not be absolute '{target}'")
            continue
        resolved = resolve_markdown_link(page_path, normalized)
        if not resolved.exists():
            errors.append(f"{page_path}: markdown link target path does not exist '{target}'")
            continue
        try:
            repo_relative_target = resolved.relative_to(repo_root).as_posix()
        except ValueError:
            errors.append(f"{page_path}: markdown link target escapes repo root '{target}'")
            continue
        if is_path_like_label(label) and (not is_repo_relative(label) or label != repo_relative_target):
            errors.append(f"{page_path}: markdown link label must be project-relative '{label}'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge wiki")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    ensure_knowledge_structure(repo_root)
    wiki_root = repo_root / "knowledge" / "wiki"

    if not wiki_root.exists():
        print(f"[ERROR] wiki root not found: {wiki_root}")
        return 1

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    all_errors: list[str] = []

    for page in pages:
        all_errors.extend(validate_page(page, repo_root))

    if all_errors:
        for error in all_errors:
            print(f"[ERROR] {error}")
        print(f"[FAIL] knowledge lint found {len(all_errors)} issue(s)")
        return 1

    print(f"[OK] knowledge lint passed for {len(pages)} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
