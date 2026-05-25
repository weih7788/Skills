# 质量标准

完整字段、引用与模板约定见 [schema.md](./schema.md)。

## 硬性要求

- wiki 页面必须包含 YAML front matter（必填键见 schema 第 4 节）
- `source_refs` 必须使用“相对仓库根目录”路径，且非空；外部共享知识库中的跨项目来源使用 `project_key:相对路径`
- `related_pages` 必须使用“相对仓库根目录”的 wiki 路径
- `source_refs` 和 `related_pages` 中的每一项，都必须在正文中有可跳转 Markdown 链接（label 与 front matter 路径一致）；分别用 `Source:` / `Ref:` 前缀
- 正文中**所有**源文件引用必须使用标准 Markdown 链接格式：`[repo-root-path](relative-from-current-wiki-page)`
- 正文中 Markdown 链接 **label** 必须使用相对仓库根目录的路径，或外部共享模式的 `project_key:相对路径`，格式与 `source_refs` 一致
- 正文中 Markdown 链接 **target** 必须相对当前文件、且能解析到仓库内真实路径
- `Source:` 行必须以 Markdown 链接开头；可在链接后附加说明文字
- 引用的来源文件应真实存在
- 每次更新 wiki 页面内容时，必须同步更新该页 `last_verified_at`
- `last_verified_at` 超过 30 天会被视为陈旧知识，需要复核后刷新日期
- 不确定内容必须显式标记 `Inference:` 或 `Open Question:`
- 项目 `knowledge/` 不存放维护脚本；bootstrap、lint、迁移等脚本只在 skill 的 `scripts/` 目录中

## 好的 wiki 行为

- 短而结构化的总结优于长篇原文搬运
- 一页只表达一个清晰主题
- 尽量通过页面间链接复用上下文，而不是重复粘贴
- `canonical` 要谨慎使用

## 常见失败模式

- `source_refs` 写成绝对路径、`./` 或 `../`
- front matter 中登记了 `source_refs` / `related_pages`，但正文没有 label 一致的可跳转链接
- `Ref:` 行使用纯文本路径，而不是 Markdown 链接
- `Source:` 行使用纯文本路径或仅反引号路径，而不是 Markdown 链接
- 链接 label 只写 `foo.md` 等纯文件名（应写完整 repo-root 路径，如 `doc/design/foo.md`）
- 链接 target 未按当前 Markdown 文件位置计算，导致 IDE 无法跳转
- `knowledge.md` 未配置 `project_root` 时，Agent 未解析 `repo_root` 就手写 `../../../` 猜测项目路径（应传 `--repo-root` 或按 `.git` 自动解析）
- 多项目共用外部知识库时未配置稳定 `project_key`，导致 raw 索引或跨项目 `source_refs` 难以区分来源项目
- **外部模式**下 `raw/README.md` 使用 `../../../project/...` 相对 target（知识库在仓库外时 IDE 通常无法点击；应运行 `refresh_indexes.py` 生成 `<project_root 绝对路径>`）
- `raw/README.md` 索引行缺少 `Source:` 前缀，或手改 `AUTO-GENERATED` 块导致与 `refresh_indexes.py` 输出格式不一致
- 外部共享模式下手工覆盖 `raw/README.md` 的其他项目自动块；应只让 `refresh_indexes.py` 刷新当前 `project_key` 块
- 外部共享模式下从当前项目 lint 时逐条提示其他项目页面路径不存在；应只校验当前项目相关页面，其他项目页面由所属项目 lint
- 页面逐渐变成 changelog，而不是知识页
- 页面内容已更新但 `last_verified_at` 仍停留在旧日期
- 推断行为被误写成事实
- 来源链接只指向 wiki，而没有回到 raw source
