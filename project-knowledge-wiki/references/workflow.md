# 工作流

路径、front matter 与引用格式以 [schema.md](./schema.md) 为准。

## 查询流程

回答项目问题时，按这个顺序查找：

0. 确定当前项目根目录，并确保该根目录下存在 `knowledge/`；若不存在，通过 skill 的 `knowledge_bootstrap.py --repo-root <项目>` 触发 bootstrap（会写入 `SCHEMA.md`）。**不要**把 skill 脚本复制到项目 `knowledge/` 中。
1. `knowledge/wiki/README.md`
2. 相关 `canonical` 页面
3. 相关 `reviewed` 页面
4. `knowledge/raw/README.md`
5. 原始设计文档、SQL、脚本、源码

如果 wiki 与原始来源冲突，优先以源码和正式设计文档为准，并随后回写 wiki。

## 新增或更新知识

1. Confirm what changed.
2. Locate the source artifact.
3. 决定是更新已有页面，还是新建页面。
4. `source_refs` / `related_pages` 使用仓库根目录相对路径。
5. 为每个 `source_refs` / `related_pages` 条目在正文添加可跳转 Markdown 链接；所有源文件引用使用标准格式，label 为 repo-root 相对路径，target 相对当前 wiki 文件（见 schema 第 6 节）。
6. 结论不确定时添加 `Open Question:`。
7. 每次更新 wiki 页面内容时，同步更新该页 `last_verified_at`。
8. 通过 skill 的 `lint_knowledge.py --repo-root <项目>` 校验（校验项与 schema 第 4、6、8.3 节一致）。
9. 如果页面使用了旧版引用格式，通过 skill 的 `migrate_source_links.py` 迁移后再 lint。
10. 如果页面索引发生变化，再执行 skill 的 `refresh_indexes.py`。

## 页面状态提升

- `draft`：新建或尚不完整的页面
- `reviewed`：已经足够稳定，可重复参考
- `canonical`：当前主题下最推荐优先阅读的入口页

除非页面已经稳定且来源充分，否则不要升级为 `canonical`。
