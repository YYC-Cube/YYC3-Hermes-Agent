---
file: 04-依赖漏洞Triage报告.md
description: YYC3 Hermes Agent 依赖漏洞分级、影响面与修复批次
author: YYC³ Team <admin@0379.email>
version: v1.0.0
created: 2026-10-23
updated: 2026-10-23
status: active
tags: [security, dependencies, triage]
category: report
---

<p align="center">
  <img src="../../website/static/img/yyc3-family.png" alt="YYC³ Family" />
</p>

> ***YanYuCloudCube***
> *言启象限 | 语枢未来*
> ***Words Initiate Quadrants, Language Serves as Core for Future***
> *万象归元于云枢 | 深栈智启新纪元*
> ***All things converge in cloud pivot; Deep stacks ignite a new era of intelligence***

# 依赖漏洞 Triage 报告

## 一、结论摘要

1. **328 条告警不等于 328 个独立漏洞**：按 package + manifest + advisory 去重后，critical 集中在 **10 个包**。
2. **npm 侧：源码仓锁文件过期，但运行时锁文件已修复**。运行时已使用 `dompurify 3.4.17`、`simple-git 4.0.2`、`vite 8.2.4`、`undici 7.30.0` 等修复版本；新仓库提交的是 0.21.3 旧锁文件。
3. **Python 侧：真实运行环境仍然脆弱**。`venv` 中 `certifi 2026.5.20`、`PyJWT 2.13.0`、`Pillow 12.2.0`、`anyio 4.12.1`、`aiohttp 3.14.1`、`urllib3 2.7.0` 均低于修复版本。
4. **额外发现：运行环境与锁文件漂移**。`pyproject.toml` 要求 `cryptography==50.0.0`，实际 venv 为 `46.0.7`；`Pillow` 锁为 12.3.0，实际为 12.2.0。
5. 建议顺序：**同步 npm 锁 → 修 Python runtime → 处理 Electron / simple-git 大版本 → 清理 dev-only**。

## 二、数据来源与方法

| 项 | 说明 |
| --- | --- |
| 数据源 | GitHub Dependabot Alerts（`state=open`） |
| 采集时间 | 2026-10-23 |
| 告警数 | 328 条 |
| 生态 | npm 203，pip 125 |
| 作用域 | runtime 226，development 102 |
| 说明 | `npm audit` 因 registry / 代理返回错误，本次以 Dependabot 为准 |

### 严重度分布

| 严重度 | 数量 |
| --- | ---: |
| critical | 23 |
| high | 142 |
| medium | 125 |
| low | 38 |

### 受影响清单（Top）

| 条数 | Manifest |
| ---: | --- |
| 97 | `package-lock.json` |
| 85 | `uv.lock` |
| 43 | `website/package-lock.json` |
| 40 | `pyproject.toml` |
| 29 | `apps/desktop/package.json` |
| 12 | `plugins/platforms/photon/sidecar/package-lock.json` |
| 7 | `web/package.json` |
| 7 | `apps/bootstrap-installer/package.json` |
| 4 | `ui-tui/package.json` |
| 3 | `scripts/whatsapp-bridge/package-lock.json` |

## 三、Critical 清单（10 个包）

| 包 | 生态 | 源码仓 | 运行时 | 修复版本 | 作用域 | 处理建议 |
| --- | --- | --- | --- | --- | --- | --- |
| Pillow | pip | 12.3.0 | 12.2.0 | 13.0.0 | runtime | 升 13，回归视觉/图片工具 |
| PyJWT | pip | 2.13.0 | 2.13.0 | 2.14.0 | runtime | 直接升，回归认证 |
| certifi | pip | 2026.5.20 | 2026.5.20 | 2026.10.19 | runtime | 直接升，回归 TLS |
| anyio | pip | 4.12.1 | 4.12.1 | 4.14.2 | runtime | 锁文件升级，回归异步调用 |
| dompurify | npm | 3.4.13 | 3.4.17 | 3.4.17 | runtime | 同步运行时锁 |
| shell-quote | npm | 1.9.0 | 1.12.0 | 1.11.0 | runtime/dev | 同步运行时锁 |
| proxy-addr | npm | 2.0.7（website） | 2.0.8 | 2.0.8 | runtime | 同步 website 锁 |
| tinypool | npm | 1.1.1（website） | 2.2.0 | 2.1.2 | development | 随 vitest 升级 |
| simple-git | npm | 3.36.0 | 4.0.2 | 4.0.1 | runtime（Desktop） | 大版本，回归 Git Review |
| @simple-git/argv-parser | npm | 1.1.1 | 2.0.1 | 2.0.1 | runtime（Desktop） | 随 simple-git 4 升级 |

## 四、High 热点

| 包 | 条数 | 源码仓 | 运行时 | 修复版本 | 影响面 |
| --- | ---: | --- | --- | --- | --- |
| Pillow | 46 | 12.3.0 | 12.2.0 | 13.0.0 | 图片解析、视觉工具 |
| @xmldom/xmldom | 14 | 0.8.13 | 0.8.15 | 0.9.12 | Docusaurus 构建链 |
| electron | 10 | 40.10.2 | 40.10.2 | 41.10.6 | Desktop 主进程 |
| fast-uri | 10 | 3.1.5 | 3.1.8 | 3.1.8 | 构建链 / URL 解析 |
| undici | 5 | 7.29.0 | 7.30.0 | 7.29.1 | HTTP 客户端 |
| vite | 4 | 8.2.0 | 8.2.4 | 8.2.4 | 开发服务器 / 构建 |
| PyJWT | 6 | 2.13.0 | 2.13.0 | 2.14.0 | 认证 |
| simple-git | 4 | 3.36.0 | 4.0.2 | 4.0.0 | Desktop Git 操作 |
| axios | 4 | 1.18.1 | 1.20.0 | 1.20.0 | 构建 / 脚本 |
| browserslist | 3 | — | — | 4.28.7 | 构建链 |
| aiohttp | 3 | 3.14.3 | 3.14.1 | 3.14.4 | 消息网关 |
| urllib3 | 2 | 2.7.0 | 2.7.0 | 2.8.0 | HTTP / TLS |
| tornado | 2 | 6.5.8 | 未安装 | 6.5.9 | 可选 extras |
| httpx2 | 2 | 2.7.0 | 未安装 | 2.12.0 | MCP / dev |
| joi | 1 | 18.2.3 | 18.2.9 | 17.13.8 / 18.2.9 | 构建链 |

## 五、额外发现：运行时漂移

| 包 | `pyproject.toml` 要求 | `uv.lock` | 实际 venv | 风险 |
| --- | --- | --- | --- | --- |
| cryptography | `==50.0.0` | 50.0.0 | **46.0.7** | 加密、WeCom、TLS |
| Pillow | `==12.3.0` | 12.3.0 | **12.2.0** | 图片解析 |
| aiohttp | `==3.14.3` | 3.14.3 | **3.14.1** | 消息渠道 |
| certifi | `==2026.5.20` | 2026.5.20 | 2026.5.20 | 证书校验 |
| PyJWT | `==2.13.0` | 2.13.0 | 2.13.0 | 认证 |
| anyio | 未直接 pin | 4.12.1 | 4.12.1 | 异步运行时 |

结论：**当前 venv 不是由最新锁文件构建的**。修复依赖前必须先确认 venv 来源，否则改了锁文件也不会影响真实运行。

## 六、修复批次

### Batch A（P0，低风险）：同步 npm 锁

- 目标：关闭 dompurify / shell-quote / proxy-addr / fast-uri / undici / axios / joi / @xmldom / vite / tinypool 告警
- 方式：以运行时锁为基线，按包定向更新；不要手改 `package-lock.json`
- 验证：`npm ci`（root、website、desktop）、`npm run typecheck && npm test && npm run build`
- 风险：低；仅锁文件与补丁版本

### Batch B（P0，中风险）：Python runtime

- 变更：`certifi==2026.10.19`、`PyJWT[crypto]==2.14.0`、`Pillow==13.0.0`、`aiohttp==3.14.4`、`urllib3>=2.8.0,<3`、`httpx2==2.12.0`，并让 `anyio>=4.14.2`
- 步骤：改 `pyproject.toml` → `uv lock` → 重建 venv / `hermes pm repair`
- 验证：`hermes doctor`、认证回归、视觉工具回归、网关消息回归、`scripts/run_tests.sh`
- 风险：Pillow 13 有 API 变更；cryptography 46→50 可能影响加密渠道

### Batch C（P1，大版本）：Desktop 运行时

- `electron@41.10.6`（40 → 41）
- `simple-git@4.0.2` + `@simple-git/argv-parser@2.0.1`
- `tinypool@2.2.0`（随 vitest）
- 验证：Desktop `typecheck`、`test`、`build`、启动、Git Review、终端、原生模块
- 风险：Electron ABI、native modules（node-pty / get-windows）、simple-git 4 API

### Batch D（P2）：dev-only

- @xmldom/xmldom、joi、launch-editor、browserslist 等
- 仅在 A/B/C 完成后处理；不阻塞 runtime 安全

## 七、执行约束

1. 禁止 `npm audit fix --force` 或整体大版本升级。
2. Python 依赖保持精确 pin；改 `pyproject.toml` 后必须 `uv lock`。
3. 每批单独提交，提交前跑 T12 回滚演练中的验证步骤。
4. Electron / simple-git 升级必须做 Desktop 启动与 Git Review 实测。
5. 推送后重新查看 Dependabot，确认 critical 归零。
6. 不修改 `pm/downloader.py` 的本地 400 回退补丁（T13 单独处理）。

## 八、验收标准

| 指标 | 目标 |
| --- | --- |
| critical 告警 | 0 |
| high（runtime） | 0 |
| high（development） | 有明确排期 |
| `hermes doctor` | 通过 |
| 本地 one-shot | 返回 `OK` |
| Desktop build | 通过 |
| 回滚路径 | T12 手册可用 |

## 九、下一步

1. **Batch A**：同步 npm 锁，预计关闭大部分 npm critical/high。
2. **Batch B**：更新 Python 依赖并重建 venv，关闭全部 pip critical。
3. **Batch C**：Electron 41 与 simple-git 4 专项回归。
4. **Batch D**：dev-only 清理。

> 本报告只做 triage，未修改任何依赖或锁文件。
