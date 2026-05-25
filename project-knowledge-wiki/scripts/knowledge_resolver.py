"""Resolve repo root and external/local knowledge root from knowledge.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from knowledge_metadata import parse_front_matter, parse_front_matter_fallback

KNOWLEDGE_CONFIG_FILE = "knowledge.md"
KNOWLEDGE_ROOT_KEY = "knowledge_root"
PROJECT_ROOT_KEY = "project_root"
PROJECT_KEY_KEY = "project_key"
PLAIN_LINE = re.compile(r"^\s*({keys})\s*[:=]\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class KnowledgeLayout:
    repo_root: Path
    knowledge_root: Path
    project_root: Path
    project_key: str

    @property
    def wiki_root(self) -> Path:
        return self.knowledge_root / "wiki"

    @property
    def raw_root(self) -> Path:
        return self.knowledge_root / "raw"

    @property
    def is_external(self) -> bool:
        return self.knowledge_root.resolve() != (self.repo_root / "knowledge").resolve()


def default_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if (path / ".git").exists():
            return path
    return cwd


def _raw_config_value(data: dict[str, object], text: str, key: str) -> str | None:
    raw_value = data.get(key)
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value.strip()

    pattern = re.compile(PLAIN_LINE.pattern.format(keys=re.escape(key)), re.MULTILINE)
    match = pattern.search(text)
    if match:
        return match.group(2).strip().strip("\"'")

    return None


def _path_config_value(data: dict[str, object], text: str, key: str) -> Path | None:
    raw_value = _raw_config_value(data, text, key)
    if raw_value:
        return Path(raw_value).expanduser().resolve()
    return None


def _default_project_key(project_root: Path) -> str:
    return project_root.resolve().name


def _parse_config_text(text: str, path: Path) -> dict[str, Path | str]:
    stripped = text.strip()
    if not stripped:
        return {}

    data: dict[str, object]
    if stripped.startswith("---"):
        try:
            data = parse_front_matter(text if text.endswith("\n") else text + "\n", path)
        except ValueError:
            data = {}
    else:
        data = parse_front_matter_fallback(stripped, path)

    parsed = {}
    for key in (KNOWLEDGE_ROOT_KEY, PROJECT_ROOT_KEY):
        value = _path_config_value(data, text, key)
        if value is not None:
            parsed[key] = value
    project_key = _raw_config_value(data, text, PROJECT_KEY_KEY)
    if project_key:
        parsed[PROJECT_KEY_KEY] = project_key
    return parsed


def parse_knowledge_config(repo_root: Path) -> dict[str, Path | str]:
    config_path = repo_root / KNOWLEDGE_CONFIG_FILE
    if not config_path.is_file():
        return {}
    return _parse_config_text(config_path.read_text(encoding="utf-8"), config_path)


def resolve_knowledge_layout(
    repo_root: Path | None = None,
    knowledge_root: Path | None = None,
) -> KnowledgeLayout:
    resolved_repo = (repo_root or default_repo_root()).resolve()
    configured = parse_knowledge_config(resolved_repo)
    configured_project_root = configured.get(PROJECT_ROOT_KEY)
    project_root = configured_project_root if isinstance(configured_project_root, Path) else resolved_repo
    configured_project_key = configured.get(PROJECT_KEY_KEY)
    project_key = str(configured_project_key) if configured_project_key else _default_project_key(project_root)

    if knowledge_root is not None:
        return KnowledgeLayout(resolved_repo, knowledge_root.expanduser().resolve(), project_root, project_key)

    configured_knowledge_root = configured.get(KNOWLEDGE_ROOT_KEY)
    if isinstance(configured_knowledge_root, Path):
        return KnowledgeLayout(resolved_repo, configured_knowledge_root, project_root, project_key)

    return KnowledgeLayout(resolved_repo, resolved_repo / "knowledge", project_root, project_key)


def local_knowledge_dir(repo_root: Path) -> Path:
    return repo_root.resolve() / "knowledge"


def knowledge_config_path(repo_root: Path) -> Path:
    return repo_root.resolve() / KNOWLEDGE_CONFIG_FILE


def has_local_knowledge(repo_root: Path) -> bool:
    """Return True when {repo_root}/knowledge/ has been bootstrapped or contains wiki content."""
    local = local_knowledge_dir(repo_root)
    if not local.is_dir():
        return False
    wiki = local / "wiki"
    if not wiki.is_dir():
        return False
    return (local / "README.md").is_file() or any(path.name != "README.md" for path in wiki.rglob("*.md"))


def is_knowledge_initialized(layout: KnowledgeLayout) -> bool:
    """Return True when the resolved knowledge_root exists and has minimal structure."""
    root = layout.knowledge_root
    if not root.is_dir():
        return False
    return (root / "wiki").is_dir()


def write_knowledge_config(repo_root: Path, knowledge_root: Path) -> Path:
    config_path = knowledge_config_path(repo_root)
    resolved_repo = repo_root.resolve()
    config_path.write_text(
        f"{KNOWLEDGE_ROOT_KEY}: {knowledge_root.resolve().as_posix()}\n"
        f"{PROJECT_ROOT_KEY}: {resolved_repo.as_posix()}\n"
        f"{PROJECT_KEY_KEY}: {_default_project_key(resolved_repo)}\n",
        encoding="utf-8",
    )
    return config_path


def is_external_path_configured(repo_root: Path, explicit_knowledge_root: Path | None = None) -> bool:
    """Return True when external knowledge_root is explicitly known (CLI arg or knowledge.md)."""
    if explicit_knowledge_root is not None:
        return True
    return KNOWLEDGE_ROOT_KEY in parse_knowledge_config(repo_root.resolve())
