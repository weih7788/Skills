# Quickstart

用于查询或轻量更新知识库时的最小流程。完整结构、front matter 与引用规则见 `schema.md`；只有新建、批量修改、迁移或 lint 失败时才需要展开阅读完整 schema。

## 定位知识库

1. 解析 `repo_root`：优先使用脚本 `--repo-root`；否则从当前目录向上找 `.git`；再否则使用当前目录绝对路径。
2. 读取 `{repo_root}/knowledge.md`：
   - 有 `knowledge_root`：使用该外部知识库。
   - 无 `knowledge_root`：使用 `{repo_root}/knowledge/`。
   - 有 `project_root`：项目源码以它为准；否则 `project_root = repo_root`。
   - 有 `project_key`：共享库项目命名空间以它为准；否则使用 `project_root` 目录名。

## 查询顺序

1. 读 `{knowledge_root}/wiki/README.md` 找入口。
2. 优先读相关 `canonical` 页面，其次 `reviewed`，最后 `draft`。
3. wiki 不足时再读 `{knowledge_root}/raw/README.md`。
4. 仍不足时回到当前项目的设计文档、SQL、脚本或源码。

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
