---
file: 10-上游0230安全补丁backport评估报告.md
description: 0.23.0 Security & Reliability 四类补丁的 backport 可行性评估——现状、变更、判定、优先级
author: AI Tutor <Intelligent Application Implementation Expert>
version: v1.0.0
created: 2026-11-11
updated: 2026-11-11
status: active
tags: [backport, upstream-0.23.0, security, feasibility-assessment]
category: report
---

# 10 · 上游 0.23.0 安全补丁 Backport 评估报告

> 依据 07 报告方案 (a)：「保持 0.21.3 基线 + 安全类补丁定点 backport」。0.23.0 Security & Reliability 章节的 4 类补丁（共 11 个上游 PR）在 0.21.3 基线上的 backport 可行性评估。
>
> 方法论约束：本 fork 为 squash 导入（`ceb2a4a11f` 无上游祖先），**不可 cherry-pick**。Backport = 阅读上游 PR diff，理解核心逻辑，在 0.21.3 基线上**等价实现**。上游 diff 基于更高版本（`agent/redact.py` index `66c9e2c43a458` 等），与我方基线（`agent/redact.py` 1335 行）有分叉，无法直接打补丁，必须逐函数等价重写。

## 0. 评估速览

| 类别 | 上游 PR | 我方现状 | 可行性 | 建议 | 预估工作量 |
| --- | --- | --- | --- | --- | --- |
| URL 歧义拒绝 | 145578 | `tools/url_safety.py` 已有基础，缺 ambiguous authority 检查 | 🟢 高 | ✅ 立即 backport | 小（~200 行，单文件） |
| shell-hook 同意 | 140984 + 141034 | `agent/shell_hooks.py` 已有基础，缺 `interactive` 参数 + 同意变更重新 sync | 🟡 中等 | ✅ backport（分两步） | 中（3 文件） |
| 审批门加固 | 87362 + 148865 + 141377 + 87554 | `tools/approval_detection.py` 缺 pipe-shell/PowerShell/wmic/content-rules；`tools/approval.py` 已有 `request_id` 基础 | 🟡 中等偏低 | ⚠️ 分阶段：先 87554（request_id 卡片绑定），其余待 v0.24.0 评估 | 中～大 |
| Secret 掩码 | 149435 + 148862 + 149470 | `agent/redact.py` 已有 PEM 私钥 + userinfo 基础，缺 CLI flag / 非 PEM 私钥 / 限定键名 / connstr | 🔴 低 | ❌ 不 backport（等 v0.24.0），或仅做最高风险子项 | 大（1335 行文件多处增强 + 新文件） |

**总体建议**：先 backport URL 歧义拒绝（独立、低风险、高收益）+ shell-hook 同意（行为改进、已有基础）；审批门只 backport 87554（request_id 卡片绑定，我方已有基础，改动最小）；secret 掩码不 backport，等 v0.24.0 整树评估时再决策。

---

## 1. 类别一：URL 歧义拒绝（上游 145578）

### 1.1 上游变更
`tools/url_safety.py` 增加：
- `_url_hostname(url, percent_decode=False)`：WHATWG 客户端（浏览器、Node、urllib3）读取的主机名形式（IDNA 编码、尾随点去除、可选百分号解码）
- `_authority_ambiguity(url, floor=False)`：判断 urlsplit 与其他客户端可能读到不同主机的原因（反斜杠在 authority、用户信息、百分号编码、主机名空白、无效端口、控制字符）
- `is_always_blocked_url`：新增 ambiguous authority 检查（floor=True），对 percent-encoded host 做解码后判断
- `is_safe_url`：新增 ambiguous authority 检查（floor=False），拒绝 `http://127.0.0.1:8080\@1.1.1.1` 等形态
- `_URL_EDGE_WHITESPACE`、`_IDNA_DOTS`（ideographic/fullwidth/halfwidth 理想点）

测试：`tests/tools/test_url_safety_authority.py`、`tests/tools/test_url_safety_authority_floor.py`

### 1.2 我方现状
`tools/url_safety.py`（621 行）已有 `is_safe_url` / `is_always_blocked_url` 基础，但**无 ambiguous authority 检查**：`http://127.0.0.1:8080\@1.1.1.1` 会被 urlsplit 解析为 host 1.1.1.1 从而放行，而浏览器会拨 127.0.0.1:8080（SSRF/元数据端点泄露）。

### 1.3 可行性判定：🟢 高
- 单文件、自包含，无跨文件依赖
- 纯增量（新增函数 + 两处调用点插入），不改既有签名
- 上游测试可等价移植

### 1.4 建议
✅ **立即 backport**。实现 `_url_hostname` / `_authority_ambiguity`，在 `is_always_blocked_url`（floor=True）和 `is_safe_url` 中插入检查，同步移植两个测试文件。

---

## 2. 类别二：shell-hook 同意（上游 140984 + 141034）

### 2.1 上游变更
- `agent/shell_hooks.py`：`register_from_config` 新增 `interactive` 参数；`_consented(spec, accept, allowed, prompt=)`；只有 foreground CLI 命令（chat/rl）才会 TTY prompt，gateway 启动、profile 加载、cron、tui_gateway、force-reload 再不 prompt（避免隐藏控制台把 event loop 冻住直到 liveness watchdog 退出 75）
- `gateway/run_startup.py`：`_register_config_hooks` 文档更新，明确 gateway 不 prompt
- `gateway/shutdown_watchdog.py`：liveness 死亡时同时写 dump 文件 + stderr（控制台-less 启动器丢弃 stderr 时留下栈）
- `hermes_cli/main.py`：`_prepare_agent_startup` 按命令区分 `interactive`（只有 `chat`/`rl` 为 True）
- `gateway/run_profile_reconcile.py`：watcher 每 tick（~30 秒）重新 sync 每个 home 的 shell-hook 同意变更（允许文件或 config.yaml 变更），无需重启
- `hermes_cli/hooks.py` / `subcommands/hooks.py`：revoke 提示更新为"约 30 秒内生效"

### 2.2 我方现状
`agent/shell_hooks.py`（602 行）已有 `register_from_config(cfg, accept_hooks=False)`（无 `interactive`）、`_consented(spec, accept, allowed)`（无 `prompt`）、`_prompt_and_record`。`gateway/run_profile_reconcile.py` 存在但**无 shell-hook 同意变更重新 sync**（watcher 只 rescan profiles，不 re-sync hooks）。

### 2.3 可行性判定：🟡 中等
- `register_from_config` 签名变更（新增 `interactive` 关键字参数，向后兼容）
- 需确认所有调用站点（`gateway/run_startup.py`、`hermes_cli/main.py`、`agent/shell_hooks.py` 内部 `sync_from_config`/`record_consent_from_config`）是否传 `interactive`
- `gateway/run_profile_reconcile.py` 需新增 watcher tick 逻辑（与既有 `reconcile_served_profiles` 并行，不冲突）

### 2.4 建议
✅ **backport，分两步**：
1. `agent/shell_hooks.py` + `gateway/run_startup.py` + `hermes_cli/main.py`：`interactive` 参数 + 非 foreground 不 prompt
2. `gateway/run_profile_reconcile.py`：watcher tick 重新 sync 同意变更

---

## 3. 类别三：审批门加固（上游 87362 + 148865 + 141377 + 87554）

### 3.1 上游变更（四个 PR）

**87362 — pipe-to-shell 扩展**
- `tools/approval_detection.py`：`_PipeRemoteToShellMatcher`（线性扫描替代贪婪正则，避免回溯）、`_PIPE_SHELL_NAMES_RE` 增加 fish/csh/tcsh/ash、带启动器链（sudo/env/timeout/exec…）的宽 sink、路径限定/.exe/引号 shell 名称
- `DANGEROUS_PATTERNS_COMPILED` 改用 `_CUSTOM_MATCHERS` 字典

**148865 — PowerShell 前缀匹配 + wmic shadowcopy**
- `_PS_RECURSE` / `_PS_FORCE` / `_PS_DELETE_VERB`（前缀匹配：`-r` = `-Recurse`，`-fo` = `-Force`）
- `_PS_EXE_AT_COMMAND_POSITION`（PowerShell 在命令位置，含启动器链）
- `_WmicShadowDeleteMatcher`（`wmic shadowcopy delete` 穿透 cmd /c / pwsh / ssh 等启动器）
- 引号内脚本执行检测（`ssh host "gci | ri -r"` 等）

**141377 — content-level rules 独立同意**
- `detect_dangerous_command` 重构为 `_iter_dangerous_descriptions` 生成器（返回所有匹配，不再只返回第一个）
- 新增 `detect_content_rule_keys`（credential upload / invisible Unicode 等 content 规则）
- `tools/approval.py`：`_unapproved_findings(command, approved)`——已同意的 pipe-to-shell 不能放行未同意的 credential upload；`check_dangerous_command` / `check_all_command_guards` / `_unattended_deny` 皆按 `pending` 列表逐项求同意

**87554 — 审批卡片按 request_id 绑定**
- `tools/approval.py`：新增 `resolve_gateway_approval_card(session_key, choice, request_id)`——只解析卡片对应的 request，不再误解析同会话里下一张卡片
- 七个平台 adapter（telegram/slack/feishu/matrix/teams/whatsapp_cloud/relay）全部改用 `resolve_gateway_approval_card` 并传 `prompt.request_id`
- `hermes_cli/plugin_validate_private_imports.py`、`website/docs/...` 同步

### 3.2 我方现状
- `tools/approval_detection.py`（1501 行）：`DANGEROUS_PATTERNS_COMPILED` 是**简单的正则列表**（第 442 行），无 `_PipeRemoteToShellMatcher`、`_WmicShadowDeleteMatcher`、`_CUSTOM_MATCHERS`；`detect_dangerous_command` 仍返回元组 `(is_dangerous, pattern_key, description)`，**非生成器**
- `tools/approval.py`（1353 行）：**已有** `resolve_gateway_approval(session_key, choice, resolve_all=False, reason=None, request_id=None)`（第 141 行），`request_id` 基础到位；**缺失** `resolve_gateway_approval_card`、`_unapproved_findings`、`detect_content_rule_keys`
- 七个平台 adapter：我方是否有对应文件需另查（fork 是 0.21.3 基线，平台 adapter 结构可能与上游 0.23 差异大）

### 3.3 可行性判定：🟡 中等偏低
- 87362 / 148865：需要改 `detect_dangerous_command` 的返回协议（元组 → 生成器），**牵一发而动全身**（所有调用站点、所有 adapter、所有 tests）；在 0.21.3 基线上等价重写风险高，收益中等
- 141377：同上，且引入 `_iter_dangerous_descriptions`，检测逻辑重构
- 87554：我方 `approval.py` 已有 `request_id` 参数，**改动最小**——只需新增 `resolve_gateway_approval_card` 包装 + 适配器传 `request_id`。但需确认我方七个 adapter 是否已有 `request_id` 字段和对应调用

### 3.4 建议
⚠️ **分阶段**：
1. **先做 87554**（request_id 卡片绑定）：我方已有 `request_id` 基础，改动最小，收益是避免"旧卡片误解析新请求"的安全漏洞。需先确认我方 adapter 结构。
2. **87362 / 148865 / 141377**：**不在本次 backport**，等 v0.24.0 整树评估时再决策。理由：`detect_dangerous_command` 返回协议变更在分叉基线上等价实现风险高，且我方已有 `approval_detection.py` 的大量本地定制（`approval_floors.py`、`approval_smart.py` 等），直接移植容易回归。

---

## 4. 类别四：Secret 掩码（上游 149435 + 148862 + 149470）

### 4.1 上游变更
`agent/redact.py`（+ 新文件 `agent/redact_connstr.py`）多处增强：
- CLI 秘密 flag 掩码（`--password=`, `--token`, `docker login -p`，含引号/转义/多行）
- 非 PEM 私钥掩码（base64 PEM、`_B64_PEM_RE`、`_is_b64_pem_key`；PGP armor、`_PGP_PRIVATE_KEY_RE`；PuTTY `.ppk`、`_PUTTY_PRIVATE_LINES_RE`；age、`_AGE_SECRET_KEY_RE`；`_redact_private_key_blocks`）
- 限定键名（`aws_secret_access_key`、`signing_key`、`privateKey`、`_KEY_QUALIFIED_NAME`、`_is_qualified_key_name`）
- YAML 密钥词扩展、JSON 任意密钥（`_JSON_ANY_KEY_FIELD_RE`、`_json_affixed_key_secret`）
- URL userinfo 密码掩码（`_redact_userinfo_passwords`、`_URL_USERINFO_PAIR_RE`）
- BASIC 对（`NAME=user:pass`，force-only、`_BASIC_PAIR_ASSIGN_RE`）
- 密码-only 连接字符串（`redis://:pw@host`、`_DB_CONNSTR_RE` 扩展）
- 网络路径 userinfo（`//user:pass@host`，force-only、`_NETWORK_PATH_USERINFO_RE`）
- 连接字符串 key/value 掩码（新文件 `agent/redact_connstr.py`，ADO.NET/ODBC/JDBC/libpq）
- 已掩码标记识别（`_REDACTION_MARKER_RE`，避免二次掩码擦除 kind）

### 4.2 我方现状
`agent/redact.py`（1335 行）已有：
- `_PRIVATE_KEY_RE`（PEM 私钥，第 500 行）+`_redact_private_key_blocks`（第 940 行）
- userinfo 处理相关注释（第 518/523/549/752/872/961 行）
- `_redact_url_credentials`（第 844 行）

缺失：
- CLI flag 掩码（`--password=` 等）
- 非 PEM 私钥（base64/PGP/PuTTY/age）
- 限定键名（`aws_secret_access_key` 等）
- 网络路径 userinfo（`//user:pass@host`）
- 连接字符串 key/value（需新文件 `agent/redact_connstr.py`）

### 4.3 可行性判定：🔴 低
- `agent/redact.py` 是 1335 行的核心安全模块，上游 diff 是在**更高版本基准点**（index `66c9e2c43a458`）上的增量，与我方 1335 行版本有分叉
- 多处正则交织（YAML/JSON/URL/前缀/私钥），等价重写极易引入回归（误杀合法配置 / 漏掉新形态）
- 新文件 `agent/redact_connstr.py` 需从零实现
- 测试覆盖（`test_redact_leak_shapes.py` 等）也需同步移植

### 4.4 建议
❌ **不在本次 backport**。建议等 v0.24.0 整树评估时再决策。若确实需尽快处理，仅回 port **最高风险子项**（CLI flag 掩码 + 密码-only 连接字符串），作为最小可行性补丁，其余待 v0.24.0。

---

## 5. 优先级排序与实施计划

| 优先级 | 事项 | 上游 PR | 预估工作量 | 风险 |
| --- | --- | --- | --- | --- |
| P0 | URL 歧义拒绝 backport | 145578 | 小（1 文件 ~200 行） | 低 |
| P1 | shell-hook 同意 backport（interactive 参数） | 140984 | 中（3 文件） | 中（签名变更需确认调用站点） |
| P2 | shell-hook 同意 backport（同意变更重新 sync） | 141034 | 中（1 文件 + watcher tick） | 中 |
| P3 | 审批卡片 request_id 绑定 backport | 87554 | 小～中（需先确认我方 adapter 结构） | 低 |
| P4 | 审批门 pipe-shell / PowerShell / content-rules | 87362/148865/141377 | 大 | 高（返回协议变更） |
| P5 | Secret 掩码增强 | 149435/148862/149470 | 大 | 高（1335 行核心模块多处增强） |

**建议执行顺序**：P0 → P1 → P2 → P3。P4/P5 等 v0.24.0 干跑评估后再决策。

---

## 6. 风险提示

1. **无共同祖先**：所有 backport 都必须是"等价重写"，不能直接 `git cherry-pick` 或 `git apply` 上游 diff。每一处变更都要在 0.21.3 基线上重新理解并实现。
2. **`detect_dangerous_command` 返回协议**：141377 将其从元组改为生成器，我方 `tools/approval.py`、`tools/approval_floors.py`、`tools/approval_smart.py` 等多处调用站点都需要同步改造，回归风险高。
3. **`agent/redact.py` 分叉**：我方 1335 行版本与上游 diff 基准点（`66c9e2c43a458`）不一致，直接移植正则极易引入误杀或漏检。
4. **平台 adapter 差异**：87554 涉及七个平台 adapter，我方 0.21.3 基线的 adapter 结构可能与上游 0.23 差异大，需逐个确认 `request_id` 字段和调用站点。

---

## 7. 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v1.0.0 | 2026-11-11 | 初版：四类补丁可行性评估，P0-P5 优先级排序，P4/P5 建议等 v0.24.0 |

---

> YYC³ · YanYuCloudCube · 言启象限 · 语枢未来
> Words Initiate Quadrants, Language Serves as Core for Future
> 本文档遵循 `~/YYC-Cube/YYC3-团队通用-标准规范/` v2.0.0 文档闭环规范
> © 2025-2026 YYC³ Team · All Rights Reserved
