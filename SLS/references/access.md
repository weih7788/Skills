# 连接与本地回退

优先调用已加载的阿里云 SLS MCP 工具。代理 `alibabacloud-sls-mcp-proxy` 通过环境变量 `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 或已配置的本地凭证运行；本机 `SLS/private-credentials.env` 已保存私密凭证，`query.py` 在环境变量未提供凭证时自动读取。该文件权限为 `0600` 且受 Git 忽略，不要在 Markdown 或终端输出密钥值。若需新配置 Codex MCP，保留现有 `$CODEX_HOME/config.toml` 内容，合并同名 server 配置并重启或重新加载。只有真实查询成功才报告连接成功。

工具没有加载而本机已安装该代理时，可使用 `scripts/query.py` 通过代理做一次性只读查询。脚本调用代理的 stdio MCP 接口，默认只输出元数据；`--include-message` 默认输出原文前 2000 字符并标明是否截断。定位核心日志后，用 `--full-message` 和日志时间、类名、trace_id 过滤，默认输出该条完整原始 `message`。仅当用户要求脱敏时添加 `--redact`。代理必须在执行脚本的 Python 环境中可作为模块 `alibabacloud_sls_mcp_proxy` 导入；建议 Python 3.11+。若未安装，应按用户授权和本机环境安装匹配版本；当前已验证版本为 `0.3.2`。脚本支持通过环境变量传递凭证，或在获得当前任务的明确授权后用 `--credential-file` 指向私密 Markdown 接入文件。该参数是文件路径，不接受密钥明文。

示例（在 Skills 目录下执行，将标识替换为实际值）：

```bash
SLS/.venv/bin/python SLS/scripts/query.py --env prod --from now-1h --to now \
  --query 'BOOKING_IDENTIFIER' --reverse --lines 10
```

定位到核心日志后，按该条记录的元数据获取完整 `message`，例如：

```bash
SLS/.venv/bin/python SLS/scripts/query.py --env prod --from 1791871290 --to 1791871320 \
  --query 'BOOKING_IDENTIFIER' --reverse --lines 20 --full-message \
  --message-time '2026-10-13 14:01:46.810' \
  --message-class 'WebLogAop.java:63' --message-trace-id 'TRACE_ID'
```

`--full-message` 只在同时指定以上三个单条定位条件时可用，不会输出其他匹配日志的消息。默认不脱敏日志内容；使用 `--redact` 时会对常见密码、token、邮箱、手机号和 URL 脱敏，仍须检查是否有其他敏感字段。不要直接在终端打印完整 MCP 原始响应；本机 SLS 访问密钥不得输出。若用户要原始 JSON，从完整 `message` 中解析对应的请求或响应对象，保持字段和值，并明确说明它取自哪条日志。
