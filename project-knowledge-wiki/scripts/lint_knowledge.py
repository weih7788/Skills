#!/usr/bin/env python3
"""
Validate the repo-local knowledge wiki.

Checks:
- front matter presence
- required metadata keys
- allowed type/status values
- repo-root relative source_refs and related_pages
- body links exist for every source_refs and related_pages item
- markdown link labels match repo-root relative paths
- Source: lines start with a markdown link
- referenced files/directories exist
- last_verified_at format
- stale pages older than 30 days by default
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from knowledge_bootstrap import ensure_knowledge_structure
from knowledge_config import ALLOWED_STATUS, ALLOWED_TYPES, STALE_AFTER_DAYS
from knowledge_links import (
    collect_valid_body_links,
    is_repo_relative,
    resolve_repo_ref,
    validate_ref_lines,
    validate_source_lines,
)
from knowledge_metadata import parse_front_matter


REQUIRED_KEYS = {
    "title",
    "type",
    "status",
    "owner",
    "last_verified_at",
    "source_refs",
    "related_pages",
}


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


def validate_page(page_path: Path, repo_root: Path, max_age_days: int, fail_on_stale: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = page_path.read_text(encoding="utf-8")

    try:
        front_matter = parse_front_matter(text, page_path)
    except ValueError as exc:
        return [str(exc)], warnings

    missing = sorted(REQUIRED_KEYS - set(front_matter.keys()))
    if missing:
        errors.append(f"{page_path}: missing keys: {', '.join(missing)}")
        return errors, warnings

    page_type = str(front_matter["type"])
    if page_type not in ALLOWED_TYPES:
        errors.append(f"{page_path}: invalid type '{page_type}'")

    status = str(front_matter["status"])
    if status not in ALLOWED_STATUS:
        errors.append(f"{page_path}: invalid status '{status}'")

    last_verified_at = str(front_matter["last_verified_at"])
    try:
        verified_date = dt.datetime.strptime(last_verified_at, "%Y-%m-%d").date()
    except ValueError:
        errors.append(f"{page_path}: invalid last_verified_at '{last_verified_at}'")
    else:
        age_days = (dt.date.today() - verified_date).days
        if age_days < 0:
            errors.append(f"{page_path}: last_verified_at '{last_verified_at}' is in the future")
        elif age_days > max_age_days:
            message = (
                f"{page_path}: stale last_verified_at '{last_verified_at}' "
                f"({age_days} days old, max {max_age_days}); update it after wiki review"
            )
            if fail_on_stale:
                errors.append(message)
            else:
                warnings.append(message)

    errors.extend(validate_source_lines(text, page_path))
    errors.extend(validate_ref_lines(text, page_path))

    body_links, link_errors = collect_valid_body_links(text, page_path, repo_root)
    errors.extend(link_errors)

    for field_name in ("source_refs", "related_pages"):
        value = front_matter[field_name]
        if not isinstance(value, list):
            errors.append(f"{page_path}: {field_name} must be a list")
            continue
        if field_name == "source_refs" and not value:
            errors.append(f"{page_path}: source_refs must not be empty")
        for item in value:
            if not isinstance(item, str):
                errors.append(f"{page_path}: {field_name} item must be a string, got {item!r}")
                continue
            if not is_repo_relative(item):
                errors.append(f"{page_path}: {field_name} contains non repo-relative path '{item}'")
                continue
            resolved_ref = resolve_repo_ref(repo_root, item)
            if not resolved_ref.exists():
                errors.append(f"{page_path}: {field_name} path does not exist '{item}'")
                continue
            if item not in body_links:
                errors.append(
                    f"{page_path}: {field_name} item '{item}' must have a jumpable body markdown link "
                    f"with matching label '[{item}](...)'"
                )
            elif body_links[item] != resolved_ref:
                errors.append(
                    f"{page_path}: {field_name} item '{item}' has a body link label but target does not resolve correctly"
                )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge wiki")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the minimal knowledge/ structure before linting if it is missing.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=STALE_AFTER_DAYS,
        help="Fail pages whose last_verified_at is older than this many days.",
    )
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Report stale pages as warnings instead of lint errors.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if args.bootstrap:
        ensure_knowledge_structure(repo_root)

    knowledge_root = repo_root / "knowledge"
    if not knowledge_root.exists():
        print(f"[ERROR] knowledge root not found: {knowledge_root}")
        print("[HINT] run the skill's knowledge_bootstrap.py or pass --bootstrap to create the minimal structure")
        return 1

    wiki_root = repo_root / "knowledge" / "wiki"

    if not wiki_root.exists():
        print(f"[ERROR] wiki root not found: {wiki_root}")
        return 1

    knowledge_scripts = repo_root / "knowledge" / "scripts"
    if knowledge_scripts.exists():
        all_warnings.append(
            f"{knowledge_scripts} should not exist; keep maintenance scripts in the skill, not in knowledge/"
        )

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    all_errors: list[str] = []
    all_warnings: list[str] = []

    for page in pages:
        errors, warnings = validate_page(page, repo_root, args.max_age_days, not args.allow_stale)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    if all_errors:
        for error in all_errors:
            print(f"[ERROR] {error}")
        for warning in all_warnings:
            print(f"[WARN] {warning}")
        print(f"[FAIL] knowledge lint found {len(all_errors)} issue(s)")
        return 1

    for warning in all_warnings:
        print(f"[WARN] {warning}")
    print(f"[OK] knowledge lint passed for {len(pages)} page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
