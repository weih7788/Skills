---
name: project-knowledge-wiki
description: 当需要查询或维护项目知识库时使用；使用本技能从代码、SQL、设计文档等确定性来源确认了可复用的项目事实后，也要自动同步到已有知识库。支持项目内 knowledge/ 与 knowledge.md 指向的外部私有知识库，以及多个子项目分别配置知识库。写入前须确定目标子项目和知识库模式；项目尚无知识库时先让用户选择模式。
---

# 项目知识库维护

## 概述

这个 skill 用来维护 LLM Wiki，支持两种模式：

- **本地模式**：知识库在目标项目或子项目根目录的 `knowledge/`（默认）
- **外部模式**：知识库在本机绝对路径，由目标项目或子项目的 `knowledge.md` 配置（多个项目可指向同一目录）

它主要服务两类工作：

- 在重新翻代码之前，优先查询已经沉淀的稳定项目知识
- 把新的项目事实整理成带来源、可审阅、可持续维护的 wiki 页面

不要把大量**项目业务事实**直接复制进 skill 本体。业务事实应写在知识库 `wiki/`、源码、设计文档、SQL 和脚本中。

**结构契约**只由 skill 自带的 [references/schema.md](./references/schema.md) 定义。项目知识库实例中不要创建或维护 `SCHEMA.md` / scheme 约束文件；`knowledge_root` 只存放 wiki Markdown 与来源索引。

## 沉淀写入前置门禁（第一步，强制）

当用户要求沉淀已确定的方案、流程、决策、排障结论，或本技能触发下需要自动同步从确定性来源确认的项目事实时，**写入前必须确定本次使用哪一种知识库模式**：

- **项目内知识库**：`{config_root}/knowledge/`
- **外部知识库**：`knowledge.md` 中 `knowledge_root` 指向的本机绝对路径

执行顺序不可颠倒：

1. 先确定本次操作对应的目标项目或子项目。以用户指定的项目目录、相关源文件所在目录或当前工作目录作为查找起点；一个工作区可能包含多个子项目，不能直接把最外层 Git 根当成唯一项目根。
2. 从每个查找起点逐级向上查找 `knowledge.md`，到工作区边界为止；**距离目标最近的配置文件优先**。找到配置文件的目录记为 `config_root`，脚本参数 `--repo-root` 必须传这个目录。
3. 若最近的 `knowledge.md` 配置了有效的绝对路径 `knowledge_root`，立即确定为外部模式，以该路径作为唯一 `knowledge_root`，并优先检索外部知识库。即使 `{config_root}/knowledge/` 同时存在，也不构成模式冲突；它可能只是迁移前副本，不得优先检索或静默回退使用。
4. 仅当向上没有找到有效 `knowledge.md` 时，才从查找起点向上检查最近的 `{candidate_root}/knowledge/`（包括忽略规则兜底检查）并判断项目内模式；该目录的父目录成为 `config_root`。
5. 根据判定结果，在首次进度说明中告知用户目标子项目、配置文件位置、知识库模式及路径。
6. 若一次任务涉及多个子项目，分别执行上述解析；每个子项目可拥有不同 `knowledge.md` 和 `knowledge_root`，不得拿其中一个子项目的配置代替全部项目。若无法从上下文确定目标子项目，或发现多个等价候选，必须先询问用户选择范围。
7. 如果项目尚未初始化、`knowledge.md` 配置无效，或用户意图与配置冲突，必须先询问用户；外部模式还必须取得明确绝对路径。
8. **模式和目标路径未确定前立即停止写入流程**：不得选择或新建 wiki 页面，不得登记 raw source，不得 bootstrap、迁移、刷新索引，也不得先把内容写到任一候选目录。

仅仅确认“要补充到知识库”不等于确认知识库模式。即使上下文中的方案或流程已经完全明确，也不能跳过本门禁。

## Schema 契约（必读）

使用本 skill 进行查询、新建或更新 wiki 前，按以下顺序读取规范：

1. 查询或轻量补充知识时，优先读 skill 内 [references/quickstart.md](./references/quickstart.md)
2. 新建页面、批量修改、迁移、lint 失败或引用规则不确定时，再读 skill 内 [references/schema.md](./references/schema.md)（规范真源，含完整 front matter、页面类型、引用规则与模板）
3. 若旧知识库中遗留 `SCHEMA.md`，仅作为历史参考，不以其作为规范真源；不要新建或更新该文件

Schema 要点摘要（细节以 `references/schema.md` 为准）：


| 层级                           | 职责                                   |
| ---------------------------- | ------------------------------------ |
| `raw/`                       | 只登记来源索引，不改写事实                        |
| `wiki/`                      | 稳定知识页，带 front matter 与 `source_refs` |
| skill `references/schema.md` | 页面类型、元字段、引用格式、维护流程（不复制到知识库）          |


**Front matter 必填字段**：`title`、`type`、`status`、`owner`、`last_verified_at`、`source_refs`、`related_pages`

`**type` 取值**：`domain` | `concept` | `flow` | `integration` | `data-model` | `runbook` | `decision`

`**status` 可信度**：`draft` → `reviewed` → `canonical`（查询时优先 canonical）

**路径规则（双根）**：

- **项目来源**（`source_refs` 指向当前项目的设计文档、SQL、源码等）：相对**当前项目仓库根目录**，禁止 `./`、`../`、绝对路径
- **wiki 互链**（`related_pages`）：外部知识库模式下用 `wiki/...`（相对知识库根）；本地模式下仍可用 `knowledge/wiki/...`（相对项目根）
- 正文 Markdown 链接 **label**（方括号）必须与 front matter 路径字符串完全一致
- 正文 Markdown 链接 **target**（圆括号）：wiki 页相对**当前 wiki 文件**；**外部模式下** `raw/README.md` 引用项目源文件时须用 `project_root` 拼出的**本机绝对路径**（`< /abs/path >`），禁止手写 `../../../` 跨出知识库（IDE 内通常无法点击）
- `source_refs` 用 `Source:`，`related_pages` 用 `Ref:`
- **`raw/README.md`**：由 `refresh_indexes.py` 自动生成；外部模式检查或修复链接不可点时，优先重跑该脚本，不要手改相对路径

**正文标注**：`Source:` / `Inference:` / `Open Question:`（不要把推断写成 canonical 事实）

页面类型说明与章节模板见 [references/page-types.md](./references/page-types.md) 与 schema 第 9 节。

## 知识库定位（多项目、多根模型）

使用此 skill 时，先确定目标子项目，再解析以下目录：


| 根               | 含义 | 解析方式 |
| ---------------- | ---- | -------- |
| `workspace_root` | 最外层工作区或 Git 集合根，可能包含多个子项目 | 仅作为向上查找边界，不直接决定知识库 |
| `config_root` / 脚本 `repo_root` | 当前目标子项目的配置根 | 最近 `knowledge.md` 所在目录；无配置时为最近本地 `knowledge/` 的父目录 |
| `project_root` | 当前子项目源文件根，用于解析 `source_refs` 与外部 raw 绝对链接 | `knowledge.md` 中的 `project_root`；未配置时等于 `config_root` |
| `knowledge_root` | 当前子项目 wiki 实际存放目录 | 见下方发现顺序 |
| `project_key` | 多项目共享知识库时的项目命名空间 | `knowledge.md` 中的 `project_key`；未配置时使用 `project_root` 目录名 |

### 子项目配置发现（必做）

1. 选择查找起点：显式指定的子项目目录 > 当前处理文件所在目录 > 当前工作目录。
2. 对每个起点向上逐级检查 `knowledge.md`，直到 `workspace_root`；最近的文件胜出。不要只检查 Git 根。
3. 若没有任何 `knowledge.md`，再向上查找最近已 bootstrap 的 `knowledge/wiki/`。
4. 若用户请求覆盖多个子项目，对每个子项目独立解析。多个子项目可指向同一外部知识库，也可分别指向不同知识库。
5. 若用户只说“这个项目”而工作区内有多个子项目配置，且无法根据相关文件、当前目录或上下文唯一定位，先询问目标子项目，不得任选一个配置。
6. 发现文件时不要只依赖可能受 `.gitignore` 影响的 `rg`/Glob；使用直接路径检查或不忽略文件的方式兜底。

### `project_root` 自动解析（未配置时必做）

`knowledge.md` 里的 `project_root` **可选**。若项目未配置，Agent 与脚本须**自行计算出项目绝对路径**，不得根据目录名或 `../../../` 猜测。

**脚本 `repo_root` / `config_root` 解析顺序**（优先级从高到低）：

1. 脚本参数 `--repo-root <目标子项目配置目录>`（显式传入时）
2. 从当前工作目录向上查找最近的 `knowledge.md`
3. 未找到配置时，从当前工作目录向上查找最近的 `knowledge/wiki/`
4. 以上均失败时，从当前工作目录向上查找含 `.git` 的目录
5. 仍失败时，使用当前工作目录的 `.resolve()` 绝对路径

**`project_root` 解析顺序**：

1. `knowledge.md` 中已配置的 `project_root`（展开 `~` 并 `.resolve()`）
2. 未配置时：**`project_root = config_root`**（即脚本接收的 `repo_root`）

**使用约定**：

- 运行脚本时传入 `--repo-root` 指向含目标 `knowledge.md` 的子项目目录；不要固定传最外层 Git 根
- 若子项目配置目录就是源码根，不必手写 `project_root`；仅当两者不同时才显式配置
- 外部模式生成 `raw/README.md` 绝对链接、校验 `source_refs` 是否存在、拼接 wiki 正文 `Source:` 跳转路径时，一律以解析后的 `project_root` 为准
- **禁止**手写 `../../../work/xxx-backend/...` 代替 `project_root`；链接不可点时运行 `refresh_indexes.py`，由脚本按 `project_root` 重写

**`knowledge_root` 发现顺序**（优先级从高到低）：

1. 脚本参数 `--knowledge-root`（显式指定）
2. 最近的 `knowledge.md` 中的 `knowledge_root`（**本机绝对路径**）
3. fallback：`{config_root}/knowledge/`（本地模式）

**外部配置优先规则**：模式判定和知识查询必须先读取目标子项目最近的 `knowledge.md`。只要其中存在有效的绝对路径 `knowledge_root`，该配置就是该子项目的权威知识库入口：先从外部 `{knowledge_root}/wiki/README.md` 开始检索，不要因为子项目内也存在 `knowledge/` 而询问二选一，也不要在外部查询未命中或目录异常时自动回退到项目内目录。外部目录缺失或不可用时，按外部配置异常处理并告知用户；只有用户明确要求恢复、迁移或改回项目内模式时，才检查项目内副本作为候选。

### 目录发现防漏（`.gitignore` / `.cursorignore`）

某些检索工具会遵循忽略规则，`knowledge/` 即使真实存在，也可能在文件检索结果中被隐藏（例如仓库配置了 `/knowledge/` 到 `.gitignore`）。

为避免误判“知识库不存在”，必须遵循以下兜底顺序：

1. 先按上面的发现顺序解析 `knowledge_root`。
2. 如果 `Glob/rg` 返回空，**不要直接下结论不存在**。
3. 必须用不依赖忽略规则的方式二次确认目录是否真实存在（例如 `ls <repo_root>`、`ls <knowledge_root>`，或直接 `ReadFile` 读取 `<knowledge_root>/README.md`）。
4. 只有在兜底检查也失败时，才进入“未初始化”流程并询问用户选模式。

### knowledge.md 配置

每个项目或子项目根目录都可放置自己的私有配置文件 `knowledge.md`（建议加入 `.gitignore`，仅本机使用）。同一工作区有多个配置时，按目标文件所在子项目分别解析，最近配置优先：

```yaml
knowledge_root: /Users/weihuang/work/knowledge/points-mall
# project_root 可选；未配置时脚本从 --repo-root / .git 自动解析 repo_root 并用作 project_root
# project_root: /Users/weihuang/work/points-mall-backend
# project_key 可选；多个项目共用同一知识库时建议显式配置，如 backend / frontend
# project_key: backend
```

也支持 YAML front matter 或单行 `knowledge_root: /path` / `knowledge_root=/path`；`project_root`、`project_key` 同理可用 `key: value` / `key=value`。**未配置 `project_root` 时，脚本与 Agent 须按上一节规则自动解析 `repo_root` 并以其绝对路径作为 `project_root`**，不要省略 `--repo-root` 或臆造路径。

模板见 [references/knowledge.md.example](./references/knowledge.md.example)。

**外部知识库目录结构**（`knowledge_root` 指向的目录）：

```text
/Users/you/work/knowledge/points-mall/
├── wiki/
├── raw/
└── README.md
```

### 核心约定

1. 知识库读写一律在 `knowledge_root` 下进行，不要读 skill 安装目录里的内容。
2. `knowledge/`（无论在本项目内还是外部路径）**只存放 wiki Markdown 与索引**，不含维护脚本。
3. 脚本在 skill 的 `scripts/` 目录运行，传入 `--repo-root` 指向当前项目配置所在目录；脚本会自动读取 `knowledge.md` 解析 `knowledge_root`，并在 `project_root` 未配置时按 `.git` / `--repo-root` 计算出 `repo_root` 作为 `project_root`。
4. 若项目尚未初始化知识库，**必须先向用户确认模式**（见下一节「首次创建与模式选择」），不要擅自假设本地或外部模式。

### 多项目共用知识库的冲突规避

当前端、后端等多个项目指向同一个外部 `knowledge_root` 时，必须把“共享 wiki”和“项目来源索引”分开处理：

1. 每个项目应在自己的 `knowledge.md` 配置稳定 `project_key`，例如后端 `backend`、前端 `frontend`。若未配置，脚本会用 `project_root` 目录名兜底，但目录改名可能影响后续引用。
2. 共享 wiki 页引用当前项目来源时可写普通相对路径；引用其他项目来源，或页面本身是跨端主题时，`source_refs` 使用 `project_key:path`，如 `backend:doc/order.md`、`frontend:src/api/order.ts`。
3. 外部模式下 `refresh_indexes.py` 只刷新 `raw/README.md` 中当前 `project_key` 的自动块，不删除其他项目块；不要手工改写其他项目的 raw 块。
4. `wiki/README.md` 是共享页面索引，可以由任一项目重新生成；它只扫描 `knowledge_root/wiki`，不扫描项目源码。
5. `lint_knowledge.py` 在外部共享模式下只校验当前项目相关页面和 raw 块；只引用其他项目来源的页面会被计入 skipped，不逐条输出 warning。
6. 同一页面被多端共同维护时，先保留对方来源与结论；若前后端事实冲突，用 `Open Question:` 标出，或新增 `decision` 页面记录最终取舍，不要直接覆盖。

## 首次创建与模式选择

当项目**尚未可用知识库**时（满足任一条件即视为未初始化），**必须先询问用户**选择本地模式或外部模式，再执行创建；不要跳过确认直接 bootstrap。

**未初始化判定**（按顺序检查）：

1. 已存在 `knowledge.md` 且配置了 `knowledge_root` → 路径已明确，可直接 bootstrap / 迁移（目录不存在时**可自动创建**）
2. 不存在 `knowledge.md`，且 `{repo_root}/knowledge/` 不存在或从未 bootstrap → **询问用户选模式**；若选外部模式，**必须先索取路径**
3. 已存在本地 `{repo_root}/knowledge/` 且有内容，用户明确要求改用外部知识库 → **走迁移流程**（见流程 C）；外部路径未明确前不得执行

**外部模式路径约束**（核心：路径须明确，而非禁止创建目录）：


| 情况                                            | 是否可创建外部知识库                                              |
| --------------------------------------------- | ------------------------------------------------------- |
| 用户**尚未提供**外部路径，且项目**无** `knowledge.md`        | **否** — 必须先询问用户索取绝对路径，不得猜测或默认路径                         |
| 用户**已回答**并提供绝对路径                              | **是** — 可写入 `knowledge.md` 并 bootstrap；目标目录不存在时**自动创建** |
| 项目**已有** `knowledge.md` 且配置了 `knowledge_root` | **是** — 视为路径已明确；目录不存在时**自动创建**                          |


**禁止的行为**：在用户未提供路径、且 `knowledge.md` 不存在/无有效 `knowledge_root` 时，擅自选定外部路径并创建知识库。

### 向用户确认（必做）

用简洁选项让用户选择：

```text
当前项目还没有可用的知识库。请选择：

A. 本地模式 — 知识库放在项目内 {repo_root}/knowledge/（仅当前项目使用）
B. 外部模式 — 知识库放在本机绝对路径（多个项目可共用，需你提供路径）
```

- 用户选 **A** → 执行「流程 A：创建本地知识库」
- 用户选 **B** → **必须**继续询问：`请提供外部知识库的绝对路径（例如 /Users/you/work/knowledge/my-product）`；**在用户给出路径之前，不得执行任何外部创建或 bootstrap 操作**
- 若用户已同时说明模式与路径 → 路径视为已明确，可直接进入流程 B；若项目已有 `knowledge.md` 配置了路径 → 可直接 bootstrap，无需重复询问

### 流程 A：创建本地知识库

适用：用户选择本地模式，且当前**没有**可用的本地知识库。

1. 执行 bootstrap：

```bash
python <skill>/scripts/knowledge_bootstrap.py --repo-root <项目>
```

1. 确认 `{repo_root}/knowledge/` 下已生成 `wiki/`、`raw/`、`README.md`；不要创建 `SCHEMA.md`。
2. 告知用户知识库位置：`{repo_root}/knowledge/`。
3. **不要**创建 `knowledge.md`（本地模式不需要该文件）。

### 流程 B：创建外部知识库

适用：用户选择外部模式；或项目已有 `knowledge.md` 配置了 `knowledge_root`。

**前置条件**：外部路径已明确（来自用户回答，或来自 `knowledge.md`）。未明确时停止并询问，不得猜测路径。

1. 取得 `EXTERNAL_ROOT`：
  - 用户刚提供 → 使用该绝对路径
  - 已有 `knowledge.md` → 读取其中 `knowledge_root`
2. 写入或更新 `{repo_root}/knowledge.md`（若尚未写入；建议提醒用户加入 `.gitignore`）：

```yaml
knowledge_root: <EXTERNAL_ROOT>
project_root: <项目绝对路径>
```

1. Bootstrap（**路径已明确时，目录不存在则自动创建**，并初始化 `wiki/`、`raw/`、`README.md` 等；不要创建 `SCHEMA.md`）：

```bash
python <skill>/scripts/knowledge_bootstrap.py --repo-root <项目> --knowledge-root <EXTERNAL_ROOT>
```

1. 创建完成后执行 `lint_knowledge.py --repo-root <项目> --allow-stale` 验证（无 wiki 页时也应通过）。

### 流程 C：本地知识库迁移到外部

适用：项目**已有**本地 `{repo_root}/knowledge/` 且含 wiki 内容，用户要求改为外部模式。

**顺序不可颠倒**：先创建外部知识库并同步，再切换配置；不要只写 `knowledge.md` 而遗漏内容迁移。

1. **向用户索取**外部绝对路径 `EXTERNAL_ROOT`（未提供则停止；若 `knowledge.md` 已配置则跳过）。
2. 执行迁移（外部目录不存在时**自动创建** → 复制本地内容 → 写入 `knowledge.md` → 规范化引用）：

```bash
python <skill>/scripts/migrate_local_knowledge.py \
  --repo-root <项目> \
  --knowledge-root <EXTERNAL_ROOT>
```

1. 迁移完成后执行：

```bash
python <skill>/scripts/lint_knowledge.py --repo-root <项目> --allow-stale
python <skill>/scripts/refresh_indexes.py --repo-root <项目>
```

（`migrate_local_knowledge.py` 会自动重算 wiki 页中对项目文件的链接 target，无需再手动改路径。）

1. **询问用户**是否删除本地 `{repo_root}/knowledge/`：
  - 用户确认删除时，才加 `--remove-local` 重新执行迁移脚本，或手动删除该目录
  - 用户未确认前，**保留**本地目录作为备份，不要擅自删除
2. 告知用户：此后 wiki 读写均在 `<EXTERNAL_ROOT>`；`source_refs` 可指向当前项目内的 `doc/`、`src/` 等路径，跨项目共享页使用 `project_key:path` 标明来源项目。

### 首次创建检查清单


| 步骤                        | 本地模式 | 外部模式（新建） | 外部模式（从本地迁移）                     |
| ------------------------- | ---- | -------- | ------------------------------- |
| 询问用户选模式                   | 是    | 是        | 是（确认改外部）                        |
| 路径已明确（用户回答或 knowledge.md） | —    | 是        | 是                               |
| 路径未明确时询问用户                | —    | 是（必做）    | 是（必做）                           |
| 路径明确后自动创建目录               | —    | 是        | 是                               |
| 写入 `knowledge.md`         | 否    | 是        | 是（脚本写入）                         |
| 同步已有本地内容                  | —    | 否        | 是（`migrate_local_knowledge.py`） |
| 删除本地 `knowledge/`         | 否    | 否        | 仅用户确认后                          |


## 何时使用

当用户有以下需求时，应触发这个 skill：

- 解释某个项目概念、业务域、流程或历史设计决策
- 在需求变更、代码变更、SQL 变更、脚本变更、事故复盘后更新知识库
- 新建知识页
- 对知识库做 lint 或刷新索引
- 沉淀可复用的 onboarding / 项目背景材料

## 核心规则

1. 用户要求把上下文结论沉淀到知识库时，先执行「沉淀写入前置门禁」；必须先确定目标子项目、最近配置文件、项目内或外部模式及唯一目标路径，再进行任何内容整理或写入。
2. 已初始化时，读 `{knowledge_root}/README.md` 与 skill 内 `references/schema.md`；若结构缺失，通过 `knowledge_bootstrap.py` 补全。**外部模式**下须先有明确路径（用户回答或 `knowledge.md`），再 bootstrap；路径明确后目录不存在可自动创建。不要在知识库内创建 `SCHEMA.md`。
3. 查询知识时优先按 `canonical -> reviewed -> draft` 的顺序使用 `{knowledge_root}/wiki`。
4. 如果 wiki 不足以支撑结论，再回退到 raw 文档和当前项目源码。
5. 遵守 schema 第 6、7 节的路径与可信度标注规则。
6. 不确定的内容必须显式标记为 `Inference:` 或 `Open Question:`。
7. **只要查询命中知识库，且最终回答使用了其中的信息，必须明确告知用户“该信息来自项目知识库”**；不得只在内部读取或仅通过文件链接暗示来源。若同时使用源码、设计文档等原始来源核对，应分别说明知识库结论与原始来源核对结果。
8. 使用本技能时，若从代码、SQL、配置、测试或正式设计文档等确定性来源确认了新的、已变化的或与 wiki 冲突的**可长期复用的项目事实**，在本次任务中自动更新已定位的知识库，无需等待用户另行提出“写入”要求。仅用于本次回答的细节、临时运行结果、未经核实的推断不触发自动写入；同一事实已准确记载时不重复编辑。

**典型场景**：用户问某张表在代码中如何使用。现有知识库没有这张表的相关信息时，先从 SQL、模型、读写代码等来源核实；回答用户的同时，在现有知识库中新增或补充相应的 `data-model` 等知识页，记录表的用途、实际读写路径和来源引用。无需用户再次要求更新知识库。

## 查询工作流

1. 先根据相关文件或当前目录确定目标子项目，再向上查找最近的 `knowledge.md`；若配置有效 `knowledge_root`，确定为外部模式并优先检索该外部知识库。仅在没有有效外部配置时，才使用该子项目内 `knowledge/`。
2. 外部配置存在时，即使项目内 `knowledge/` 也存在或外部查询未命中，也不得自动切换到项目内知识库。
3. 若检索结果为空，先做一次“目录发现防漏”兜底确认（见上文），避免被忽略规则误导。
4. 从已确定的 `{knowledge_root}/wiki/README.md` 开始定位页面。
5. 优先打开最相关的 `canonical` 或 `reviewed` 页面。
6. 如有需要，再结合 `{knowledge_root}/raw/README.md`、当前项目设计文档、SQL、脚本或源码做核对。
7. 输出结论时，要区分“来源可证实的事实”和“综合推断”。
8. 若最终回答采用了本次命中的 wiki 或 raw 信息，在结论开头或对应内容旁明确说明：`以下信息来自项目知识库`（可同时附相关知识页路径）。即使结论又经过源码或设计文档核对，也不能省略知识库来源声明。
9. 若第 6 步确认了值得长期复用且 wiki 尚未准确记载的项目事实，在回答结束前按「更新工作流」自动补充或修正知识页；回答中简要说明已更新的页面。知识库尚未初始化、模式或目标路径不明时，遵守写入门禁并询问用户，不向候选目录写入。

更细的流程说明见 [references/workflow.md](./references/workflow.md)。

## 更新工作流

1. **先执行「沉淀写入前置门禁」**，确定目标子项目、最近配置、项目内或外部模式及唯一 `knowledge_root`；未确定则停止并询问用户。
2. 再确认新增事实来自哪里：设计文档、SQL、脚本、代码变更、事故记录、发布检查单，或本轮上下文中已由用户确认的方案/流程。自动同步时以已核实的最终源码或文档状态为准，记录能直接支撑结论的来源路径；不要把推断升格为确定事实。
3. 将支撑结论的来源加入页面 `source_refs`；如需更新 `{knowledge_root}/raw/README.md` 来源索引，在页面更新后运行 `refresh_indexes.py`，不要手改自动生成块。
4. 如果已有页面覆盖该主题，就更新原页面；如果原页面会明显过载，就新建页面。
5. 新建页面时，可优先使用 skill 的 `new_page.py`（章节结构对齐 schema 模板）。
6. 更新 wiki 页面时，必须同步更新该页 `last_verified_at`；更新后通过 `lint_knowledge.py --repo-root <项目>` 校验。若页面仍使用旧版引用格式，先执行 `migrate_source_links.py`。
7. 如果页面索引发生变化，或外部模式下 `raw/README.md` 链接无法点击，再执行 `refresh_indexes.py`（raw 索引扫描当前项目的来源目录；外部模式只更新当前 `project_key` 的 raw 块，并写入绝对路径）。

## 质量要求

- 每个 wiki 页面都应包含符合 schema 的 front matter。
- `source_refs` 应指向当前项目或知识库内真实存在的文件或目录。
- 页面完成实质性复核或内容更新后，应更新 `last_verified_at`；超过 30 天未验证会被 lint 判为陈旧。
- 如果页面还不足以稳定复用，就保持 `draft`。

更细的质量标准见 [references/quality-bar.md](./references/quality-bar.md)。

## 附带脚本

以下脚本位于 **skill 安装目录**的 `scripts/` 下。传入 `--repo-root` 指向当前目标子项目的配置目录（即最近 `knowledge.md` 所在目录）；脚本读取该目录的配置解析外部 `knowledge_root`，也可用 `--knowledge-root` 显式覆盖。未显式传参时，脚本会从当前工作目录向上优先查找最近的 `knowledge.md`，再查找最近的本地 `knowledge/wiki/`，最后才使用 Git 根。


| 脚本                           | 作用                                                                                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `knowledge_bootstrap.py`     | 创建 `knowledge_root` 目录树；不会在知识库内创建 `SCHEMA.md`                                                                    |
| `migrate_local_knowledge.py` | 将本地 `{repo_root}/knowledge/` 迁移到外部路径，写入 `knowledge.md`，并规范化 wiki 引用                                              |
| `lint_knowledge.py`          | 校验 front matter、双根路径、链接 label、`Source:` 行、来源是否存在、`last_verified_at`；外部共享模式只检查当前 `project_key` 相关页面与 raw 块 |
| `migrate_source_links.py`    | 将 wiki 页源文件引用迁移为标准 Markdown 链接格式                                                                                 |
| `new_page.py`                | 按 schema 页面类型在 `knowledge_root/wiki/` 生成新页                                                                       |
| `refresh_indexes.py`         | 刷新 wiki 全局索引与 raw 项目索引；外部模式下 raw 只更新当前 `project_key` 块，避免覆盖其他项目                                             |


默认前提：**规范真源**在 skill 的 `references/schema.md`；**知识实例**在 `knowledge_root`（本地或外部绝对路径，仅 Markdown 内容与索引）。
