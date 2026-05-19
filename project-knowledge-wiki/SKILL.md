---
name: project-knowledge-wiki
description: 当需要查询当前项目知识库、补充或更新当前项目根目录下的 `knowledge/` 页面、登记新的 raw source、生成 wiki 页面，或对仓库内 LLM Wiki 做 lint / 索引刷新时使用此 skill。凡是需要把一次性对话结论沉淀为可长期复用项目知识的场景，都应优先使用此 skill。
---

# 项目知识库维护

## 概述

这个 skill 用来维护当前项目仓库内的 LLM Wiki，位置在“当前项目根目录”的 `knowledge/`。

它主要服务两类工作：

- 在重新翻代码之前，优先查询已经沉淀的稳定项目知识
- 把新的项目事实整理成带来源、可审阅、可持续维护的 wiki 页面

不要把大量**项目业务事实**直接复制进 skill 本体。业务事实应写在项目 `knowledge/wiki/`、源码、设计文档、SQL 和脚本中。

**结构契约**由 skill 自带的 [references/schema.md](./references/schema.md) 定义；项目里的 `knowledge/SCHEMA.md` 应与该文件保持一致（新建项目时由脚本自动复制，已有项目需人工对齐）。

## Schema 契约（必读）

使用本 skill 进行查询、新建或更新 wiki 前，按以下顺序读取规范：

1. 项目内 `knowledge/SCHEMA.md`（若存在，以项目为准；与 skill 冲突时先核对再合并）
2. skill 内 [references/schema.md](./references/schema.md)（规范真源，含完整 front matter、页面类型、引用规则与模板）

Schema 要点摘要（细节以 `references/schema.md` 为准）：

| 层级 | 职责 |
|------|------|
| `raw/` | 只登记来源索引，不改写事实 |
| `wiki/` | 稳定知识页，带 front matter 与 `source_refs` |
| `SCHEMA.md` | 页面类型、元字段、引用格式、维护流程 |

**Front matter 必填字段**：`title`、`type`、`status`、`owner`、`last_verified_at`、`source_refs`、`related_pages`

**`type` 取值**：`domain` | `concept` | `flow` | `integration` | `data-model` | `runbook` | `decision`

**`status` 可信度**：`draft` → `reviewed` → `canonical`（查询时优先 canonical）

**路径规则**：

- `source_refs`、`related_pages`：相对**仓库根目录**，禁止 `./`、`../`、绝对路径
- 正文 Markdown 链接**目标**（圆括号）：相对**当前 wiki 文件**的可跳转路径
- 正文 Markdown 链接 **label**（方括号）：仅**文件名**（含扩展名），不写目录

**正文标注**：`Source:` / `Inference:` / `Open Question:`（不要把推断写成 canonical 事实）

页面类型说明与章节模板见 [references/page-types.md](./references/page-types.md) 与 schema 第 9 节。

## 项目根目录与知识库位置

1. 使用此 skill 时，先确定当前项目根目录：
   - 优先使用当前工作目录向上找到的 Git 仓库根目录。
   - 如果当前工作目录不在 Git 仓库内，就使用当前工作目录本身。
   - 如果用户显式指定项目目录或 `--repo-root`，以用户指定为准。
2. 知识库始终读取和写入该项目根目录下的 `knowledge/`，不要读取 skill 自身安装目录里的 `knowledge/`。
3. 如果该项目根目录下还没有 `knowledge/`，先创建最小知识库结构，再继续查询或更新：
   - `knowledge/README.md`
   - `knowledge/SCHEMA.md`（由 `scripts/knowledge_bootstrap.py` 从 `references/schema.md` 写入）
   - `knowledge/wiki/README.md`
   - `knowledge/raw/README.md`
   - `knowledge/wiki/{domains,concepts,flows,integrations,data-models,runbooks,decisions}/`
4. 运行附带脚本时，默认在当前项目根目录执行；如果从别的目录调用脚本，传入 `--repo-root /path/to/project`。

## 何时使用

当用户有以下需求时，应触发这个 skill：

- 解释某个项目概念、业务域、流程或历史设计决策
- 在需求变更、代码变更、SQL 变更、脚本变更、事故复盘后更新知识库
- 新建知识页
- 对知识库做 lint 或刷新索引
- 为团队成员沉淀可复用的 onboarding / 项目背景材料

## 核心规则

1. 修改知识库前，先读项目 `knowledge/README.md` 与 `knowledge/SCHEMA.md`；若缺失，执行 lint 或 new_page 脚本完成 bootstrap。
2. 查询知识时优先按 `canonical -> reviewed -> draft` 的顺序使用 `knowledge/wiki`。
3. 如果 wiki 不足以支撑结论，再回退到 raw 文档和源码。
4. 遵守 schema 第 6、7 节的路径与可信度标注规则。
5. 不确定的内容必须显式标记为 `Inference:` 或 `Open Question:`。

## 查询工作流

1. 从 `knowledge/wiki/README.md` 开始定位页面。
2. 优先打开最相关的 `canonical` 或 `reviewed` 页面。
3. 如有需要，再结合 `knowledge/raw/README.md`、设计文档、SQL、脚本或源码做核对。
4. 输出结论时，要区分“来源可证实的事实”和“综合推断”。

更细的流程说明见 [references/workflow.md](./references/workflow.md)。

## 更新工作流

1. 先确认新增事实来自哪里：设计文档、SQL、脚本、代码变更、事故记录或发布检查单。
2. 如果是新的重要来源或新的来源类别，先更新 `knowledge/raw/README.md`。
3. 如果已有页面覆盖该主题，就更新原页面；如果原页面会明显过载，就新建页面。
4. 新建页面时，可优先使用 `scripts/new_page.py`（章节结构对齐 schema 模板）。
5. 更新后执行 `scripts/lint_knowledge.py`（校验项与 schema 第 4、6、8.3 节一致）。
6. 如果页面索引发生变化，再执行 `scripts/refresh_indexes.py`。

## 质量要求

- 每个 wiki 页面都应包含符合 schema 的 front matter。
- `source_refs` 应指向仓库内真实存在的文件或目录。
- 页面完成实质性复核后，应更新 `last_verified_at`。
- 如果页面还不足以稳定复用，就保持 `draft`。

更细的质量标准见 [references/quality-bar.md](./references/quality-bar.md)。

## 附带脚本

| 脚本 | 作用 |
|------|------|
| `scripts/knowledge_bootstrap.py` | 创建 `knowledge/` 目录树；将 `references/schema.md` 写入 `knowledge/SCHEMA.md`（仅当不存在） |
| `scripts/lint_knowledge.py` | 校验 front matter、路径、链接 label、来源是否存在 |
| `scripts/new_page.py` | 按 schema 页面类型生成新 wiki 页；默认要求 `--source-ref`，临时草稿可显式传 `--allow-empty-source-refs` |
| `scripts/refresh_indexes.py` | 刷新 `knowledge/raw/README.md` 与 `knowledge/wiki/README.md` 自动索引区 |

默认前提：这个 skill 可安装在任意位置；**规范真源**在 skill 的 `references/schema.md`，**项目实例**在目标仓库的 `knowledge/`。
