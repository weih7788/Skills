"""Shared constants for the project knowledge wiki tools."""

from __future__ import annotations

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
    "concept": ["定义", "使用位置", "约束", "常见误解", "风险与待确认项", "Sources"],
    "flow": ["触发条件", "流程步骤", "关键落库/调用点", "异常与回退", "Sources"],
    "integration": ["这是什么", "关键依赖", "调用方式", "异常点", "Sources"],
    "data-model": ["定义", "关键字段", "关联关系", "边界与例外", "Sources"],
    "runbook": ["何时执行", "执行步骤", "校验方式", "常见失败点", "Sources"],
    "decision": ["背景", "决策", "原因", "结果", "不做什么", "Sources"],
}

ALLOWED_TYPES = set(TYPE_TO_DIR)
ALLOWED_STATUS = {"draft", "reviewed", "canonical"}
STALE_AFTER_DAYS = 30
STATUS_ORDER = {"canonical": 0, "reviewed": 1, "draft": 2}

