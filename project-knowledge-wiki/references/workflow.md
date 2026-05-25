# 工作流

查询或轻量补充知识时优先使用 [quickstart.md](./quickstart.md)。路径、front matter 与引用格式的完整规则以 [schema.md](./schema.md) 为准。

## 知识库定位

每次操作前先解析双根：

1. `repo_root`：当前 Git 项目根 — `--repo-root`（显式）→ 从 cwd 向上找 `.git` → cwd 的绝对路径
2. `project_root`：项目源文件根 — `knowledge.md` 的 `project_root`；**未配置时自动等于上一步解析出的 `repo_root`**
3. `knowledge_root`：`knowledge.md` 配置的绝对路径，或 fallback 到 `{repo_root}/knowledge/`
4. `project_key`：多项目共用外部知识库时的项目命名空间 — `knowledge.md` 的 `project_key`，未配置时用 `project_root` 目录名

**Agent 必做**：即使 `knowledge.md` 只配置了 `knowledge_root`、没有 `project_root`，也须通过上述规则自行算出项目绝对路径；运行脚本时传 `--repo-root <含 knowledge.md 的项目目录>`，不要手写 `../../../` 猜测源码位置。

若项目尚未初始化知识库，**必须先向用户确认本地或外部模式**；外部模式须先取得明确路径（用户回答或 `knowledge.md`），**不得在路径未明确时擅自创建**；路径明确后目录不存在可自动 bootstrap。

若本地已有 `knowledge/` 且用户要改外部，使用 `migrate_local_knowledge.py` 同步（须提供或已配置外部路径）。

## 查询流程

回答项目问题时，按这个顺序查找：

1. `{knowledge_root}/wiki/README.md`
2. 相关 `canonical` 页面
3. 相关 `reviewed` 页面
4. `{knowledge_root}/raw/README.md`
5. 当前项目的原始设计文档、SQL、脚本、源码

如果 wiki 与原始来源冲突，优先以源码和正式设计文档为准，并随后回写 wiki。

## 新增或更新知识

1. Confirm what changed.
2. Locate the source artifact in the current project (`project_root`).
3. 决定是更新已有页面，还是新建页面（写入 `{knowledge_root}/wiki/`）。
4. `source_refs` 使用当前项目相对路径（如 `doc/design/foo.md`）；外部共享知识库中跨项目页面使用 `project_key:相对路径`（如 `backend:doc/design/foo.md`、`frontend:src/api/foo.ts`）；`related_pages` 使用 `wiki/...`（外部模式）或 `knowledge/wiki/...`（本地模式）。
5. 为每个 `source_refs` / `related_pages` 条目在正文添加可跳转 Markdown 链接；label 与 front matter 一致，target 相对当前 wiki 文件（见 schema 第 6 节）。
6. 结论不确定时添加 `Open Question:`。
7. 每次更新 wiki 页面内容时，同步更新该页 `last_verified_at`。
8. 通过 skill 的 `lint_knowledge.py --repo-root <项目>` 校验（外部共享模式下只检查当前项目相关页面与 raw 块；校验项与 schema 第 4、6、8.3 节一致）。
9. 如果页面使用了旧版引用格式，通过 skill 的 `migrate_source_links.py` 迁移后再 lint。
10. 如果页面索引发生变化，再执行 skill 的 `refresh_indexes.py`（wiki 索引全局刷新；外部模式 raw 索引只刷新当前 `project_key` 的自动块）。
11. **外部模式 raw 链接排查**：若 `raw/README.md` 中项目源文件链接无法点击，检查 target 是否为 `project_root` 绝对路径；若是 `../../../` 相对路径，运行 `refresh_indexes.py` 重新生成（见 schema 第 6.3 节）。

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
