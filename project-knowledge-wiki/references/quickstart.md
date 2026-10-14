# Quickstart

用于查询或轻量更新知识库时的最小流程。完整结构、front matter 与引用规则见 `schema.md`；只有新建、批量修改、迁移或 lint 失败时才需要展开阅读完整 schema。

## 写入门禁

用户要求沉淀已确定的结论，或本技能使用中从确定性来源确认了需自动同步的项目事实时，写入前先确定模式和唯一目标路径：

1. 先根据用户指定目录、相关源文件或当前目录确定目标子项目；从该位置向上查找最近的 `knowledge.md`，不要只检查最外层 Git 根。
2. 最近配置含有效绝对路径 `knowledge_root` 时，确定为外部模式并优先使用外部知识库，即使子项目内 `knowledge/` 同时存在也不视为冲突。
3. 仅在向上没有有效配置时，才查找最近的项目内 `knowledge/`。
4. 明确告知用户目标子项目、配置文件、写入模式与路径。
5. 一次涉及多个子项目时分别解析；范围无法唯一确定时先询问用户。
6. 未初始化、配置无效或用户意图与配置冲突时，先询问用户；外部模式必须取得绝对路径。
7. 确认前不得选页、建页、登记 raw source、bootstrap、迁移、刷新索引或写入任何候选目录。

## 定位知识库

1. 确定查找起点：显式子项目目录 > 当前处理文件目录 > 当前目录。
2. 从起点向上查找最近的 `knowledge.md`；其所在目录作为脚本 `repo_root` / `config_root`。未找到配置时再查找最近的 `knowledge/wiki/`，最后才回退 Git 根。
3. 读取最近的 `knowledge.md`：
   - 有有效的绝对路径 `knowledge_root`：使用并优先检索该外部知识库；不得因项目内 `knowledge/` 同时存在或外部查询未命中而自动回退。
   - 无有效 `knowledge_root`：再检查并使用 `{repo_root}/knowledge/`。
   - 有 `project_root`：项目源码以它为准；否则 `project_root = repo_root`。
   - 有 `project_key`：共享库项目命名空间以它为准；否则使用 `project_root` 目录名。

## 查询顺序

1. 先按目标子项目和最近配置确定 `knowledge_root`；外部配置有效时，先读外部 `{knowledge_root}/wiki/README.md` 找入口。
2. 优先读相关 `canonical` 页面，其次 `reviewed`，最后 `draft`。
3. wiki 不足时再读 `{knowledge_root}/raw/README.md`。
4. 仍不足时回到当前项目的设计文档、SQL、脚本或源码。
5. 只要最终回答采用了命中的 wiki 或 raw 信息，必须明确告诉用户“该信息来自项目知识库”；如又核对了源码或设计文档，分别说明知识库来源和核对结果。
6. 从代码、SQL、配置、测试或正式设计文档确认了可长期复用的新事实、变更或 wiki 错误时，在本次任务结束前自动更新已定位的 wiki 页面，并附来源；事实已准确记载则无需改动。临时细节与未经核实的推断不自动写入。知识库未初始化或写入路径不明时，按写入门禁询问用户。

例如：查询某张表在代码中的用法，知识库已有但缺少该表信息；查明表的用途和实际读写路径后，自动新增或补充知识页，再完成答复。

## 共享库约定

- 外部共享库中，`source_refs` 可写 `project_key:path`，例如 `backend:doc/order.md`、`frontend:src/api/order.ts`。
- 从当前项目运行 lint 时，只检查当前 `project_key` 相关页面与 raw 块；其他项目页面由所属项目校验。
- `refresh_indexes.py` 在外部模式下只刷新当前 `project_key` 的 raw 自动块，不覆盖其他项目块。

## 常用命令

```bash
python <skill>/scripts/lint_knowledge.py --repo-root <项目> --allow-stale
python <skill>/scripts/refresh_indexes.py --repo-root <项目>
python <skill>/scripts/new_page.py <type> "<title>" --repo-root <项目> --source-ref <path>
```
