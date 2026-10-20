#!/usr/bin/env python3
"""Fetch one Yunxiao iteration and its requirement/task tree via read-only OpenAPI."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = SKILL_ROOT / "config" / "yunxiao.json"
KEYCHAIN_SERVICE = "codex.release-checklist.yunxiao"
TOKEN_ENV_NAME = "YUNXIAO_PERSONAL_ACCESS_TOKEN"
DEFAULT_CATEGORIES = "Req,Task"
PAGE_SIZE = 200
MAX_PAGES = 50


class YunxiaoError(RuntimeError):
    """A safe-to-display Yunxiao API or resolution error."""


class _RichTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "blockquote",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")
        elif tag == "img":
            attributes = dict(attrs)
            name = str(attributes.get("name") or "未命名图片").strip()
            self.parts.append(f"\n[图片：{name}]\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        result: list[str] = []
        for line in lines:
            if line:
                result.append(line)
            elif result and result[-1] != "":
                result.append("")
        return "\n".join(result).strip()


def description_text(value: Any, format_type: Any) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    if str(format_type or "").upper() == "RICHTEXT":
        try:
            richtext = value if isinstance(value, dict) else json.loads(raw)
            if isinstance(richtext, dict) and isinstance(richtext.get("htmlValue"), str):
                raw = richtext["htmlValue"]
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if str(format_type or "").upper() != "RICHTEXT" and "<" not in raw:
        return raw.strip()
    parser = _RichTextExtractor()
    try:
        parser.feed(raw)
        parser.close()
        return unescape(parser.text())
    except Exception:
        return raw.strip()


def load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise YunxiaoError(f"云效配置不存在：{path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise YunxiaoError(f"云效配置无法读取：{path}（{exc}）") from exc
    if not isinstance(value, dict):
        raise YunxiaoError("云效配置必须是 JSON object")
    return value


def load_token(organization_id: str) -> str:
    token = os.environ.get(TOKEN_ENV_NAME, "").strip()
    if token:
        return token

    security = Path("/usr/bin/security")
    if sys.platform == "darwin" and security.exists():
        result = subprocess.run(
            [
                str(security),
                "find-generic-password",
                "-a",
                organization_id,
                "-s",
                KEYCHAIN_SERVICE,
                "-w",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        candidate = result.stdout.strip()
        if result.returncode == 0 and candidate:
            return candidate

    # 支持从用户私有目录读取凭据，无需在进程环境中传入令牌。
    private_root = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config"))
    token_path = private_root / "release-checklist" / f"{organization_id}.token"
    if token_path.is_file():
        try:
            candidate = token_path.read_text(encoding="utf-8").strip()
        except OSError:
            raise YunxiaoError("无法读取已导入的私有云效凭据，请检查本机文件权限") from None
        if candidate:
            return candidate

    raise YunxiaoError(
        "未找到云效个人访问令牌。请运行 configure_yunxiao.py --store-token，"
        f"或设置 {TOKEN_ENV_NAME}。"
    )


def normalize_base_url(value: Any) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise YunxiaoError("配置中的 baseUrl 必须是完整的 http(s) OpenAPI 地址")
    if parsed.netloc.lower() == "devops.aliyun.com":
        raise YunxiaoError("baseUrl 是云效网页地址，请改为 OpenAPI 地址")
    return base_url


def projex_root(base_url: str) -> str:
    marker = "/oapi/v1/projex"
    marker_index = base_url.find(marker)
    if marker_index >= 0:
        return base_url[: marker_index + len(marker)]
    return base_url + marker


class YunxiaoClient:
    def __init__(
        self,
        base_url: str,
        organization_id: str,
        token: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url
        self.organization_id = organization_id
        self.token = token
        self.timeout = timeout
        self.prefix = (
            f"{projex_root(base_url)}/organizations/"
            f"{quote(organization_id, safe='')}"
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = self.prefix + path
        if query:
            url += "?" + urlencode(query, doseq=True)
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            url,
            data=payload,
            method=method,
            headers={
                "Content-Type": "application/json",
                "x-yunxiao-token": self.token,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = ""
            try:
                error_body = exc.read(8192).decode("utf-8", errors="replace")
                parsed = json.loads(error_body)
                detail = str(
                    parsed.get("message")
                    or parsed.get("error")
                    or parsed.get("errorMessage")
                    or ""
                )
            except Exception:
                detail = ""
            if self.token and detail:
                detail = detail.replace(self.token, "[REDACTED]")
            suffix = f"：{detail}" if detail else ""
            raise YunxiaoError(f"云效 API {path} 返回 HTTP {exc.code}{suffix}") from exc
        except URLError as exc:
            raise YunxiaoError(f"无法连接云效 API {path}：{exc.reason}") from exc
        except TimeoutError as exc:
            raise YunxiaoError(f"云效 API {path} 请求超时") from exc

        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise YunxiaoError(f"云效 API {path} 返回了非 JSON 数据") from exc

    def search_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            batch = self.request(
                "POST",
                "/projects:search",
                body={
                    "orderBy": "name",
                    "page": page,
                    "perPage": PAGE_SIZE,
                    "sort": "asc",
                },
            )
            if not isinstance(batch, list):
                raise YunxiaoError("搜索项目返回格式异常，预期为 array")
            projects.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < PAGE_SIZE:
                return projects
        raise YunxiaoError(f"项目数量超过脚本上限 {PAGE_SIZE * MAX_PAGES}")

    def list_sprints(self, project_id: str, iteration_name: str) -> list[dict[str, Any]]:
        sprints: list[dict[str, Any]] = []
        encoded_project_id = quote(project_id, safe="")
        for page in range(1, MAX_PAGES + 1):
            batch = self.request(
                "GET",
                f"/projects/{encoded_project_id}/sprints",
                query={
                    "name": iteration_name,
                    "page": page,
                    "perPage": PAGE_SIZE,
                },
            )
            if not isinstance(batch, list):
                raise YunxiaoError(f"项目 {project_id} 的迭代列表返回格式异常")
            sprints.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < PAGE_SIZE:
                return sprints
        raise YunxiaoError(f"项目 {project_id} 的迭代数量超过脚本上限")

    def search_workitems(self, project_id: str, categories: str) -> list[dict[str, Any]]:
        workitems: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            batch = self.request(
                "POST",
                "/workitems:search",
                body={
                    "category": categories,
                    "orderBy": "gmtCreate",
                    "page": page,
                    "perPage": PAGE_SIZE,
                    "sort": "asc",
                    "spaceId": project_id,
                    "spaceType": "Project",
                },
            )
            if not isinstance(batch, list):
                raise YunxiaoError("搜索工作项返回格式异常，预期为 array")
            workitems.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < PAGE_SIZE:
                return workitems
        raise YunxiaoError(f"工作项数量超过脚本上限 {PAGE_SIZE * MAX_PAGES}")

    def get_workitem(self, workitem_id: str) -> dict[str, Any]:
        item = self.request(
            "GET",
            f"/workitems/{quote(workitem_id, safe='')}",
        )
        if not isinstance(item, dict):
            raise YunxiaoError(f"工作项 {workitem_id} 详情返回格式异常")
        return item


def project_identity(project: dict[str, Any]) -> tuple[str, str]:
    return str(project.get("id") or ""), str(project.get("name") or "")


def sprint_candidate(project: dict[str, Any], sprint: dict[str, Any]) -> dict[str, Any]:
    project_id, project_name = project_identity(project)
    return {
        "projectId": project_id,
        "projectName": project_name,
        "iterationId": str(sprint.get("id") or ""),
        "iterationName": str(sprint.get("name") or ""),
        "startDate": sprint.get("startDate"),
        "endDate": sprint.get("endDate"),
        "status": sprint.get("status"),
        "sprint": sprint,
        "project": project,
    }


def resolve_iteration(
    client: YunxiaoClient,
    projects: list[dict[str, Any]],
    iteration_name: str,
    max_workers: int,
) -> tuple[dict[str, Any], list[str]]:
    exact: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    warnings: list[str] = []

    def load(project: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        project_id, _ = project_identity(project)
        if not project_id:
            return project, []
        return project, client.list_sprints(project_id, iteration_name)

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = {executor.submit(load, project): project for project in projects}
        for future in as_completed(futures):
            project = futures[future]
            project_id, project_name = project_identity(project)
            try:
                _, sprints = future.result()
            except YunxiaoError as exc:
                warnings.append(
                    f"项目 {project_name or project_id} 的迭代读取失败：{exc}"
                )
                continue
            for sprint in sprints:
                candidate = sprint_candidate(project, sprint)
                all_candidates.append(candidate)
                if str(sprint.get("name") or "").strip() == iteration_name:
                    exact.append(candidate)

    if len(exact) == 1:
        return exact[0], warnings

    def display(candidate: dict[str, Any]) -> str:
        return (
            f"{candidate['projectName']} ({candidate['projectId']}) / "
            f"{candidate['iterationName']} ({candidate['iterationId']}) / "
            f"{candidate.get('startDate') or '?'} ~ {candidate.get('endDate') or '?'} / "
            f"{candidate.get('status') or '?'}"
        )

    if len(exact) > 1:
        detail = "\n".join(f"- {display(item)}" for item in exact)
        raise YunxiaoError(
            "迭代名称存在多个精确匹配，请使用 --project-id 指定项目：\n" + detail
        )

    names = sorted(
        {
            str(candidate.get("iterationName") or "")
            for candidate in all_candidates
            if candidate.get("iterationName")
        }
    )
    close_names = difflib.get_close_matches(iteration_name, names, n=8, cutoff=0.45)
    suggestions = [
        candidate
        for candidate in all_candidates
        if candidate.get("iterationName") in close_names
    ][:12]
    detail = ""
    if suggestions:
        detail = "\n相近候选：\n" + "\n".join(
            f"- {display(item)}" for item in suggestions
        )
    if warnings and not all_candidates:
        detail += "\n所有候选项目均读取失败，请检查令牌权限或项目范围。"
    raise YunxiaoError(f"未找到精确匹配的迭代：{iteration_name}{detail}")


def custom_fields(item: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    raw_fields = item.get("customFieldValues")
    if not isinstance(raw_fields, list):
        return result
    for field in raw_fields:
        if not isinstance(field, dict):
            continue
        values: list[dict[str, str]] = []
        raw_values = field.get("values")
        if isinstance(raw_values, list):
            for value in raw_values:
                if isinstance(value, dict):
                    values.append(
                        {
                            "displayValue": str(value.get("displayValue") or ""),
                            "identifier": str(value.get("identifier") or ""),
                        }
                    )
                elif value is not None:
                    values.append({"displayValue": str(value), "identifier": ""})
        result.append(
            {
                "fieldId": str(field.get("fieldId") or ""),
                "fieldName": str(field.get("fieldName") or ""),
                "fieldFormat": str(field.get("fieldFormat") or ""),
                "values": values,
            }
        )
    return result


def object_name(value: Any) -> str:
    return str(value.get("name") or value.get("displayName") or "") if isinstance(value, dict) else ""


def object_id(value: Any) -> str:
    return str(value.get("id") or "") if isinstance(value, dict) else ""


def normalize_workitem(item: dict[str, Any], selection_reason: str) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "serialNumber": str(item.get("serialNumber") or ""),
        "categoryId": str(item.get("categoryId") or ""),
        "workitemType": object_name(item.get("workitemType")),
        "subject": str(item.get("subject") or item.get("name") or ""),
        "description": str(item.get("description") or ""),
        "descriptionFormat": str(item.get("formatType") or ""),
        "descriptionText": description_text(
            item.get("description"), item.get("formatType")
        ),
        "parentId": str(item.get("parentId") or ""),
        "idPath": str(item.get("idPath") or ""),
        "status": {
            "id": object_id(item.get("status")),
            "name": object_name(item.get("status")),
        },
        "assignedTo": {
            "id": object_id(item.get("assignedTo")),
            "name": object_name(item.get("assignedTo")),
        },
        "labels": [
            str(label.get("name") or "")
            for label in (item.get("labels") or [])
            if isinstance(label, dict) and label.get("name")
        ],
        "customFields": custom_fields(item),
        "gmtCreate": item.get("gmtCreate"),
        "gmtModified": item.get("gmtModified"),
        "selectionReason": selection_reason,
    }


def select_iteration_tree(
    workitems: list[dict[str, Any]], iteration_id: str
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    by_id = {
        str(item.get("id")): item
        for item in workitems
        if isinstance(item, dict) and item.get("id")
    }
    direct_ids = {
        item_id
        for item_id, item in by_id.items()
        if isinstance(item.get("sprint"), dict)
        and str(item["sprint"].get("id") or "") == iteration_id
    }
    selected_ids = set(direct_ids)

    for item_id in list(direct_ids):
        current = by_id.get(item_id)
        visited: set[str] = set()
        while current:
            parent_id = str(current.get("parentId") or "")
            if not parent_id or parent_id in visited or parent_id not in by_id:
                break
            selected_ids.add(parent_id)
            visited.add(parent_id)
            current = by_id[parent_id]

    changed = True
    descendant_ids: set[str] = set()
    while changed:
        changed = False
        for item_id, item in by_id.items():
            parent_id = str(item.get("parentId") or "")
            item_sprint = item.get("sprint")
            item_sprint_id = (
                str(item_sprint.get("id") or "")
                if isinstance(item_sprint, dict)
                else ""
            )
            if (
                item_id not in selected_ids
                and parent_id in direct_ids.union(descendant_ids)
                and item_sprint_id in {"", iteration_id}
            ):
                selected_ids.add(item_id)
                descendant_ids.add(item_id)
                changed = True

    selected = [by_id[item_id] for item_id in selected_ids]
    return selected, direct_ids, descendant_ids


def sort_workitems(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            str(item.get("serialNumber") or ""),
            str(item.get("gmtCreate") or ""),
            str(item.get("id") or ""),
        ),
    )


def hydrate_workitem_details(
    client: YunxiaoClient,
    items: list[dict[str, Any]],
    max_workers: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    details: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = {
            executor.submit(client.get_workitem, str(item.get("id") or "")): item
            for item in items
            if item.get("id")
        }
        for future in as_completed(futures):
            search_item = futures[future]
            item_id = str(search_item.get("id") or "")
            serial_number = str(search_item.get("serialNumber") or item_id)
            try:
                detail = future.result()
            except YunxiaoError as exc:
                warnings.append(f"工作项 {serial_number} 详情读取失败：{exc}")
                continue
            merged = dict(search_item)
            merged.update(detail)
            details[item_id] = merged

    return [
        details.get(str(item.get("id") or ""), item)
        for item in items
    ], warnings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按完整名称读取云效迭代的原始需求与任务。"
    )
    parser.add_argument("--iteration-name", required=True, help="云效完整迭代名称")
    parser.add_argument("--project-id", help="迭代重名时指定云效项目 ID")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--base-url", help="临时覆盖配置中的 OpenAPI 地址")
    parser.add_argument("--organization-id", help="临时覆盖配置中的云效组织 ID")
    parser.add_argument("--output", type=Path, help="输出 JSON 文件；默认写 stdout")
    parser.add_argument("--categories", default=DEFAULT_CATEGORIES)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--project-workers", type=int, default=8)
    parser.add_argument("--workitem-workers", type=int, default=8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    iteration_name = args.iteration_name.strip()
    if not iteration_name:
        print("读取失败：迭代名称不能为空", file=sys.stderr)
        return 2

    try:
        config = load_config(args.config)
        base_url = normalize_base_url(args.base_url or config.get("baseUrl"))
        organization_id = str(
            args.organization_id or config.get("organizationId") or ""
        ).strip()
        if not organization_id:
            raise YunxiaoError("云效 organizationId 尚未配置")
        token = load_token(organization_id)
        client = YunxiaoClient(base_url, organization_id, token, args.timeout)

        projects = client.search_projects()
        configured_project_ids = {
            str(value).strip()
            for value in config.get("projectIds", [])
            if str(value).strip()
        }
        requested_project_ids = {args.project_id.strip()} if args.project_id else set()
        allowed_project_ids = requested_project_ids or configured_project_ids
        if allowed_project_ids:
            projects = [
                project
                for project in projects
                if str(project.get("id") or "") in allowed_project_ids
            ]
            visible_ids = {str(project.get("id") or "") for project in projects}
            missing_ids = sorted(allowed_project_ids - visible_ids)
            if missing_ids:
                raise YunxiaoError(
                    "以下项目 ID 不在令牌可见项目中：" + ", ".join(missing_ids)
                )
        if not projects:
            raise YunxiaoError("令牌下没有可读取的云效项目")

        match, warnings = resolve_iteration(
            client, projects, iteration_name, args.project_workers
        )
        project = match["project"]
        sprint = match["sprint"]
        project_id = str(project.get("id") or "")
        iteration_id = str(sprint.get("id") or "")
        all_workitems = client.search_workitems(project_id, args.categories)
        selected, direct_ids, descendant_ids = select_iteration_tree(
            all_workitems, iteration_id
        )
        selected, detail_warnings = hydrate_workitem_details(
            client, selected, args.workitem_workers
        )
        warnings.extend(detail_warnings)

        normalized: list[dict[str, Any]] = []
        for item in selected:
            item_id = str(item.get("id") or "")
            if item_id in direct_ids:
                reason = "iteration"
            elif item_id in descendant_ids:
                reason = "descendant"
            else:
                reason = "ancestor"
            normalized.append(normalize_workitem(item, reason))
        normalized = sort_workitems(normalized)
        requirements = [
            item for item in normalized if item["categoryId"].lower() == "req"
        ]
        tasks = [
            item for item in normalized if item["categoryId"].lower() == "task"
        ]
        other = [
            item
            for item in normalized
            if item["categoryId"].lower() not in {"req", "task"}
        ]

        output = {
            "schemaVersion": 1,
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "source": {
                "baseUrl": base_url,
                "organizationId": organization_id,
                "project": {
                    "id": project_id,
                    "name": str(project.get("name") or ""),
                },
                "iteration": {
                    "id": iteration_id,
                    "name": str(sprint.get("name") or ""),
                    "description": str(sprint.get("description") or ""),
                    "startDate": sprint.get("startDate"),
                    "endDate": sprint.get("endDate"),
                    "status": sprint.get("status"),
                },
                "categories": args.categories,
            },
            "counts": {
                "searchedWorkitems": len(all_workitems),
                "selectedWorkitems": len(normalized),
                "requirements": len(requirements),
                "tasks": len(tasks),
                "other": len(other),
            },
            "warnings": warnings,
            "requirements": requirements,
            "tasks": tasks,
            "otherWorkitems": other,
        }
        rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
            os.chmod(args.output, 0o600)
            print(
                f"已读取迭代 {iteration_name}：{len(requirements)} 条需求、"
                f"{len(tasks)} 个任务，输出 {args.output}"
            )
        else:
            sys.stdout.write(rendered)
        return 0
    except YunxiaoError as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
