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

不要把大量项目事实直接复制进 skill 本体。真正承载事实的内容应该保留在当前项目仓库里的 `knowledge/`、源码、设计文档、SQL 和脚本中。

## 项目根目录与知识库位置

1. 使用此 skill 时，先确定当前项目根目录：
   - 优先使用当前工作目录向上找到的 Git 仓库根目录。
   - 如果当前工作目录不在 Git 仓库内，就使用当前工作目录本身。
   - 如果用户显式指定项目目录或 `--repo-root`，以用户指定为准。
2. 知识库始终读取和写入该项目根目录下的 `knowledge/`，不要读取 skill 自身安装目录里的 `knowledge/`。
3. 如果该项目根目录下还没有 `knowledge/`，先创建最小知识库结构，再继续查询或更新：
   - `knowledge/README.md`
   - `knowledge/SCHEMA.md`
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

1. 修改知识库结构前，先确保当前项目根目录下存在 `knowledge/`；如果不存在，创建最小结构，然后读 `knowledge/README.md` 和 `knowledge/SCHEMA.md`。
2. 查询知识时优先按 `canonical -> reviewed -> draft` 的顺序使用 `knowledge/wiki`。
3. 如果 wiki 不足以支撑结论，再回退到 raw 文档和源码。
4. `source_refs` 与 `related_pages` 必须使用“相对仓库根目录”的路径。
5. 不确定的内容必须显式标记为 `Inference:` 或 `Open Question:`。
6. 不要把猜测写成 canonical 事实。

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
4. 新建页面时，可优先使用 `scripts/new_page.py`。
5. 更新后执行 `scripts/lint_knowledge.py`。
6. 如果页面索引发生变化，再执行 `scripts/refresh_indexes.py`。

## 页面类型选择

- `domain`：业务域总览
- `concept`：字段语义、规则、重要术语
- `flow`：跨模块流程或时序链路
- `runbook`：重复执行的维护与排障手册
- `decision`：架构或产品级决策

模板与选择建议见 [references/page-types.md](./references/page-types.md)。

## 质量要求

- 每个 wiki 页面都应包含 front matter。
- `source_refs` 应指向仓库内真实存在的文件或目录。
- 页面完成实质性复核后，应更新 `last_verified_at`。
- 如果页面还不足以稳定复用，就保持 `draft`。

更细的质量标准见 [references/quality-bar.md](./references/quality-bar.md)。

## 附带脚本

- `scripts/lint_knowledge.py`：校验 wiki 元信息、路径引用和基础规范。
- `scripts/new_page.py`：按页面类型模板生成新的知识页。
- `scripts/refresh_indexes.py`：刷新 `knowledge/raw/README.md` 与 `knowledge/wiki/README.md` 中的自动索引区。

默认前提：这个 skill 可安装在任意位置；项目知识内容始终存放在“正在使用该 skill 的当前项目根目录”的 `knowledge/` 目录下。
