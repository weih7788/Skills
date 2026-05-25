# LLM Wiki Schema

## 1. 目标

本规范用于统一项目知识页的结构、可信度分层、引用方式和维护动作，避免知识库继续演化成新的“文档堆”。

本项目的 LLM Wiki 只做两件事：

- 把已有事实编译成稳定知识页
- 把事实之间的关系表达清楚

它不替代源码、SQL、脚本和正式设计文档。

## 2. 三层结构

### 2.1 Raw Sources

原始知识源，包含但不限于：

- 仓库中的正式设计文档
- SQL 脚本
- 关键源码文件
- Groovy 脚本
- 发布 checklist
- 事故复盘与问题记录

约束：

- `raw` 只登记来源，不做事实改写
- 原始文件可以在仓库原位置维护，不强制复制到 `knowledge/raw`
- `knowledge/raw` 至少需要维护“来源目录”和“推荐阅读入口”
- `knowledge/` 只存放 wiki 相关 Markdown 与索引，**不存放维护脚本**；bootstrap、lint、迁移等脚本均在 skill 的 `scripts/` 目录中

### 2.2 Wiki

稳定知识页，面向：

- 新同学入项
- 业务排障
- 需求分析
- 代码评审
- LLM 检索与回答

Wiki 页必须：

- 有明确主题
- 有来源引用
- 有状态标记
- 能指出边界、例外和待确认项

### 2.3 Schema

Schema 用来约束：

- 页面类型
- 页面模板
- 元信息字段
- 引用格式
- 可信度标注
- 维护流程

### 2.4 外部私有知识库（可选）

除项目内 `{repo_root}/knowledge/` 外，支持通过项目根目录 `knowledge.md` 将 wiki 指向本机绝对路径（`knowledge_root`）。多个项目可共用同一 `knowledge_root`。

- `knowledge.md` 建议仅本机使用（加入 `.gitignore`），模板见 skill 的 `references/knowledge.md.example`
- 外部模式下，wiki 文件位于 `{knowledge_root}/wiki/`，不在当前项目仓库内
- **双根解析**：项目来源相对 `project_root`（未配置时自动等于解析后的 `repo_root`）；wiki 互链相对 `knowledge_root`（推荐 `wiki/...` 前缀）
- **`project_root` 自动解析**：`knowledge.md` 未配置 `project_root` 时，须先解析 `repo_root`（`--repo-root` → 向上找 `.git` → 当前工作目录），再令 `project_root = repo_root`（均为 `.resolve()` 后的绝对路径）；禁止猜测 `../../../` 路径
- **项目命名空间**：多个项目共用同一 `knowledge_root` 时，建议每个项目在 `knowledge.md` 配置稳定的 `project_key`（如 `backend`、`frontend`）。共享 wiki 页引用项目来源时可写 `project_key:path/to/source`，避免前后端同名路径冲突。
- **外部模式链接 target**：wiki 正文引用项目源文件时，Markdown target 仍相对当前 wiki 页；**`raw/README.md` 索引**引用项目源文件时，Markdown target **必须**为 `project_root` 拼出的本机绝对路径（`< /abs/path/to/file >`），label 仍保留项目相对路径
- **外部模式 raw 索引不可点链**：知识库在仓库外时，`raw/README.md` 若手写 `../../../project/...` 之类相对路径，Cursor/IDE 预览往往无法跳转；应运行 `refresh_indexes.py` 重新生成，不要手改相对路径
- **路径须明确**：外部模式下，须由用户回答提供绝对路径，或项目 `knowledge.md` 已配置 `knowledge_root`；**不得在路径未明确时猜测或默认路径**
- **路径明确后可自动创建**：上述条件满足时，目标目录不存在可由 bootstrap / 迁移脚本自动创建，并初始化 `wiki/`、`raw/` 等子结构

发现顺序：

- `knowledge_root`：`--knowledge-root` 参数 → `knowledge.md` → `{repo_root}/knowledge/`
- `repo_root`：`--repo-root` 参数 → 从 cwd 向上找 `.git` → cwd
- `project_root`：`knowledge.md` 中的 `project_root` → 未配置时使用上述 `repo_root` 的绝对路径
- `project_key`：`knowledge.md` 中的 `project_key` → 未配置时使用 `project_root` 目录名

#### 多项目共用与冲突规避

外部知识库可以被前端、后端、运营脚本等多个项目共用，但写入时必须遵守下面的并发边界：

- 每个项目使用不同且稳定的 `project_key`；目录改名不应导致历史 wiki 引用失效。
- `source_refs` 引用当前项目来源时，可继续写 `doc/foo.md`；引用其他项目来源或编写跨端共享页面时，必须写成 `backend:doc/foo.md`、`frontend:src/foo.ts` 这类带命名空间的格式。
- `refresh_indexes.py` 在外部模式下只更新 `raw/README.md` 中当前 `project_key` 的自动块，不覆盖其他项目块；不要手动合并或删除其他项目块。
- `lint_knowledge.py` 在外部共享模式下只检查当前 `project_key` 相关页面和 raw 块；只引用其他项目来源的页面应静默跳过，并在最终摘要中计数。
- `wiki/README.md` 是共享的全局页面索引，任一项目刷新都会按当前 `wiki/` 目录重新生成；它不包含项目私有扫描结果。
- 共同编辑同一 wiki 页面前，先查看该页 `owner`、`source_refs` 和现有 `Open Question:`；跨端语义冲突时，新建或更新 `decision` 页面记录取舍，不要直接覆盖另一端结论。

## 3. 页面类型

### 3.1 `domains/`

回答“这个业务域整体是什么、核心对象是什么、入口在哪里、关键流程是什么”。

适用示例：

- `entrusted`
- `booking`
- `bill_input`

### 3.2 `concepts/`

回答“某个概念、字段、规则、枚举究竟是什么意思”。

适用示例：

- `businessNo`
- `thirdSystemNo`
- `tenantId`
- `DTO/VO/Entity`

### 3.3 `flows/`

回答“一个完整链路怎么跑、经过哪些模块、在哪些点落库、在哪些点调用脚本/三方”。

### 3.4 `integrations/`

回答“某个三方系统如何接入、依赖哪些字段、哪些租户在用、异常点在哪里”。

### 3.5 `data-models/`

回答“关键表、Mongo 结构、配置模型的语义和关联”。

### 3.6 `runbooks/`

回答“线上问题如何排查、上线前后如何检查、出错时先看哪里”。

### 3.7 `decisions/`

记录关键设计决策，回答“为什么这么设计，而不是别的做法”。

## 4. 页面元信息

每个 wiki 页面头部都使用 YAML Front Matter：

```md
---
title: 页面标题
type: domain|concept|flow|integration|data-model|runbook|decision
status: draft|reviewed|canonical
owner: 团队或模块
last_verified_at: 2026-04-14
source_refs:
  - doc/example_design.md
related_pages:
  - knowledge/wiki/domains/example.md
---
```

字段说明：

- `status=draft`：初稿，允许存在不完整项
- `status=reviewed`：已有人审阅，但仍可能有局部过期
- `status=canonical`：当前推荐优先引用的知识页
- `source_refs`：项目来源相对**当前项目仓库根目录**；外部共享模式可用 `project_key:相对路径` 标明来源项目；wiki 互链可用 `wiki/...`（外部模式，相对 knowledge_root）或 `knowledge/wiki/...`（本地模式，相对 repo_root）
- `related_pages`：同上；外部模式推荐 `wiki/{type}/{page}.md`
- `source_refs` 和 `related_pages` 是机器可读索引；其中每一项都必须在正文中有**可跳转** Markdown 链接（`label` 与 front matter 路径一致，`target` 相对当前 wiki 页），确保读者可直接跳转到目标文件或目录
- `last_verified_at`：每次实质性更新或复核 wiki 页面时都必须更新；超过 30 天未验证视为陈旧知识

## 5. 正文推荐结构

除非页面非常短，否则建议按下面顺序组织：

1. 这是什么
2. 为什么存在
3. 核心对象/字段/模块
4. 关键流程
5. 边界与例外
6. 风险与待确认项
7. Sources

## 6. 引用规则

### 6.1 `source_refs` 与 `related_pages`

用于页面头部列出最主要的事实来源（`source_refs`）与相关 wiki 页（`related_pages`）。

要求：

- Front Matter 中保留相对路径字符串，供脚本校验（项目来源相对 `repo_root`，wiki 互链相对 `knowledge_root` 或 `repo_root`，见第 2.4 节）。
- 正文必须为每个 `source_refs` 项提供符合第 6.2 节格式的可跳转 Markdown 链接，通常放在 `Sources` 小节，使用 `Source:` 前缀。
- 正文必须为每个 `related_pages` 项提供符合第 6.2 节格式的可跳转 Markdown 链接，通常放在 `Related Pages` 小节或相关段落，使用 `Ref:` 前缀。
- 链接 `label` 必须与 front matter 中的路径字符串完全一致，否则视为未满足可跳转要求。

### 6.2 源文件引用格式（强制）

正文中**所有**源文件引用必须使用以下 Markdown 链接格式：

```md
[ref-label](relative-from-current-wiki-page)
```

其中 `ref-label` 与 front matter 中的路径字符串一致：项目来源为 repo-root 相对路径（如 `doc/design/foo.md`）或外部共享模式的项目命名空间路径（如 `backend:doc/design/foo.md`），wiki 互链在外部模式下为 `wiki/flows/example.md`。

适用场景：

- `Sources` 小节中每个 `source_refs` 条目（`Source:` 前缀）
- `Related Pages` 小节中每个 `related_pages` 条目（`Ref:` 前缀）
- 正文中任何 `Source:` 标注
- 正文中指向仓库内源文件（设计文档、SQL、脚本、关键源码等）的引用

正文标注前缀：

- `Source:` 明确来源；行首必须是 Markdown 链接，可在链接后附加说明文字
- `Ref:` 明确相关 wiki 页；行首必须是 Markdown 链接，可在链接后附加说明文字
- `Inference:` 明确该结论是综合多个来源推断得到
- `Open Question:` 明确仍需确认

示例：

```md
Source: [doc/design/entrust/BusinessNo_design.md](../../../doc/design/entrust/BusinessNo_design.md)
Source: [doc/design/entrust/BusinessNo_design.md](../../../doc/design/entrust/BusinessNo_design.md) — 字段语义以此文档为准
Source: [backend:doc/design/order.md](</Users/you/work/order-backend/doc/design/order.md>) — 共享外部知识库中引用后端项目来源
Inference: 当前 `thirdSystemNo` 已被统一定义为系统内部工作单号，但仍需核对所有历史脚本是否都已切换。
Open Question: 是否存在仅在生产脚本中保留的旧字段回退逻辑。
```

补充约定：

- Front Matter 中的路径是相对路径字符串，便于脚本检查；禁止 `./`、`../` 和绝对路径。
- Front Matter 里的每个 `source_refs` / `related_pages` 条目，都必须能在正文中找到一个解析后指向同一目标的 Markdown 链接。
- Markdown 正文中的链接**目标**（圆括号内）使用相对当前文件的标准相对路径，便于在 Git 平台和本地 IDE 中直接跳转。
- Markdown 正文中的链接 **label**（方括号内）与 `source_refs` / `related_pages` 路径字符串完全一致。

外部模式下 wiki 互链示例：

```md
Ref: [wiki/flows/release-monitoring-execution.md](../flows/release-monitoring-execution.md)
```

链接写法示例（以 `knowledge/wiki/concepts/foo.md` 引用设计文档为例）：

```md
Source: [doc/design/entrust/BusinessNo_design.md](../../../doc/design/entrust/BusinessNo_design.md)
```

- 方括号内：`doc/design/entrust/BusinessNo_design.md`（repo-root 相对路径）
- 圆括号内：`../../../doc/design/entrust/BusinessNo_design.md`（相对当前 wiki 页的可跳转路径）

不允许的写法：

- 纯文本路径：`Source: doc/design/foo.md`
- 仅反引号路径：`Source: \`doc/design/foo.md\``
- label 仅写文件名：`Source: [foo.md](../../../doc/design/foo.md)`

wiki 内互链（`related_pages`）示例：

```md
Ref: [knowledge/wiki/flows/release-monitoring-execution.md](../flows/release-monitoring-execution.md)
```

- 方括号内：`knowledge/wiki/flows/release-monitoring-execution.md`（与 `related_pages` 一致）
- 圆括号内：相对当前 wiki 页的可跳转路径

### 6.3 `raw/README.md` 索引（自动生成）

`raw/README.md` 的 `AUTO-GENERATED` 块由 `refresh_indexes.py` 维护，**不要手改链接 target**。外部共享模式下，raw 索引按 `project_key` 分块维护。

格式要求：

- 每行以 `- Source:` 开头，后接 Markdown 链接
- **label**：项目相对路径（本地模式）或 `project_key:项目相对路径`（外部共享模式），如 `backend:db/migration/V20260523_02__mp_points_card.sql`
- **target**：
  - **本地模式**（`knowledge_root` 在仓库内）：相对 `raw/README.md` 的可跳转路径
  - **外部模式**（`knowledge_root` 在仓库外）：`project_root` 下的本机绝对路径，用尖括号包裹

外部模式示例：

```md
## Project: backend

<!-- AUTO-GENERATED:START project=backend -->
- Source: [backend:db/points_mall.sql](</Users/you/work/points-mall-backend/db/points_mall.sql>)
<!-- AUTO-GENERATED:END project=backend -->
```

不允许的写法（外部模式）：

```md
- [db/points_mall.sql](../../../work/points-mall-backend/db/points_mall.sql)
- Source: [db/points_mall.sql](../../../work/points-mall-backend/db/points_mall.sql)
```

原因：外部知识库文件不在当前 Git 工作区内，跨目录 `../` 相对路径在 IDE Markdown 预览中通常无法解析。绝对路径由 `refresh_indexes.py` 根据解析后的 `project_root` 生成——若 `knowledge.md` 未配置，脚本会先按 `--repo-root` / `.git` 自动计算出 `repo_root` 并用作 `project_root`。

修复方式：

```bash
python <skill>/scripts/refresh_indexes.py --repo-root <项目>
```

## 7. 内容约束

必须遵守：

- 不把源码不存在的行为写成既定事实
- 不把一次性口头结论写成 canonical 事实
- 不用“大概率”“应该”掩盖不确定性，必须显式标注 `Inference` 或 `Open Question`
- 不复制大段源码，优先总结语义并给源码链接

## 8. 维护动作

### 8.1 Ingest

出现下列材料时，应更新 `raw` 和相关 wiki：

- 新设计文档
- 新 SQL 变更
- 新增或修改关键脚本
- 关键接口/字段语义调整
- 线上事故复盘

### 8.2 Query

LLM 或研发检索时，优先顺序建议：

1. `wiki/canonical`
2. `wiki/reviewed`
3. `raw`
4. 源码直接检索

### 8.3 Lint

后续可自动检查：

- 页面无 `source_refs`
- `source_refs` / `related_pages` 未在正文提供可跳转链接，或链接 label 与 front matter 路径不一致
- `Source:` / `Ref:` 行未以 Markdown 链接开头
- Markdown 链接 label 不是 repo-root 相对路径，或与 target 解析结果不一致
- 页面超过 30 天未验证
- 页面引用的源码路径不存在
- 外部模式下 `raw/README.md` 使用 `../` 相对 target（应运行 `refresh_indexes.py` 生成绝对路径）
- `raw/README.md` 索引行缺少 `Source:` 前缀或链接 target 不存在
- 外部共享模式下 `raw/README.md` 只有一个全局 raw 自动块，导致一个项目刷新时覆盖另一个项目的来源索引
- 外部共享模式下从当前项目 lint 时逐条报告其他项目页面的路径不存在；这些页面应由所属项目 lint 校验
- 同一概念存在多个冲突页面
- `Open Question` 长期未关闭

## 9. 建议模板

### 9.1 Domain 模板

```md
---
title: Xxx Domain
type: domain
status: draft
owner: xxx
last_verified_at: 2026-04-14
source_refs: []
related_pages: []
---

## 这是什么

## 核心对象

## 核心入口

## 关键流程

## 边界与例外

## 风险与待确认项

## Sources
```

### 9.2 Concept 模板

```md
---
title: Xxx Concept
type: concept
status: draft
owner: xxx
last_verified_at: 2026-04-14
source_refs: []
related_pages: []
---

## 定义

## 使用位置

## 约束

## 常见误解

## 风险与待确认项

## Sources
```

### 9.3 Flow 模板

```md
---
title: Xxx Flow
type: flow
status: draft
owner: xxx
last_verified_at: 2026-04-14
source_refs: []
related_pages: []
---

## 触发条件

## 流程步骤

## 关键落库/调用点

## 异常与回退

## Sources
```

## 10. 当前阶段约定

第一阶段只做“最小可用知识库”，重点是：

- 目录结构稳定
- 首批关键页面建立
- 页面之间形成链接
- 明确后续怎么补充，而不是一次性写全
