# 质量标准

## 硬性要求

- wiki 页面必须包含 YAML front matter
- `title`、`type`、`status`、`owner`、`last_verified_at`、`source_refs`、`related_pages` 必须存在
- `source_refs` 必须使用“相对仓库根目录”路径
- 引用的来源文件应真实存在
- 不确定内容必须显式标记

## 好的 wiki 行为

- 短而结构化的总结优于长篇原文搬运
- 一页只表达一个清晰主题
- 尽量通过页面间链接复用上下文，而不是重复粘贴
- `canonical` 要谨慎使用

## 常见失败模式

- source path 写成绝对路径或机器相关路径
- 页面逐渐变成 changelog，而不是知识页
- 推断行为被误写成事实
- 来源链接只指向 wiki，而没有回到 raw source
