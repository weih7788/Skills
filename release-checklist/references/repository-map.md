# 后端发布范围与 Git 取证

## 默认仓库

`${WORKSPACE_ROOT}` 表示本机后端仓库的父目录。先从当前工作区和常用开发目录确认后端仓库真实位置。下表路径只是查找线索，运行前必须验证。

| 端 | 仓库 | 本机路径 | 默认基线 | 用户每次必须提供 |
|---|---|---|---|---|
| 后端 | `cube-control-desk` | `${WORKSPACE_ROOT}/cube-control-desk` | `preview` | 发布分支或“无改动/不发布” |

默认基线为 `preview`，用户可覆盖。运行前验证后端仓库、基线和目标 ref；不要求提供或读取前端、集群仓库。

## Ref 解析

优先解析用户指定的准确名称，记录最终采用的完整 ref 和 SHA：

```bash
git -C <repo> show-ref --verify refs/heads/<branch>
git -C <repo> show-ref --verify refs/remotes/origin/<branch>
git -C <repo> rev-parse <resolved-ref>^{commit}
```

用户明确指定“当前分支”时采用本地 HEAD 并记录 SHA。其他情况下，本地分支和远端跟踪分支同时存在但 SHA 不同且用户未写明 `origin/` 时，展示两个 SHA 并要求用户确认，不能静默任选其一。默认基线可优先使用存在的远端跟踪 ref，但要在发布范围表中写明。没有用户授权时不要 checkout、merge、rebase 或把工作区未提交内容混入分支 diff。

## Diff 范围

```bash
TASK_BASE_SHA=$(git -C <repo> rev-parse <base-ref>^{commit})
TASK_TARGET_SHA=$(git -C <repo> rev-parse <target-ref>^{commit})
TASK_MERGE_BASE=$(git -C <repo> merge-base "$TASK_BASE_SHA" "$TASK_TARGET_SHA")
git -C <repo> log "$TASK_MERGE_BASE..$TASK_TARGET_SHA" --oneline --decorate
git -C <repo> diff "$TASK_MERGE_BASE..$TASK_TARGET_SHA" --stat
git -C <repo> diff "$TASK_MERGE_BASE..$TASK_TARGET_SHA" --name-status --find-renames
git -C <repo> diff "$TASK_MERGE_BASE..$TASK_TARGET_SHA" --find-renames
```

### 合入基线后发布的增量

本项目默认将迭代来源分支合入对应基线，发布合并后的基线；用户明确指定其他方式时遵从用户。上面的 merge-base diff 用于找出来源分支的候选增量，需求判断须结合基线已有能力。基线有而来源分支未包含的改动，不直接判为遗漏或回退。

可用 `git merge-tree --write-tree <base-ref> <target-ref>` 做模拟合并，不 checkout，不实际合并或创建发布分支。记录退出状态、树 SHA 和冲突；无冲突时以 `git diff <base-sha> <merged-tree>` 复核正式发布净增量。冲突文件不能当成已解决版本，须说明待保留的两侧能力，并在真实合并提交上复核。用户同意创建验证分支且确有需要时，再创建隔离的验证分支。

继承的基线能力计入需求覆盖，但不重复列入本次 SQL、脚本和配置发布操作。commit 归属以该提交实际 diff 为准，不能将分支全部变化归到分支头提交。

## 后端分类信号

- Controller/OpenAPI 契约、manager/provider/strategy/job/callback。
- service/mapper/entity/DTO/VO/enum、SQL、Groovy、配置和测试。
- 数据兼容、任务状态、回调幂等、配置/脚本同步。

## 疑似污染信号

以下只是调查入口，不是自动定罪规则：

- commit message、目录或业务域明显属于其他迭代。
- 大段格式化/重命名掩盖业务 diff，或无需求依据的依赖升级和公共重构。
- 调试接口、硬编码环境/租户、临时日志、mock、注释掉的关键逻辑。
- 构建产物、IDE 文件、缓存、测试数据或真实凭据误入分支。
- 后端外部契约变更缺少兼容处理；外部实现是否匹配仅列待确认依赖，不据此断言其他端遗漏或污染。

必要的测试、迁移、兼容、日志和配套重构应映射为需求的实现支撑，不应机械判为污染。
