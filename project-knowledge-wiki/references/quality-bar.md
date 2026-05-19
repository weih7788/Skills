# 质量标准

完整字段、引用与模板约定见 [schema.md](./schema.md)。

## 硬性要求

- wiki 页面必须包含 YAML front matter（必填键见 schema 第 4 节）
- `source_refs` 必须使用“相对仓库根目录”路径，且非空
- `related_pages` 必须使用“相对仓库根目录”的 wiki 路径
- 正文中 Markdown 链接 **label** 仅写文件名，不得含 `/` 或 `\`
- 正文中 Markdown 链接 **target** 必须相对当前文件、且能解析到仓库内真实路径
- 引用的来源文件应真实存在
- 不确定内容必须显式标记 `Inference:` 或 `Open Question:`

## 好的 wiki 行为

- 短而结构化的总结优于长篇原文搬运
- 一页只表达一个清晰主题
- 尽量通过页面间链接复用上下文，而不是重复粘贴
- `canonical` 要谨慎使用

## 常见失败模式

- `source_refs` 写成绝对路径、`./` 或 `../`
- 链接 label 写成 `doc/design/foo.md` 等带目录路径（应只写 `foo.md`）
- 链接 target 未按当前 Markdown 文件位置计算，导致 IDE 无法跳转
- 页面逐渐变成 changelog，而不是知识页
- 推断行为被误写成事实
- 来源链接只指向 wiki，而没有回到 raw source
