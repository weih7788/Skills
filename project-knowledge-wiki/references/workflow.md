# 工作流

## 查询流程

回答项目问题时，按这个顺序查找：

0. 确定当前项目根目录，并确保该根目录下存在 `knowledge/`；如果不存在，先创建最小知识库结构。
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
4. 保持 `source_refs` 为“相对仓库根目录”路径。
5. 正文中指向项目源文件的 Markdown 链接，链接文本使用“相对仓库根目录”路径，链接目标使用从当前 Markdown 文件可跳转到源文件的相对路径，例如 `knowledge/raw/README.md` 中写 `[doc/foo.md](../../doc/foo.md)`。
6. 如果结论仍不完全确定，添加 `Open Question:`。
7. 执行 lint。
8. 页面目录变化后刷新索引。

## 页面状态提升

- `draft`：新建或尚不完整的页面
- `reviewed`：已经足够稳定，可重复参考
- `canonical`：当前主题下最推荐优先阅读的入口页

除非页面已经稳定且来源充分，否则不要升级为 `canonical`。
