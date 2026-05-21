"""Shared helpers for knowledge wiki markdown source links."""

from __future__ import annotations

import os
import re
from pathlib import Path

SOURCE_LINE = re.compile(r"^(\s*(?:[-*]\s*)?)Source:\s*(.+)$", re.MULTILINE)
REF_LINE = re.compile(r"^(\s*(?:[-*]\s*)?)Ref:\s*(.+)$", re.MULTILINE)
MARKDOWN_LINK_PREFIX = re.compile(r"^\[[^\]]+\]\([^)]+\)")
MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")


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
    return [(match.group(1), match.group(2)) for match in MARKDOWN_LINK.finditer(text)]


def resolve_markdown_link(page_path: Path, target: str) -> Path:
    return (page_path.parent / target).resolve()


def resolve_repo_ref(repo_root: Path, repo_ref: str) -> Path:
    return (repo_root / repo_ref).resolve()


def to_repo_ref(repo_root: Path, resolved: Path) -> str:
    return resolved.relative_to(repo_root).as_posix()


def repo_ref_link(from_page: Path, repo_root: Path, repo_ref: str) -> str:
    target = os.path.relpath(repo_root / repo_ref, from_page.parent).replace(os.sep, "/")
    return f"[{repo_ref}]({target})"


def validate_link_label(label: str, resolved_target: Path, repo_root: Path) -> str | None:
    if not is_repo_relative(label):
        return f"markdown link label must be repo-root relative path, got '{label}'"
    try:
        label_resolved = resolve_repo_ref(repo_root, label)
    except ValueError:
        return f"markdown link label must be repo-root relative path, got '{label}'"
    if label_resolved != resolved_target:
        expected = to_repo_ref(repo_root, resolved_target)
        return f"markdown link label must be '{expected}', got '{label}'"
    return None


def collect_valid_body_links(
    text: str, page_path: Path, repo_root: Path
) -> tuple[dict[str, Path], list[str]]:
    """Return repo-root label -> resolved path for valid in-repo links, plus errors."""
    links: dict[str, Path] = {}
    errors: list[str] = []
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
        label_error = validate_link_label(label, resolved, repo_root)
        if label_error:
            errors.append(f"{page_path}: {label_error}")
            continue
        links[label] = resolved
    return links, errors


def validate_prefixed_lines(
    text: str,
    page_path: Path,
    line_pattern: re.Pattern[str],
    prefix_name: str,
) -> list[str]:
    errors: list[str] = []
    for match in line_pattern.finditer(text):
        content = match.group(2).strip()
        if not MARKDOWN_LINK_PREFIX.match(content):
            errors.append(
                f"{page_path}: {prefix_name} line must start with a markdown link, got '{content}'"
            )
    return errors


def validate_source_lines(text: str, page_path: Path) -> list[str]:
    return validate_prefixed_lines(text, page_path, SOURCE_LINE, "Source")


def validate_ref_lines(text: str, page_path: Path) -> list[str]:
    return validate_prefixed_lines(text, page_path, REF_LINE, "Ref")
