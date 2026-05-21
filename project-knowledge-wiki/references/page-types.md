# 页面类型

目录划分、front matter 与章节模板见 [schema.md](./schema.md) 第 3、5、9 节。

## domain

用于业务域总览（`wiki/domains/`）。

常见章节：这是什么、核心对象、核心入口、关键流程、边界与例外、风险与待确认项、Sources

## concept

用于字段语义、业务术语或横切规则（`wiki/concepts/`）。

常见章节：定义、使用位置、约束、常见误解、风险与待确认项、Sources

## flow

用于跨模块流程或时序链路（`wiki/flows/`）。

常见章节：触发条件、流程步骤、关键落库/调用点、异常与回退、Sources

## integration

用于三方系统接入说明（`wiki/integrations/`）。

常见章节：这是什么、关键依赖、调用方式、异常点、Sources

## data-model

用于表、Mongo、配置模型语义（`wiki/data-models/`）。

常见章节：定义、关键字段、关联关系、边界与例外、Sources

## runbook

用于重复执行的运维或维护步骤（`wiki/runbooks/`）。

常见章节：何时执行、执行步骤、校验方式、常见失败点、Sources

## decision

用于记录长期有效的设计决策与取舍（`wiki/decisions/`）。

常见章节：背景、决策、原因、结果、不做什么、Sources
