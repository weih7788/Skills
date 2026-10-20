#!/usr/bin/env python3
"""Configure non-secret Yunxiao settings and store the PAT in macOS Keychain."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = SKILL_ROOT / "config" / "yunxiao.json"
KEYCHAIN_SERVICE = "codex.release-checklist.yunxiao"
DEFAULT_BASE_URL = "https://openapi-rdc.aliyuncs.com"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {
            "baseUrl": DEFAULT_BASE_URL,
            "organizationId": "",
            "projectIds": [],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取配置 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"配置必须是 JSON object: {path}")
    return value


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("云效 OpenAPI 地址必须是完整的 http(s) URL")
    if parsed.netloc.lower() == "devops.aliyun.com":
        raise ValueError("请填写 OpenAPI 地址，不要填写云效网页地址 devops.aliyun.com")
    return normalized


def save_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def store_token(organization_id: str) -> None:
    security = Path("/usr/bin/security")
    if sys.platform != "darwin" or not security.exists():
        raise RuntimeError(
            "当前系统无法使用 macOS Keychain；请改用环境变量 "
            "YUNXIAO_PERSONAL_ACCESS_TOKEN"
        )
    if not sys.stdin.isatty():
        raise RuntimeError("请在本机交互式终端运行 --store-token，以便安全隐藏令牌输入")

    print(f"即将把组织 {organization_id} 的只读云效令牌保存到 macOS Keychain。")
    print("Password: 提示出现后粘贴个人访问令牌并回车；输入不会回显。")
    command = [
        str(security),
        "add-generic-password",
        "-U",
        "-a",
        organization_id,
        "-s",
        KEYCHAIN_SERVICE,
        "-w",
    ]
    subprocess.run(command, check=True)
    print("令牌已保存到 macOS Keychain。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="配置 release-checklist 的云效只读接入。"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--base-url", help="云效 OpenAPI 服务地址")
    parser.add_argument("--organization-id", help="云效组织 ID")
    parser.add_argument(
        "--project-id",
        action="append",
        default=[],
        help="限制扫描的云效项目 ID，可重复传入；传入后替换现有列表",
    )
    parser.add_argument(
        "--clear-project-ids",
        action="store_true",
        help="清空项目限制，允许扫描令牌可见的全部项目",
    )
    parser.add_argument(
        "--store-token",
        action="store_true",
        help="通过隐藏提示把个人访问令牌保存到 macOS Keychain",
    )
    parser.add_argument("--show", action="store_true", help="显示非敏感配置")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not any(
        [
            args.base_url,
            args.organization_id,
            args.project_id,
            args.clear_project_ids,
            args.store_token,
            args.show,
        ]
    ):
        parser.print_help()
        return 0

    try:
        config = load_config(args.config)
        changed = False

        if args.base_url:
            config["baseUrl"] = normalize_base_url(args.base_url)
            changed = True
        else:
            config["baseUrl"] = normalize_base_url(
                str(config.get("baseUrl") or DEFAULT_BASE_URL)
            )

        if args.organization_id is not None:
            organization_id = args.organization_id.strip()
            if not organization_id:
                raise ValueError("organizationId 不能为空")
            config["organizationId"] = organization_id
            changed = True

        if args.clear_project_ids and args.project_id:
            raise ValueError("--clear-project-ids 不能与 --project-id 同时使用")
        if args.clear_project_ids:
            config["projectIds"] = []
            changed = True
        elif args.project_id:
            config["projectIds"] = list(
                dict.fromkeys(value.strip() for value in args.project_id if value.strip())
            )
            changed = True
        else:
            project_ids = config.get("projectIds", [])
            config["projectIds"] = project_ids if isinstance(project_ids, list) else []

        if changed:
            save_config(args.config, config)
            print(f"非敏感配置已保存：{args.config}")

        if args.store_token:
            organization_id = str(config.get("organizationId") or "").strip()
            if not organization_id:
                raise ValueError("请先配置 organizationId，再运行 --store-token")
            store_token(organization_id)

        if args.show or not changed:
            print(json.dumps(config, ensure_ascii=False, indent=2))
            print("个人访问令牌不保存在该 JSON 中。")
        return 0
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"配置失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
