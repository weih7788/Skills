# Skills

这是一个用于集中维护和同步 Agent Skills 的仓库。仓库中的 skill 可以通过 `sync.sh` 以符号链接的方式安装到不同 AI 工具的项目级或全局技能目录中，避免在多个工具各自的私有路径下重复维护同一份内容。

当前仓库主要包含 `project-knowledge-wiki`、`plan`、`run` 和 `review`：`project-knowledge-wiki` 用于帮助 Agent 查询、生成和维护项目内的 `knowledge/` 知识库，`plan` 用于在实现前产出可评审的技术方案和改动预案，`run` 用于承接方案并完成实现、验证和交付闭环，`review` 用于审查最近代码或方案修改中的明显 bug、潜在风险和验证缺口。

## 目录结构

```text
.
├── project-knowledge-wiki/      # 项目知识库维护 skill
│   ├── SKILL.md                 # skill 入口说明与执行规则
│   ├── agents/openai.yaml       # 面向 OpenAI/Agent 平台的界面描述
│   ├── references/              # 工作流、页面类型和质量标准
│   └── scripts/                 # 知识库页面生成、lint、索引刷新脚本
├── plan/                        # 实现前技术方案 skill
├── run/                         # 按方案实现与验证 skill
├── review/                      # 最近改动风险审查 skill
└── sync.sh                      # 将本仓库 skill 同步到目标 AI 工具目录
```

## 核心能力

- 统一维护技能：在本仓库编辑 skill，再同步到 Codex、Claude、Cursor 或 Antigravity。
- 按 AI 工具解析安装路径：支持项目级目录、全局目录和自定义目标目录。
- 选择性同步：可以只同步某一个 skill，适合逐步发布或局部调试。
- 实现前方案化：`plan` 会引导 Agent 先阅读代码，再输出改动范围、取舍、before / after 和验证计划。
- 方案后执行闭环：`run` 会承接已明确的方案，按范围实现代码、执行验证并说明偏差和剩余风险。
- 最近改动审查：`review` 会分析上下文、未提交改动或最新提交，列出风险项、原因和建议，但不擅自修改代码或方案。
- 知识库维护辅助：`project-knowledge-wiki` 提供页面模板、规范校验和索引刷新脚本，帮助把项目事实沉淀到仓库本地的 `knowledge/`。

## 当前 Skill

### `project-knowledge-wiki`

用于维护当前项目仓库内的 LLM Wiki，知识内容始终写入“正在工作的项目根目录”下的 `knowledge/`，而不是 skill 自身目录。

适用场景：

- 查询项目概念、业务域、流程或历史设计决策。
- 在需求、代码、SQL、脚本或事故复盘后更新项目知识库。
- 新建知识页，并为页面补齐来源、状态和关联页面。
- 对知识库执行 lint 和索引刷新。

附带脚本：

```bash
python project-knowledge-wiki/scripts/new_page.py concept "Example Concept"
python project-knowledge-wiki/scripts/lint_knowledge.py
python project-knowledge-wiki/scripts/refresh_indexes.py
```

这些脚本默认会从当前目录向上寻找 Git 仓库根目录；如果从其他目录调用，可以传入 `--repo-root /path/to/project`。

### `plan`

用于在实现产品需求、重构、架构调整或复杂代码修改前，先产出可评审、可执行的技术方案。

适用场景：

- 用户要求先给技术方案、实现规划、改动预案或风险评估。
- 改动跨多个模块、文件或协作边界，需要先明确范围。
- 需要展示关键代码 before / after，帮助评审者理解行为变化。
- 涉及数据迁移、接口兼容、权限、安全、发布或回滚风险。

`plan/SKILL.md` 是入口规则，`plan/references/` 保存输出模板和写作风格约束。

### `run`

用于在 `plan` 或其他方式已经形成相对完整方案后，按方案落地实现、补齐验证，并在交付时说明结果。

适用场景：

- 用户要求按已有方案实现、继续编码、修复代码或完成验证闭环。
- 已经有 `plan` 输出、设计文档、任务清单或明确实现范围。
- 需要在实现中跟踪方案偏差，并说明调整原因和影响。
- 需要最终汇报完成内容、验证结果、未覆盖风险和下一步 review 重点。

`run/SKILL.md` 是入口规则，`run/references/` 保存执行流程和交付汇报约束。

### `review`

用于审查代码或方案的最近一次修改，判断是否存在明显 bug、潜在风险、遗漏验证或实现偏差，并以风险项、原因和建议的形式输出结论。

适用场景：

- 用户要求 review、审查、检查最新提交或未提交改动。
- 需要分析上下文中的方案修改是否有逻辑漏洞、范围偏差或落地风险。
- 需要在实现后进入代码审查视角，优先找行为回归、数据一致性、安全、兼容性、并发幂等和边界条件问题。
- 用户只希望获得风险和建议，不希望 Agent 擅自修改代码、方案或测试。

`review/SKILL.md` 是入口规则，`review/agents/openai.yaml` 提供面向 OpenAI/Agent 平台的界面描述。

## 同步用法

`sync.sh` 会扫描 source 目录下第一层、且包含 `SKILL.md` 的目录，并将它们链接到目标技能目录。

同步到某个项目：

```bash
./sync.sh --ai cursor --project /path/to/project
./sync.sh --ai codex --project /path/to/project
./sync.sh --ai claude --project /path/to/project
./sync.sh --ai antigravity --project /path/to/project
```

同步到全局目录：

```bash
./sync.sh --ai cursor --global
./sync.sh --ai codex --global
```

只同步指定 skill：

```bash
./sync.sh --ai cursor --global --only project-knowledge-wiki
```

预览操作但不实际修改：

```bash
./sync.sh --ai cursor --project /path/to/project --dry-run
```

常用选项：

- `--source <dir>`：指定 skill 来源目录，默认是当前目录。
- `--target <dir>`：跳过 AI 工具路径解析，直接同步到指定目录。
- `--only <path>`：只同步某个第一层 skill 目录，可重复传入。
- `--force`：替换目标位置已有文件、目录或符号链接。
- `--prune`：清理目标目录中已经失效的旧符号链接。
- `--dry-run`：仅打印将要执行的动作。

## 维护建议

新增 skill 时，建议以一个独立目录承载，并在目录下提供 `SKILL.md`。只有包含 `SKILL.md` 的第一层目录才会被 `sync.sh` 识别为可同步 skill。

更新 `project-knowledge-wiki` 时，优先保持规则、参考文档和脚本之间一致：`SKILL.md` 描述执行入口，`references/` 承载细则，`scripts/` 提供可重复执行的工具。
