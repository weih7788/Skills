# 工作流

查询或轻量补充知识时优先使用 [quickstart.md](./quickstart.md)。路径、front matter 与引用格式的完整规则以 [schema.md](./schema.md) 为准。

## 知识库定位

每次操作前先确定目标子项目并解析多根：

1. `workspace_root`：最外层工作区或 Git 集合根，只作为搜索边界
2. `config_root` / 脚本 `repo_root`：从目标文件或子项目目录向上找到的最近 `knowledge.md` 所在目录；没有配置时为最近本地 `knowledge/` 的父目录
3. `project_root`：项目源文件根 — `knowledge.md` 的 `project_root`；**未配置时自动等于 `config_root`**
4. `knowledge_root`：读取最近的 `knowledge.md`；其中配置有效绝对路径时使用外部知识库，否则才 fallback 到 `{config_root}/knowledge/`
5. `project_key`：多项目共用外部知识库时的项目命名空间 — `knowledge.md` 的 `project_key`，未配置时用 `project_root` 目录名

**子项目发现顺序**：显式目标子项目 > 当前处理文件所在子项目 > cwd；从起点向上逐级找最近的 `knowledge.md`，不要只读 Git 根。若任务覆盖多个子项目，逐个解析；若无法唯一判断目标范围，先询问用户。

**外部配置是权威入口**：`knowledge.md` 配置了有效 `knowledge_root` 时，先检索外部知识库。即使项目内 `knowledge/` 同时存在，也不询问二选一、不优先检索项目内目录；外部查询未命中或目录异常时也不自动回退，除非用户明确要求恢复、迁移或改回项目内模式。

**Agent 必做**：即使最近的 `knowledge.md` 只配置了 `knowledge_root`、没有 `project_root`，也须使用 `config_root` 作为项目绝对路径；运行脚本时传 `--repo-root <该 knowledge.md 所在目录>`，不要固定传最外层 Git 根，也不要手写 `../../../` 猜测源码位置。

若项目尚未初始化知识库，**必须先向用户确认本地或外部模式**；外部模式须先取得明确路径（用户回答或 `knowledge.md`），**不得在路径未明确时擅自创建**；路径明确后目录不存在可自动 bootstrap。

若本地已有 `knowledge/` 且用户要改外部，使用 `migrate_local_knowledge.py` 同步（须提供或已配置外部路径）。

## 查询流程

回答项目问题时，按这个顺序查找：

1. 根据相关文件或当前目录确定目标子项目，向上找到最近的 `knowledge.md`；有效外部配置存在时锁定外部 `knowledge_root`，否则才使用该子项目内 `knowledge/`
2. 已确定的 `{knowledge_root}/wiki/README.md`
3. 相关 `canonical` 页面
4. 相关 `reviewed` 页面
5. `{knowledge_root}/raw/README.md`
6. 当前项目的原始设计文档、SQL、脚本、源码

从代码、SQL、配置、测试或正式设计文档确认了可长期复用的新事实、变更或 wiki 错误时，按下方更新流程在本次任务中自动补充或修正知识页，并保留可核对的来源路径。wiki 与原始来源冲突时，以已核实的原始来源为准。已准确记载的事实无需重复编辑；临时细节和未经核实的推断不自动写入。知识库尚未初始化或目标路径不明时先执行写入门禁，不写入候选目录。

只要最终回答采用了本次查询命中的 wiki 或 raw 信息，必须明确告知用户“该信息来自项目知识库”，不能仅靠链接或内部检索过程暗示。若同时参考了源码、设计文档等原始来源，应分别说明知识库提供的结论和原始来源的核对结果。

## 新增或更新知识

1. **先确定知识库模式和唯一目标路径**：先确定目标子项目并向上查找最近的 `knowledge.md`；配置有效 `knowledge_root` 时直接确定为外部模式并优先使用外部知识库，子项目内 `knowledge/` 同时存在不构成冲突。仅在没有有效外部配置时才检查项目内目录。多子项目任务分别解析；范围不明、未初始化、配置无效或用户意图与配置冲突时先询问用户。确认前不得选择页面、登记来源、bootstrap、迁移、刷新索引或写入。
2. Confirm what changed，包括本轮上下文中已由用户确认的方案、流程或决策。
3. Locate the source artifact in the current project (`project_root`).
4. 决定是更新已有页面，还是新建页面（写入 `{knowledge_root}/wiki/`）。
5. `source_refs` 使用当前项目相对路径（如 `doc/design/foo.md`）；外部共享知识库中跨项目页面使用 `project_key:相对路径`（如 `backend:doc/design/foo.md`、`frontend:src/api/foo.ts`）；`related_pages` 使用 `wiki/...`（外部模式）或 `knowledge/wiki/...`（本地模式）。
6. 为每个 `source_refs` / `related_pages` 条目在正文添加可跳转 Markdown 链接；label 与 front matter 一致，target 相对当前 wiki 文件（见 schema 第 6 节）。
7. 结论不确定时添加 `Open Question:`。
8. 每次更新 wiki 页面内容时，同步更新该页 `last_verified_at`。
9. 通过 skill 的 `lint_knowledge.py --repo-root <项目>` 校验（外部共享模式下只检查当前项目相关页面与 raw 块；校验项与 schema 第 4、6、8.3 节一致）。
10. 如果页面使用了旧版引用格式，通过 skill 的 `migrate_source_links.py` 迁移后再 lint。
11. 如果页面索引发生变化，再执行 skill 的 `refresh_indexes.py`（wiki 索引全局刷新；外部模式 raw 索引只刷新当前 `project_key` 的自动块）。
12. **外部模式 raw 链接排查**：若 `raw/README.md` 中项目源文件链接无法点击，检查 target 是否为 `project_root` 绝对路径；若是 `../../../` 相对路径，运行 `refresh_indexes.py` 重新生成（见 schema 第 6.3 节）。

## 多项目共享更新流程

前端、后端等多个项目共用同一外部 `knowledge_root` 时，按下面顺序处理，避免互相覆盖：

1. 先确认当前项目的 `knowledge.md` 是否有稳定 `project_key`；没有时建议补上。
2. 只在当前项目根运行脚本，并显式传 `--repo-root <当前项目>`。
3. 更新共享 wiki 页时，保留已有其他项目的 `source_refs`；新增跨项目来源使用 `project_key:path`。
4. 刷新索引时运行 `refresh_indexes.py`，让脚本只替换当前项目的 raw 自动块；不要手改或删除其他项目块。
5. 运行 lint 时只处理当前 `project_key` 相关页面；其他项目页面在摘要中显示 skipped，不需要逐条处理。
6. 如果同一页面出现前后端结论冲突，先写 `Open Question:` 或补一页 `decision`，不要把对方结论直接改没。

## 页面状态提升

- `draft`：新建或尚不完整的页面
- `reviewed`：已经足够稳定，可重复参考
- `canonical`：当前主题下最推荐优先阅读的入口页

除非页面已经稳定且来源充分，否则不要升级为 `canonical`。
