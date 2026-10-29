#!/usr/bin/env bash
# P0-5 方案 B 收尾/续期：DCDN HTTPS（Let's Encrypt via lego + alidns）+ 强制跳转 + 5 类响应头 + 验收
#
# 2026-10-29 全链路实测通过。前提：
#   - aliyun CLI 已配置（~/.aliyun/config.json，AK mode）；
#   - DCDN 已添加 h-agent.yyc3.vip 且 CNAME 已切到 *.queniuaa.com（用户已完成的 8.1 步骤 1-4/8）；
#   - lego 已安装（本网络 brew/ghcr 与 proxy.golang.org 不通，用：
#     GOPROXY=https://goproxy.cn,direct go install github.com/go-acme/lego/v4/cmd/lego@latest）。
#
# 用法:
#   bash p05b-dcdn-configure.sh            # 首次配置：签发→上传→强制HTTPS→响应头→验收
#   bash p05b-dcdn-configure.sh renew      # 续期（LE 90 天；acme 剩 30 天内才实际续）+ 重新上传 + 验收
#   bash p05b-dcdn-configure.sh --dry-run  # 打印将执行的动作
#
# 实测踩坑（勿改回）：
#   - SetDcdnDomainSSLCertificate 参数为 --SSLPub/--SSLPri（非 CertContent/KeyContent）。
#   - SetDcdnDomainStagingConfig 的 set_resp_header 只收 key/value，**不支持 action 参数**。
#   - PublishDcdnStagingConfigToProduction 必须带 --FunctionName（逐 function 发布）。
#   - CAS 免费证书 API 会 InsufficientQuota（额度已耗尽）——所以走 LE。
set -uo pipefail

DOMAIN="h-agent.yyc3.vip"
LEGO_EMAIL="admin@0379.email"
LEGO="${LEGO:-$(go env GOPATH 2>/dev/null)/bin/lego}"
LEGO_PATH="${LEGO_PATH:-$HOME/.lego}"
DRY=0
ACTION="setup"
[ "${1:-}" = "renew" ] && ACTION="renew"
[ "${1:-}" = "--dry-run" ] && DRY=1

step() { printf '\n== %s ==\n' "$*"; }
warn() { printf '⚠ %s\n' "$*"; }
die() { printf '❌ %s\n' "$*" >&2; exit 1; }

dcdn() {
  if [ "$DRY" -eq 1 ]; then echo "[dry-run] aliyun dcdn $*"; return 0; fi
  aliyun dcdn "$@" || { warn "DCDN RPC 失败：${1}（参数含证书/密钥，不回显；控制台可一键等效）"; return 1; }
}

load_ak() {
  read -r ALICLOUD_ACCESS_KEY ALICLOUD_SECRET_KEY <<EOF
$(python3 - <<'PY'
import json, os
cfg = json.load(open(os.path.expanduser("~/.aliyun/config.json")))
p = next((p for p in cfg.get("profiles", []) if p.get("name") == cfg.get("current", "default")), cfg.get("profiles", [{}])[0])
print(p.get("access_key_id", ""), p.get("access_key_secret", ""))
PY
)
EOF
  [ -n "${ALICLOUD_ACCESS_KEY:-}" ] && [ -n "${ALICLOUD_SECRET_KEY:-}" ] || die "无法从 ~/.aliyun/config.json 读取 AK"
  export ALICLOUD_ACCESS_KEY ALICLOUD_SECRET_KEY
}

issue_cert() {
  step "证书：lego (Let's Encrypt, dns=alidns, 存储于 $LEGO_PATH)"
  [ -x "$LEGO" ] || die "lego 不在 ${LEGO}（安装见文件头注释）"
  local MODE="run"; [ "$ACTION" = "renew" ] && MODE="renew --days 30"
  if [ "$DRY" -eq 1 ]; then echo "[dry-run] lego --email $LEGO_EMAIL --dns alidns -d $DOMAIN --path $LEGO_PATH $MODE"; return 0; fi
  load_ak
  (cd "$HOME" && "$LEGO" --email "$LEGO_EMAIL" --dns alidns -d "$DOMAIN" \
    --server https://acme-v02.api.letsencrypt.org/directory --accept-tos --path "$LEGO_PATH" $MODE) \
    || die "签发/续期失败（检查 AK 的 alidns 权限与 LE 可达性）"
  echo "✓ 证书就绪: $LEGO_PATH/certificates/$DOMAIN.crt"
}

upload_cert() {
  step "上传证书到 DCDN"
  local CRT KEY
  CRT="$(cat "$LEGO_PATH/certificates/$DOMAIN.crt")"
  KEY="$(cat "$LEGO_PATH/certificates/$DOMAIN.key")"
  dcdn SetDcdnDomainSSLCertificate --DomainName "$DOMAIN" \
    --CertName "h-agent-le-$(date +%Y%m%d%H%M%S)" --SSLProtocol on \
    --SSLPub "$CRT" --SSLPri "$KEY" \
    && echo "✓ 证书已下发" || warn "上传失败——控制台『HTTPS 配置』手动上传"
}

config_edges() {
  step "强制 HTTPS + 5 类响应头（staging→production）"
  dcdn SetDcdnDomainStagingConfig --DomainName "$DOMAIN" --Functions \
    '[{"functionName":"https_force","functionArgs":[{"argName":"enable","argValue":"on"}]}]'
  dcdn SetDcdnDomainStagingConfig --DomainName "$DOMAIN" --Functions '[
   {"functionName":"set_resp_header","functionArgs":[{"argName":"key","argValue":"Strict-Transport-Security"},{"argName":"value","argValue":"max-age=31536000; includeSubDomains"}]},
   {"functionName":"set_resp_header","functionArgs":[{"argName":"key","argValue":"X-Content-Type-Options"},{"argName":"value","argValue":"nosniff"}]},
   {"functionName":"set_resp_header","functionArgs":[{"argName":"key","argValue":"X-Frame-Options"},{"argName":"value","argValue":"DENY"}]},
   {"functionName":"set_resp_header","functionArgs":[{"argName":"key","argValue":"Referrer-Policy"},{"argName":"value","argValue":"strict-origin-when-cross-origin"}]},
   {"functionName":"set_resp_header","functionArgs":[{"argName":"key","argValue":"Permissions-Policy"},{"argName":"value","argValue":"camera=(), microphone=(), geolocation=()"}]}
  ]'
  dcdn PublishDcdnStagingConfigToProduction --DomainName "$DOMAIN" --FunctionName https_force
  dcdn PublishDcdnStagingConfigToProduction --DomainName "$DOMAIN" --FunctionName set_resp_header
  echo "✓ 已发布生产"
}

verify() {
  step "验收（等 75 秒生效后 curl）"
  [ "$DRY" -eq 0 ] && sleep 75
  local FAIL=0
  for u in "https://$DOMAIN/" "https://$DOMAIN/docs/"; do
    echo "-- $u --"
    curl -sI --max-time 20 "$u" | grep -Ei '^(HTTP|server|strict-transport-security|x-frame-options|x-content-type-options|referrer-policy|permissions-policy)' || FAIL=1
  done
  for h in strict-transport-security x-frame-options x-content-type-options referrer-policy permissions-policy; do
    curl -sI --max-time 20 "https://$DOMAIN/" | grep -qi "^$h" || { warn "缺少响应头: $h"; FAIL=1; }
  done
  [ "$FAIL" -eq 0 ] && echo "✅ P0-5 验收通过：HTTPS + 5/5 安全头" || echo "⛔ 有未通过项"
  return $FAIL
}

step "前置"
command -v aliyun >/dev/null 2>&1 || die "aliyun CLI 未安装"
CURRENT="$(dig +short "$DOMAIN" | tail -1)"
echo "解析: ${DOMAIN} -> ${CURRENT}（应经 DCDN 边缘）"

issue_cert
upload_cert
[ "$ACTION" = "setup" ] && config_edges
verify
