#!/usr/bin/env python3
"""
Validate the knowledge wiki (local or external knowledge root).

Checks:
- front matter presence
- required metadata keys
- allowed type/status values
- source_refs and related_pages resolve against repo_root or knowledge_root
- body links exist for every source_refs and related_pages item
- markdown link labels match resolved ref paths
- Source: lines start with a markdown link
- referenced files/directories exist
- external raw/README.md uses absolute project paths (not ../ relative targets)
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
    ForeignProjectRef,
    collect_valid_body_links,
    is_current_project_source_ref,
    is_repo_relative,
    markdown_links,
    normalize_markdown_link_target,
    resolve_related_ref,
    resolve_source_ref,
    validate_ref_lines,
    validate_source_lines,
)
from knowledge_metadata import parse_front_matter
from knowledge_resolver import KnowledgeLayout, default_repo_root, resolve_knowledge_layout


REQUIRED_KEYS = {
    "title",
    "type",
    "status",
    "owner",
    "last_verified_at",
    "source_refs",
    "related_pages",
}


def page_has_current_project_source(front_matter: dict[str, object], layout: KnowledgeLayout) -> bool:
    """External shared wiki lint only owns pages that reference the current project."""
    if not layout.is_external:
        return True
    source_refs = front_matter.get("source_refs")
    if not isinstance(source_refs, list):
        return True
    return any(isinstance(item, str) and is_current_project_source_ref(item, layout) for item in source_refs)


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def validate_page(
    page_path: Path,
    layout: KnowledgeLayout,
    max_age_days: int,
    fail_on_stale: bool,
) -> tuple[list[str], list[str], bool]:
    errors: list[str] = []
    warnings: list[str] = []
    text = page_path.read_text(encoding="utf-8")

    try:
        front_matter = parse_front_matter(text, page_path)
    except ValueError as exc:
        return [str(exc)], warnings, True

    missing = sorted(REQUIRED_KEYS - set(front_matter.keys()))
    if missing:
        errors.append(f"{page_path}: missing keys: {', '.join(missing)}")
        return errors, warnings, True

    if not page_has_current_project_source(front_matter, layout):
        return errors, warnings, False

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

    source_refs = string_list(front_matter.get("source_refs"))
    related_pages = string_list(front_matter.get("related_pages"))
    required_labels = set(source_refs + related_pages)
    body_links, link_errors = collect_valid_body_links(
        text,
        page_path,
        layout,
        required_labels=required_labels,
    )
    errors.extend(link_errors)

    for field_name, resolver in (("source_refs", resolve_source_ref), ("related_pages", resolve_related_ref)):
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
                errors.append(f"{page_path}: {field_name} contains invalid relative path '{item}'")
                continue
            try:
                resolved_ref = resolver(item, layout)
            except ForeignProjectRef:
                if field_name != "source_refs":
                    errors.append(f"{page_path}: {field_name} cannot point to foreign project source '{item}'")
                    continue
                continue
            except FileNotFoundError:
                if layout.is_external and field_name == "source_refs":
                    continue
                errors.append(f"{page_path}: {field_name} path does not exist '{item}'")
                continue
            except ValueError as exc:
                errors.append(f"{page_path}: {field_name} invalid path '{item}': {exc}")
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

    return errors, warnings, True


def validate_raw_index(layout: KnowledgeLayout) -> list[str]:
    """External-mode raw/README.md must use absolute project paths, not ../ relative targets."""
    errors: list[str] = []
    raw_index = layout.raw_root / "README.md"
    if not layout.is_external or not raw_index.is_file():
        return errors

    text = raw_index.read_text(encoding="utf-8")
    errors.extend(validate_source_lines(text, raw_index))

    _, link_errors = collect_valid_body_links(
        text,
        raw_index,
        layout,
        current_project_only=True,
        required_labels={
            label
            for label, _target in markdown_links(text)
            if is_current_project_source_ref(label, layout)
        },
    )
    errors.extend(link_errors)

    for label, target in markdown_links(text):
        if not is_current_project_source_ref(label, layout):
            continue
        normalized = normalize_markdown_link_target(target)
        if not normalized:
            continue
        if normalized.startswith("../") or normalized.startswith("./"):
            errors.append(
                f"{raw_index}: external raw index must use absolute project paths in link targets, "
                f"not relative paths like '{target}'; run refresh_indexes.py to regenerate"
            )
        elif not Path(normalized).is_absolute():
            errors.append(
                f"{raw_index}: external raw index link target must be an absolute path, got '{target}'; "
                f"run refresh_indexes.py to regenerate"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge wiki")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--knowledge-root",
        type=Path,
        default=None,
        help="Explicit knowledge root. Defaults to knowledge.md config or repo_root/knowledge.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create the minimal knowledge structure before linting if it is missing.",
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

    layout = resolve_knowledge_layout(args.repo_root.resolve(), args.knowledge_root)
    if args.bootstrap:
        ensure_knowledge_structure(layout.knowledge_root)

    if not layout.knowledge_root.exists():
        print(f"[ERROR] knowledge root not found: {layout.knowledge_root}")
        if layout.is_external:
            print(f"[HINT] provide --knowledge-root or configure {layout.repo_root / 'knowledge.md'}, then re-run with --bootstrap")
        else:
            print("[HINT] run knowledge_bootstrap.py or pass --bootstrap to create the minimal structure")
        return 1

    wiki_root = layout.wiki_root
    if not wiki_root.exists():
        print(f"[ERROR] wiki root not found: {wiki_root}")
        return 1

    pages = sorted(path for path in wiki_root.rglob("*.md") if path.name != "README.md")
    all_errors: list[str] = []
    all_warnings: list[str] = []
    checked_pages = 0
    skipped_pages = 0

    knowledge_scripts = layout.knowledge_root / "scripts"
    if knowledge_scripts.exists():
        all_warnings.append(
            f"{knowledge_scripts} should not exist; keep maintenance scripts in the skill, not in knowledge/"
        )

    for page in pages:
        errors, warnings, checked = validate_page(page, layout, args.max_age_days, not args.allow_stale)
        if checked:
            checked_pages += 1
        else:
            skipped_pages += 1
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    all_errors.extend(validate_raw_index(layout))

    if all_errors:
        for error in all_errors:
            print(f"[ERROR] {error}")
        for warning in all_warnings:
            print(f"[WARN] {warning}")
        print(f"[FAIL] knowledge lint found {len(all_errors)} issue(s)")
        return 1

    for warning in all_warnings:
        print(f"[WARN] {warning}")
    mode = "external" if layout.is_external else "local"
    skipped_text = f", skipped {skipped_pages} foreign page(s)" if skipped_pages else ""
    print(
        f"[OK] knowledge lint passed for {checked_pages} checked page(s)"
        f"{skipped_text} ({mode}, root={layout.knowledge_root})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
