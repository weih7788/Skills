# 租户映射与脚本分析指南

## 租户 ID 映射表

测试环境和生产环境的租户 ID 不同。脚本文件名后缀中包含的是该环境下的 tenantId。

| 租户名 | 测试环境 ID | 生产环境 ID | 生产测试 ID | 委托格式 |
|--------|------------|------------|-------------|----------|
| 上港长江 | 103046 | 106578 | 99969 | STANDARD_V2 |
| 天津外代 | 103007 | 273 | 2 | STANDARD_V2 |
| 君隆 | 103049 | 166 | | MH8 |
| *待补充* | 103078 | 10001 | | RELEASE_SPACE_FILLED |

> **生产测试 ID** 是该租户在生产环境中专门用于测试的租户实例，其脚本可包含 mock 逻辑，无需切换为正式对接。
> 同一租户在生产环境可能有多个 ID（对应不同的租户实例或子租户）。
> 此表可能不完整，遇到未知 ID 时应通过脚本头部注释中的租户名推断，并提示用户确认。

## 脚本目录说明

```
cube-control-desk-biz/src/main/resources/
├── scripts/          # 测试环境脚本
└── scripts-prod/     # 生产环境脚本
```

## 脚本命名规则

### 通用脚本（平台级）

不带租户 ID 后缀，所有租户共用：
```
ENTRUSTED_STANDARD_V2_CLEAN_CONTENT_FIELDS.groovy
ENTRUSTED_STANDARD_V2_CONVERT_BOOKING_PARAM.groovy
ENTRUSTED_STANDARD_V2_GET_ENTRUSTED_INFO.groovy
EXPORT_ENTRUST_TO_EXCEL.groovy
IMPORT_SIMILAR_ORDER_FROM_EXCEL.groovy
BOOKING_REPORT_EMAIL_BODY_CONVERT.groovy
```

### 租户级脚本

文件名包含租户 ID 后缀 `_<tenantId>`：
```
ENTRUSTED_STANDARD_V2_TENANT_POST_CLEAN_103046.groovy   → 上港长江(测试)
ENTRUSTED_STANDARD_V2_TENANT_POST_CLEAN_106578.groovy   → 上港长江(生产)
GENERATE_BOOKING_REMARK_103046.groovy                    → 上港长江(测试)
GENERATE_BOOKING_REMARK_106578.groovy                    → 上港长江(生产)
```

## 脚本类型清单

| 脚本类型前缀 | 功能 | 级别 |
|-------------|------|------|
| `ENTRUSTED_*_TENANT_POST_CLEAN_` | 租户级清洗后处理 | 租户级 |
| `ENTRUSTED_*_GET_ENTRUSTED_INFO` | 获取委托信息 | 通用 |
| `ENTRUSTED_*_CLEAN_CONTENT_FIELDS` | 内容字段清洗 | 通用 |
| `ENTRUSTED_*_CONVERT_BOOKING_PARAM` | 订舱参数转换 | 通用 |
| `ENTRUSTED_*_CONVERT_TO_SIMILAR_ORDER` | 转相似订单 | 通用 |
| `ENTRUSTED_*_GENERATE_WORK_ORDER_DETAIL` | 生成工单详情 | 通用 |
| `ENTRUSTED_*_YUNBA_CONVERTER` | 运吧数据转换 | 通用 |
| `ENTRUSTED_WORK_ORDER_ORDER_CREATED_HOOK_` | 工单创建后钩子 | 租户级 |
| `ENTRUSTED_WORK_ORDER_REVIEW_BEFORE_HOOK_` | 工单审核前钩子 | 租户级 |
| `GENERATE_BOOKING_REMARK_` | 生成订舱备注 | 租户级 |
| `SYSTEM_MAIL_SEND_HOOK_` | 邮件发送钩子 | 租户级 |
| `RELEASE_SPACE_FILLED_` | 放舱回填 | 租户级 |
| `BOOKING_REPORT_EMAIL_BODY_CONVERT` | 订舱报告邮件正文转换 | 通用 |
| `EXPORT_ENTRUST_TO_EXCEL` | 导出委托到 Excel | 通用 |
| `IMPORT_SIMILAR_ORDER_FROM_EXCEL` | 从 Excel 导入相似订单 | 通用 |

## 脚本差异分析方法

### Step 1: 列出变更的脚本

```bash
git diff <base-sha> <merged-tree> --name-status -- '*.groovy'
```

### Step 2: 区分通用 vs 租户级

- 文件名含数字后缀 `_\d+` → 租户级
- 否则 → 通用/平台级

### Step 3: 检测测试环境修改但生产未同步的脚本

对于每个 scripts/ 中变更的脚本：
1. 判断是通用还是租户级
2. 如果通用 → 检查 scripts-prod/ 中同名文件是否也有对应变更
3. 如果租户级 → 通过映射表找到对应的生产环境脚本名，检查是否同步

### Step 4: 概述脚本变更内容

对于每个需要同步的脚本，通过 diff 分析描述：
- 新增了什么逻辑
- 修改了什么逻辑
- 删除了什么逻辑

## 脚本头部注释格式

所有脚本都遵循统一的头部注释格式，可从中提取租户名和脚本功能：

```groovy
// =====================================================
// 描述: 租户 <租户名> 租户级别后处理脚本，在通用清洗后执行，用于添加租户定制化清洗逻辑
// 输入示例: {"result": {}, "record": {}, "tenantId": <id>, "entrustedCustomerCode": "TEST"}
// 可用变量:
//   - result: ShippingWorkOrderDetailDTO 对象（主脚本处理结果）
//   - record: IEntrustedRecord 对象（委托记录）
//   - tenantId: Integer 租户ID
//   - entrustedCustomerCode: String 委托客户代码
// 输出:
//   - 返回修改后的 ShippingWorkOrderDetailDTO 对象
// =====================================================
```

## 系统配置 API

获取生产环境 fieldClean 配置：
```
GET https://control-desk-admin.1datatech.net/control-desk-admin/api/v1/system/config?pageNum=1&pageSize=10&code=clean
```

其他系统配置类型，替换 `code` 参数值即可。

使用此 API 时需要获取当前生产配置快照，与代码中引用的 cleaner 枚举做对比，判断是否需要在运营后台新增或修改配置。
