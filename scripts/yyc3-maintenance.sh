#!/usr/bin/env bash
# yyc3-maintenance.sh — YYC3 Hermes Agent 本机一键维护（生产态封装）
#
# 步骤: 1) preflight 门禁  2) 证书巡检（≤35 天自动续期并重传 DCDN）
#       3) 线上验收（root/docs/5 头/分片）  4) 上游周报归档  5) 维护摘要落盘
# 用法:
#   bash scripts/yyc3-maintenance.sh              # 全量
#   bash scripts/yyc3-maintenance.sh --quick      # 跳过安全测试与上游周报
#   bash scripts/yyc3-maintenance.sh --help
# 首跑待办（见 09 报告 §五）: bash -n 本脚本；输出归档目录已自动创建。
# 调度建议: scripts/com.yyc3.hermes-maintenance.plist (launchd 每周一 09:07)。
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="$REPO/docs/hermes-agent-实施专家-20261024"
DOMAIN="h-agent.yyc3.vip"
LEGO="${LEGO:-$(go env GOPATH 2>/dev/null)/bin/lego}"
LEGO_PATH="${LEGO_PATH:-$HOME/.lego}"
CERT="$LEGO_PATH/certificates/${DOMAIN}.crt"
OUT_DIR="$SESSION/logs"
OUT="$OUT_DIR/maintenance-$(date +%Y%m%d).md"

QUICK=0; SKIP_UPSTREAM=0; SKIP_TESTS=0
for a in "$@"; do
  case "$a" in
    --quick) QUICK=1; SKIP_UPSTREAM=1; SKIP_TESTS=1 ;;
    --skip-upstream) SKIP_UPSTREAM=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 64 ;;
  esac
done

mkdir -p "$OUT_DIR"
PASS=0; FAIL=0; SUMMARY=()
note() { SUMMARY+=("$1"); printf '%s\n' "$1"; }
ok()   { PASS=$((PASS+1)); note "✅ $1"; }
bad()  { FAIL=$((FAIL+1)); note "⛔ $1"; }
step() { printf '\n── %s ──\n' "$*"; }

# ── 1) preflight ──────────────────────────────────────────────
step "1/5 preflight 门禁"
PF_FLAG=""   # --quick 时转发给 preflight（跳过其第 4 步安全测试）
[ "$SKIP_TESTS" -eq 1 ] && PF_FLAG="--quick"
if bash "$REPO/scripts/preflight.sh" $PF_FLAG; then ok "preflight: 全部门禁通过"; else bad "preflight: 存在 FAIL（详见上方输出）"; fi

# ── 2) 证书巡检（≤35 天 → lego renew → 重传 DCDN）─────────────
step "2/5 证书巡检"
if [ ! -s "$CERT" ]; then
  bad "证书文件缺失: $CERT（先跑 p05b setup）"
else
  END_EPOCH=$(openssl x509 -enddate -noout -in "$CERT" | cut -d= -f2 | xargs -I{} date -jf "%b %d %H:%M:%S %Y %Z" {} +%s 2>/dev/null)
  if [ -z "${END_EPOCH:-}" ]; then
    END_EPOCH=$(openssl x509 -enddate -noout -in "$CERT" | cut -d= -f2 | xargs -I{} date -j -f "%b %d %T %Y %Z" {} +%s 2>/dev/null)
  fi
  NOW_EPOCH=$(date +%s)
  if [ -n "$END_EPOCH" ]; then
    DAYS=$(( (END_EPOCH - NOW_EPOCH) / 86400 ))
    echo "证书剩余 ${DAYS} 天"
    if [ "$DAYS" -lt 35 ]; then
      if bash "$SESSION/scripts/p05b-dcdn-configure.sh" renew; then
        ok "证书已续期并重新下发 DCDN（剩余 ${DAYS} 天触发）"
      else
        bad "续期/下发失败——手动跑 p05b renew 并检查 AK 权限"
      fi
    else
      ok "证书余量充足（${DAYS} 天），无需续期"
    fi
  else
    bad "证书到期日解析失败（macOS date 格式差异）——手动检查 openssl x509 -enddate"
  fi
fi

# ── 3) 线上验收 ───────────────────────────────────────────────
step "3/5 线上验收 (${DOMAIN})"
HCODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "https://${DOMAIN}/")
DCODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "https://${DOMAIN}/docs/")
HCNT=$(curl -sI --max-time 20 "https://${DOMAIN}/" | grep -ciE "strict-transport|x-frame|x-content-type|referrer-policy|permissions-policy")
SHARDS=$(curl -s --max-time 20 "https://${DOMAIN}/api/skills-meta.json" | python3 -c "import json,sys
try: print(len(json.load(sys.stdin).get('shards',[])))
except Exception: print(0)")
[ "$HCODE" = "200" ] && ok "根页 200" || bad "根页 ${HCODE}"
[ "$DCODE" = "200" ] && ok "/docs/ 200" || bad "/docs/ ${DCODE}"
[ "$HCNT" -ge 5 ] && ok "安全头 5/5" || bad "安全头 ${HCNT}/5"
[ "$SHARDS" -ge 3 ] && ok "分片目录在线（${SHARDS} 片）" || bad "分片 meta 异常（${SHARDS} 片）"

# ── 4) 上游周报 ───────────────────────────────────────────────
step "4/5 上游周报"
if [ "$SKIP_UPSTREAM" -eq 1 ]; then
  echo "（--quick/--skip-upstream 跳过）"
else
  if bash "$REPO/scripts/upstream_weekly.sh" --out "$OUT.upstream.md"; then
    ok "上游周报已生成: $OUT.upstream.md"
  else
    bad "上游周报失败（gh/网络降级路径见脚本输出）"
  fi
fi

# ── 5) 维护摘要 ───────────────────────────────────────────────
step "5/5 维护摘要"
{
  echo "# 维护摘要 $(date '+%Y-%m-%d %H:%M')"
  echo
  echo "| 结果 | 项 |"
  echo "| --- | --- |"
  for l in "${SUMMARY[@]}"; do echo "| ${l%% *} | ${l#* } |"; done
  echo
  echo "PASS=${PASS} FAIL=${FAIL}"
} > "$OUT"
echo "摘要已写入: $OUT"

if [ "$FAIL" -eq 0 ]; then echo "✅ 维护完成: ${PASS} 项通过"; exit 0
else echo "⛔ ${FAIL} 项失败——按上方输出逐项处理"; exit 1
fi
