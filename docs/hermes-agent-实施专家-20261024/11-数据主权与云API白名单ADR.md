---
file: 11-数据主权与云API白名单ADR.md
description: ADR-001 数据主权决策——完全自控/非共用/本地优先，云 egress 仅限 DeepSeek×2 + GLM×2，preflight 门禁强制执行
author: AI Tutor <Intelligent Application Implementation Expert>
version: v1.0.0
created: 2026-11-18
updated: 2026-11-18
status: accepted
tags: [adr, data-sovereignty, privacy, allowlist, enforcement]
category: adr
---

# ADR-001 · 数据主权与云 API 白名单

- **状态**：Accepted（2026-11-18）
- **决策者**：仓库所有者（YYC³）
- **影响面**：模型路由、STT、辅助任务、凭据管理、preflight 门禁
- **执行载体**：`scripts/data_sovereignty_check.py` + `scripts/preflight.sh` 第 6 门禁

---

## 1. 背景（Context）

本仓库是 `NousResearch/hermes-agent` 的私有 fork，已完成整树切换评估（[08 报告](./08-上游0231整树切换干跑报告.md)），裁决为**方案 (a)：自控基线 + 定点 backport**，不再追踪上游常规演进。

在此基础上需要把「不依托上游、非共用、本地数据不出去」从口头原则升级为**可执行、可审计、可复现**的架构约束，避免后续任何配置漂移（新增 provider、辅助任务路由、STT 云上传）悄悄破坏该原则。

现状事实（2026-11-18 实测）：

| 项 | 现状 |
| --- | --- |
| 默认模型 | 本地 Ollama `qwen3-coder-30b-64k`（`http://127.0.0.1:11434/v1`） |
| `~/.hermes/.env` 云 provider 密钥 | **0 个**（无任何 `*_API_KEY`/`*_TOKEN`） |
| `providers:` 自定义 provider | 无 |
| `model.fallback_providers` | 未配置 |
| STT `provider` | 未显式设置（自动探测梯级，存在被云 provider 命中的可能） |

即：**当前已是纯本地，但缺少「防止漂移」的机制**。本 ADR 补齐该机制。

---

## 2. 决策（Decision）

### D1 · 本地优先（Local-first）

默认模型路由必须指向回环地址（`127.0.0.1` / `localhost` / `::1`）。本地推理是常态路径，不是降级路径。

### D2 · 云 egress 白名单：2 provider × 2 模型 = 4 个授权模型

| Provider | 授权模型 | 端点 |
| --- | --- | --- |
| `deepseek` | `deepseek-v4-pro`、`deepseek-flash` | `https://api.deepseek.com/v1` |
| `zai`（GLM） | `glm-5.2`、`glm-4.5-flash` | `https://api.z.ai/api/paas/v4` |

**除此之外的任何云 provider / 模型 / 端点均未授权。** 选择依据：DeepSeek 双模型 = 旗舰（v4-pro）+ 快档（flash）；GLM 双模型 = 旗舰（5.2）+ 快档（4.5-flash），与两家 provider profile 的 `fallback_models` / `default_aux_model` 对齐。

### D3 · 凭据只放 `.env`，且只允许两把云钥匙

- 允许的云凭据环境变量：`DEEPSEEK_API_KEY`、`GLM_API_KEY`（`ZAI_API_KEY`/`Z_AI_API_KEY` 为等价别名）
- `.env` 中出现其他任何云 provider 凭据（`OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`OPENROUTER_API_KEY`…）= 违规
- 凭据不得写入 `config.yaml`（`providers.*.api_key` 内联 = 违规）

### D4 · 辅助链路与 STT 同样受约束

- `auxiliary.<task>`（标题生成、压缩、vision、审批分类、curator…）的 `provider`/`base_url` 若显式设置，必须落入 D1/D2
- `stt.provider` 必须显式设为 `local`（或在无任何云 STT 凭据时允许 unset），禁止自动梯级落到云
- `fallback` 链路（`model.fallback_providers` / 顶层 `fallback_providers`）逐项受同一约束

### D5 · 门禁强制执行，不靠自觉

`scripts/data_sovereignty_check.py` 对**生效配置**做静态审计，接入 `scripts/preflight.sh` 作为第 6 门禁：

- 任一违规 → preflight FAIL → 本机维护脚本（`yyc3-maintenance.sh`）与提交前检查同步失败
- 审计对象是**配置与凭据名**，不读取对话内容、不上报任何数据（审计本身零网络）

### D6 · 变更需改 ADR，而不是改配置

新增云 provider、模型或端点 = 修订本 ADR（追加条目 + 复审记录），并同步更新门禁白名单。**禁止仅为方便而临时加 key。**

---

## 3. 数据边界（Boundary）

### 3.1 永不出本机

| 数据 | 存储位置 |
| --- | --- |
| 会话历史 | `~/.hermes/` 本地 SessionDB |
| 记忆 / 用户画像 | `~/.hermes/` 本地 |
| 技能与技能分片 | 本地仓库 + 本地缓存 |
| 配置 / 凭据 | `~/.hermes/config.yaml` + `.env` |
| 日志 / 维护归档 | `~/.hermes/logs/`、`docs/.../logs/` |
| 终端输出、文件读写、MCP 本地工具 | 本地进程 |
| 维护/巡检（preflight、launchd、SBOM、OSV） | 本地执行，零外发 |

### 3.2 选择云模型时出境的（用户显式触发）

- 当前轮的用户消息、系统提示、工具结果、压缩上下文 → 发往所选云 provider（DeepSeek 或 Z.AI）
- 目的域仅限 `api.deepseek.com` / `api.z.ai`
- 不选择云模型时，零出境（默认即此状态）

### 3.3 用户主动触发的其他 egress（非本 ADR 管辖，但需知晓）

- 浏览器工具访问的网站
- Web 搜索 provider（若启用）
- 消息网关（Telegram/Discord 等）——只有主动接入时才存在

### 3.4 明确不在本 ADR 范围

- 上游代码同步（不追踪，见 08 报告）
- 消息平台的第三方服务条款
- 本地模型自身的遥测（Ollama 默认关闭；如开启需单独记录）

---

## 4. 执行矩阵

| 约束 | 配置载体 | 强制手段 |
| --- | --- | --- |
| D1 本地默认 | `model.provider/base_url` | 门禁：非回环 + 非白名单 → FAIL |
| D2 四模型白名单 | `providers.deepseek.models` / `providers.zai.models` | 门禁：未授权模型 id → FAIL |
| D3 凭据白名单 | `~/.hermes/.env` | 门禁：扫描凭据**变量名**；`config.yaml` 内联 key → FAIL |
| D4 辅助/STT/fallback | `auxiliary.*`、`stt.provider`、`fallback*` | 门禁：逐项检查 |
| D5 门禁本身 | `scripts/preflight.sh` | 第 6 步，任一 FAIL 即整体失败 |
| D6 变更流程 | 本 ADR | 人工复审（新增条目 + 变更记录） |

---

## 5. 后果（Consequences）

**正面**

- 数据主权从原则变为可验证不变量：每次 preflight / 每次周维护都会复核
- 任何配置漂移（新 provider、新 key、STT 云梯级）在本地 11 秒门禁内暴露
- 云用量可预测：最多 4 个模型、2 个目的域

**负面 / 需要接受**

- 模型选择器对内置 provider 仍可能显示其完整目录（Hermes 对内置 provider 的 `models:` 是**追加**语义，非替换）。**以门禁为准**：显示 ≠ 授权
- 新增云 provider 需走 ADR 修订，比「直接加 key」多一步
- 本地模型能力弱于云旗舰；需要云能力时必须显式切换模型（有意识地出境）

**未采用方案**

- *仅文档约束*：无法防漂移，否决
- *包装 core 强制拦截*：需要改模型解析主链路，违背「核心窄腰」原则，且 fork 维护成本高；改为**配置门禁**，零 core 改动
- *完全禁云*：与所有者「允许 DeepSeek/GLM 双模型」的决策不符

---

## 6. 复审触发条件

1. 需要新增云 provider / 模型 / 端点
2. 升级 Hermes 基线（v0.24.0 评估）导致配置语义变化
3. 更换本地推理引擎（Ollama → vLLM/llama.cpp）
4. 每季度例行复核（与维护态巡检合并）

---

## 7. 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v1.0.0 | 2026-11-18 | 初版：D1-D6 决策、数据边界、执行矩阵、复审条件；落地为 preflight 第 6 门禁 |

---

> YYC³ · YanYuCloudCube · 言启象限 · 语枢未来
> Words Initiate Quadrants, Language Serves as Core for Future
> 本文档遵循 `~/YYC-Cube/YYC3-团队通用-标准规范/` v2.0.0 文档闭环规范
> © 2025-2026 YYC³ Team · All Rights Reserved
