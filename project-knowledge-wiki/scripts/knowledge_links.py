"""Shared helpers for knowledge wiki markdown source links."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

from knowledge_resolver import KnowledgeLayout

SOURCE_LINE = re.compile(r"^(\s*(?:[-*]\s*)?)Source:\s*(.+)$", re.MULTILINE)
REF_LINE = re.compile(r"^(\s*(?:[-*]\s*)?)Ref:\s*(.+)$", re.MULTILINE)
MARKDOWN_LINK_PREFIX = re.compile(r"^\[[^\]]+\]\([^)]+\)")
MARKDOWN_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\((<[^>]+>|[^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
PROJECT_REF = re.compile(r"^([A-Za-z0-9_.-]+):(.+)$")


class ForeignProjectRef(ValueError):
    """Raised when a source ref belongs to another project in a shared knowledge root."""

    def __init__(self, project_key: str, ref_path: str) -> None:
        super().__init__(f"source ref belongs to foreign project '{project_key}': {ref_path}")
        self.project_key = project_key
        self.ref_path = ref_path


def is_repo_relative(raw_path: str) -> bool:
    if not raw_path:
        return False
    path = Path(raw_path)
    if path.is_absolute():
        return False
    if raw_path.startswith("./") or raw_path.startswith("../") or raw_path.startswith("/"):
        return False
    return True


def split_project_ref(raw_path: str) -> tuple[str | None, str]:
    match = PROJECT_REF.match(raw_path)
    if not match:
        return None, raw_path
    return match.group(1), match.group(2)


def is_foreign_source_ref(raw_path: str, layout: KnowledgeLayout) -> bool:
    project_key, _ref_path = split_project_ref(raw_path)
    return project_key is not None and project_key != layout.project_key


def is_current_project_source_ref(raw_path: str, layout: KnowledgeLayout) -> bool:
    """Return True when a source ref is explicitly or implicitly owned by the current project."""
    project_key, ref_path = split_project_ref(raw_path)
    if project_key is not None:
        return project_key == layout.project_key
    return (layout.project_root / ref_path).exists()


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
    return unquote(target)


def markdown_links(text: str) -> list[tuple[str, str]]:
    return [(match.group(1), match.group(2)) for match in MARKDOWN_LINK.finditer(text)]


def resolve_markdown_link(page_path: Path, target: str) -> Path:
    return (page_path.parent / target).resolve()


def resolve_source_ref(ref: str, layout: KnowledgeLayout) -> Path:
    if not is_repo_relative(ref):
        raise ValueError(f"ref must be a relative path without ./ or ../: {ref}")

    project_key, ref_path = split_project_ref(ref)
    if project_key is not None and project_key != layout.project_key:
        raise ForeignProjectRef(project_key, ref_path)
    if not is_repo_relative(ref_path):
        raise ValueError(f"ref must be a relative path without ./ or ../: {ref}")

    candidate = layout.project_root / ref_path
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(ref)


def resolve_related_ref(ref: str, layout: KnowledgeLayout) -> Path:
    if not is_repo_relative(ref):
        raise ValueError(f"ref must be a relative path without ./ or ../: {ref}")

    candidates: list[Path]
    if ref.startswith("knowledge/wiki/"):
        candidates = [layout.knowledge_root / ref[len("knowledge/") :], layout.repo_root / ref]
    elif ref.startswith("wiki/"):
        candidates = [layout.knowledge_root / ref, layout.repo_root / "knowledge" / ref]
    else:
        candidates = [layout.knowledge_root / ref, layout.repo_root / ref]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(ref)


def resolve_knowledge_ref(ref: str, layout: KnowledgeLayout) -> Path:
    """Resolve a legacy untyped ref, preferring project sources before wiki refs."""
    try:
        return resolve_source_ref(ref, layout)
    except FileNotFoundError:
        return resolve_related_ref(ref, layout)


def to_ref_label(resolved: Path, layout: KnowledgeLayout) -> str:
    resolved = resolved.resolve()
    try:
        rel_repo = resolved.relative_to(layout.repo_root.resolve()).as_posix()
        if (layout.repo_root / rel_repo).resolve() == resolved:
            return rel_repo
    except ValueError:
        pass

    rel_knowledge = resolved.relative_to(layout.knowledge_root.resolve()).as_posix()
    if layout.is_external and rel_knowledge.startswith("wiki/"):
        return rel_knowledge
    if not layout.is_external:
        return f"knowledge/{rel_knowledge}"
    return rel_knowledge


def markdown_target(from_page: Path, resolved: Path, *, absolute: bool = False) -> str:
    if absolute:
        target = resolved.as_posix()
        return f"<{target}>"
    target = os.path.relpath(resolved, from_page.parent).replace(os.sep, "/")
    if any(char.isspace() for char in target):
        return f"<{target}>"
    return target


def ref_link(from_page: Path, layout: KnowledgeLayout, ref: str, *, kind: str = "auto") -> str:
    if kind == "source":
        resolved = resolve_source_ref(ref, layout)
        return f"[{ref}]({markdown_target(from_page, resolved, absolute=layout.is_external)})"
    elif kind == "related":
        resolved = resolve_related_ref(ref, layout)
    else:
        resolved = resolve_knowledge_ref(ref, layout)
    return f"[{ref}]({markdown_target(from_page, resolved)})"


def repo_ref_link(from_page: Path, repo_root: Path, repo_ref: str) -> str:
    """Backward-compatible wrapper for in-repo knowledge layout."""
    resolved_repo = repo_root.resolve()
    layout = KnowledgeLayout(resolved_repo, resolved_repo / "knowledge", resolved_repo, resolved_repo.name)
    return ref_link(from_page, layout, repo_ref)


def validate_link_label(label: str, resolved_target: Path, layout: KnowledgeLayout) -> str | None:
    if not is_repo_relative(label):
        return f"markdown link label must be a relative path, got '{label}'"
    if is_foreign_source_ref(label, layout):
        return None
    try:
        label_resolved = resolve_knowledge_ref(label, layout)
    except (ValueError, FileNotFoundError):
        return f"markdown link label must resolve to an existing path, got '{label}'"
    if label_resolved != resolved_target.resolve():
        expected = to_ref_label(resolved_target, layout)
        return f"markdown link label must be '{expected}', got '{label}'"
    return None


def collect_valid_body_links(
    text: str,
    page_path: Path,
    layout: KnowledgeLayout,
    *,
    current_project_only: bool = False,
    required_labels: set[str] | None = None,
) -> tuple[dict[str, Path], list[str]]:
    """Return ref label -> resolved target for jumpable markdown links, plus target errors."""
    links: dict[str, Path] = {}
    errors: list[str] = []
    for label, target in markdown_links(text):
        if required_labels is not None and label not in required_labels:
            continue
        if current_project_only and not is_current_project_source_ref(label, layout):
            continue
        normalized = normalize_markdown_link_target(target)
        if not normalized or is_external_link(normalized):
            continue
        if Path(normalized).is_absolute():
            resolved = Path(normalized).resolve()
        else:
            resolved = resolve_markdown_link(page_path, normalized)
        if not resolved.exists():
            if is_foreign_source_ref(label, layout):
                continue
            errors.append(f"{page_path}: markdown link target path does not exist '{target}'")
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
