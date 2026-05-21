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
- `source_refs`、`related_pages` 中的每一项，都必须在正文中有可跳转 Markdown 链接（`label` 与 front matter 路径一致，`target` 相对当前 wiki 页）；`source_refs` 用 `Source:`，`related_pages` 用 `Ref:`
- 正文 Markdown 链接**目标**（圆括号）：相对**当前 wiki 文件**的可跳转路径
- 正文 Markdown 链接 **label**（方括号）：**相对仓库根目录**的路径，与 `source_refs` 格式一致
- 正文中所有源文件引用必须使用上述 Markdown 链接格式；`Source:` 行以链接开头，可在链接后附加说明

**正文标注**：`Source:` / `Inference:` / `Open Question:`（不要把推断写成 canonical 事实）

页面类型说明与章节模板见 [references/page-types.md](./references/page-types.md) 与 schema 第 9 节。

## 项目根目录与知识库位置

1. 使用此 skill 时，先确定当前项目根目录：
   - 优先使用当前工作目录向上找到的 Git 仓库根目录。
   - 如果当前工作目录不在 Git 仓库内，就使用当前工作目录本身。
   - 如果用户显式指定项目目录或 `--repo-root`，以用户指定为准。
2. 知识库始终读取和写入该项目根目录下的 `knowledge/`，不要读取 skill 自身安装目录里的 `knowledge/`。
3. 项目 `knowledge/` **只存放 wiki 内容**（Markdown 页面、索引与 `SCHEMA.md`），**不存放维护脚本**。所有 bootstrap / lint / 迁移 / 建页 / 刷索引脚本都在 skill 自带的 `scripts/` 目录中运行，通过 `--repo-root` 操作目标项目。
4. 如果该项目根目录下还没有 `knowledge/`，先创建最小知识库结构，再继续查询或更新：
   - `knowledge/README.md`
   - `knowledge/SCHEMA.md`（由 skill 的 `knowledge_bootstrap.py` 从 `references/schema.md` 写入）
   - `knowledge/wiki/README.md`
   - `knowledge/raw/README.md`
   - `knowledge/wiki/{domains,concepts,flows,integrations,data-models,runbooks,decisions}/`
5. 运行 skill 脚本时，在 skill 安装目录下执行（例如 `python /path/to/project-knowledge-wiki/scripts/lint_knowledge.py --repo-root /path/to/project`）；不要把脚本复制或同步到项目 `knowledge/` 中。

## 何时使用

当用户有以下需求时，应触发这个 skill：

- 解释某个项目概念、业务域、流程或历史设计决策
- 在需求变更、代码变更、SQL 变更、脚本变更、事故复盘后更新知识库
- 新建知识页
- 对知识库做 lint 或刷新索引
- 为团队成员沉淀可复用的 onboarding / 项目背景材料

## 核心规则

1. 修改知识库前，先读项目 `knowledge/README.md` 与 `knowledge/SCHEMA.md`；若缺失，通过 skill 的 `knowledge_bootstrap.py --repo-root <项目>` 完成 bootstrap。
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
4. 新建页面时，可优先使用 skill 的 `new_page.py`（章节结构对齐 schema 模板）。
5. 更新 wiki 页面时，必须同步更新该页 `last_verified_at`；更新后通过 skill 的 `lint_knowledge.py` 校验（校验项与 schema 第 4、6、8.3 节一致）。若页面仍使用旧版引用格式，先执行 skill 的 `migrate_source_links.py`。
6. 如果页面索引发生变化，再执行 skill 的 `refresh_indexes.py`。

## 质量要求

- 每个 wiki 页面都应包含符合 schema 的 front matter。
- `source_refs` 应指向仓库内真实存在的文件或目录。
- 页面完成实质性复核或内容更新后，应更新 `last_verified_at`；超过 30 天未验证会被 lint 判为陈旧。
- 如果页面还不足以稳定复用，就保持 `draft`。

更细的质量标准见 [references/quality-bar.md](./references/quality-bar.md)。

## 附带脚本

以下脚本位于 **skill 安装目录**的 `scripts/` 下，不在项目 `knowledge/` 中。操作时传入 `--repo-root` 指向目标项目即可。

| 脚本 | 作用 |
|------|------|
| `knowledge_bootstrap.py` | 创建项目 `knowledge/` 目录树；将 `references/schema.md` 写入 `knowledge/SCHEMA.md`（仅当不存在） |
| `lint_knowledge.py` | 只读校验 front matter、路径、链接 label、`Source:` 行、来源是否存在，以及 `last_verified_at` 是否超过 30 天 |
| `migrate_source_links.py` | 将已有 wiki 页的源文件引用迁移为标准 Markdown 链接格式（repo-root label） |
| `new_page.py` | 按 schema 页面类型生成新 wiki 页；默认要求 `--source-ref`，临时草稿可显式传 `--allow-empty-source-refs` |
| `refresh_indexes.py` | 刷新 `knowledge/raw/README.md` 与 `knowledge/wiki/README.md` 自动索引区；可用 `--source-root` 补充 raw 来源目录 |

默认前提：这个 skill 可安装在任意位置；**规范真源**在 skill 的 `references/schema.md`，**项目实例**在目标仓库的 `knowledge/`（仅 Markdown 内容与索引，不含脚本）。
