"""Metadata parsing helpers for knowledge wiki markdown pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - keeps the tools usable in minimal Python environments.
    yaml = None


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "[]":
        return []
    if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    return value.strip("\"'")


def parse_front_matter_fallback(raw_yaml: str, path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in raw_yaml.splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("  - "):
            if current_list_key is None:
                raise ValueError(f"{path}: list item without a parent key")
            data.setdefault(current_list_key, [])
            if not isinstance(data[current_list_key], list):
                raise ValueError(f"{path}: mixed scalar/list front matter for {current_list_key}")
            data[current_list_key].append(parse_scalar(raw_line[4:]))
            continue
        if ":" not in raw_line:
            raise ValueError(f"{path}: invalid front matter line: {raw_line}")

        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = parse_scalar(value)
            current_list_key = None
        else:
            data[key] = []
            current_list_key = key

    return data


def parse_front_matter(text: str, path: Path) -> dict[str, Any]:
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

    raw_yaml = "\n".join(lines[1:end_index])
    if yaml is None:
        data = parse_front_matter_fallback(raw_yaml, path)
    else:
        try:
            data = yaml.safe_load(raw_yaml) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"{path}: invalid YAML front matter: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path}: YAML front matter must be a mapping")
    return data


def read_front_matter(path: Path) -> dict[str, Any]:
    return parse_front_matter(path.read_text(encoding="utf-8"), path)
