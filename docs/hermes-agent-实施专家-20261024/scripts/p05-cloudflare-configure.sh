#!/usr/bin/env bash
# P0-5: h-agent.yyc3.vip 上线安全响应头 —— Cloudflare 一键配置（幂等，默认 dry-run）
#
# 对应文档: docs/hermes-agent-实施专家-20261024/04-P0-5线上安全头执行手册.md
# 前提: yyc3.vip 的 NS 已切到 Cloudflare（当前在阿里云 dns29/dns30.hichina.com，
#       需先在域名注册商控制台改 NS，等待 zone active）。
#
# Token 最小权限: Zone:Read / DNS:Edit / Zone Settings:Edit / Zone Rulesets:Edit
#                 （--add-zone 另需 Zone:Edit + Account ID）
#
# 用法:
#   export CF_API_TOKEN='***'
#   bash p05-cloudflare-configure.sh                       # dry-run: 只读现状，打印将执行的动作
#   bash p05-cloudflare-configure.sh --apply               # 应用: SSL Full(strict) + DNS 代理 + 5 类响应头
#   bash p05-cloudflare-configure.sh --apply --with-csp-report-only   # 附加 CSP Report-Only（第二阶段）
#   bash p05-cloudflare-configure.sh --apply --add-zone --account-id <32位ID>  # zone 未接入时先创建
#
# 本脚本不保存任何凭据；Token 只从环境变量 CF_API_TOKEN 读取。
set -euo pipefail

ZONE_NAME="yyc3.vip"
HOSTNAME="h-agent.yyc3.vip"
CNAME_TARGET="yyc-cube.github.io"
APPLY=0
ADD_ZONE=0
WITH_CSP_RO=0
ACCOUNT_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --add-zone) ADD_ZONE=1 ;;
    --with-csp-report-only) WITH_CSP_RO=1 ;;
    --account-id) ACCOUNT_ID="${2:?--account-id 需要值}"; shift ;;
    --zone) ZONE_NAME="${2:?}"; shift ;;
    --host) HOSTNAME="${2:?}"; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 64 ;;
  esac
  shift
done

command -v jq >/dev/null 2>&1 || { echo "需要 jq（brew install jq）" >&2; exit 1; }
: "${CF_API_TOKEN:?请先 export CF_API_TOKEN（最小权限 Zone:Read/DNS:Edit/Zone Settings:Edit/Zone Rulesets:Edit）}"

API="https://api.cloudflare.com/client/v4"
cf() { curl -sS --max-time 30 -H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json" "$@"; }

# stdin: API 响应；success=false 或解析失败时打印 errors 并退出
check() {
  local res; res="$(cat)"
  if ! echo "$res" | jq -e '.success' >/dev/null 2>&1; then
    echo "❌ Cloudflare API 失败:" >&2
    echo "$res" | jq '{errors}' >&2
    exit 1
  fi
  printf '%s' "$res"
}

echo "== 1/5 Token 校验 =="
check < <(cf "$API/user/tokens/verify") | jq -r '"token status: \(.result.status)"'

echo "== 2/5 Zone ($ZONE_NAME) =="
zone_json="$(check < <(cf "$API/zones?name=$ZONE_NAME"))"
zone_id="$(echo "$zone_json" | jq -r '.result[0].id // empty')"
if [ -z "$zone_id" ]; then
  if [ "$ADD_ZONE" -eq 1 ] && [ "$APPLY" -eq 1 ]; then
    [ -n "$ACCOUNT_ID" ] || { echo "--add-zone 需要 --account-id" >&2; exit 64; }
    created="$(check < <(cf -X POST "$API/zones" \
      --data "$(jq -n --arg n "$ZONE_NAME" --arg a "$ACCOUNT_ID" '{name:$n, account:{id:$a}, type:"full"}')"))"
    zone_id="$(echo "$created" | jq -r '.result.id')"
    echo "$created" | jq -r '"zone 已创建，请到阿里云域名控制台把 NS 改为: " + (.result.name_servers | join(", "))'
    echo "⚠ NS 生效（zone active）前，代理与响应头不会上线。可稍后重跑本脚本。" >&2
  else
    echo "❌ zone $ZONE_NAME 不在 Cloudflare。两条路:" >&2
    echo "   a) Dashboard → Add site 输入 $ZONE_NAME；" >&2
    echo "   b) 本脚本 --apply --add-zone --account-id <ID>。" >&2
    echo "   创建后必须到域名注册商（当前 hichina/阿里云）把 NS 改为 Cloudflare 分配值。" >&2
    exit 2
  fi
fi
zone_status="$(echo "$zone_json" | jq -r '.result[0].status // "pending"')"
if [ "$zone_id" = "" ]; then zone_id="$(cf "$API/zones?name=$ZONE_NAME" | jq -r '.result[0].id')"; fi
echo "zone id=$zone_id status=$zone_status"
[ "$zone_status" != "active" ] && echo "⚠ zone 未 active：NS 未切换或未生效；后续写入会保存，但代理在 active 前不生效。"

echo "== 3/5 SSL/TLS 模式 =="
ssl="$(check < <(cf "$API/zones/$zone_id/settings/ssl") | jq -r '.result.value')"
echo "当前: $ssl"
if [ "$ssl" != "strict" ]; then
  if [ "$APPLY" -eq 1 ]; then
    check < <(cf -X PATCH "$API/zones/$zone_id/settings/ssl" --data '{"value":"strict"}') >/dev/null
    echo "✅ 已设为 strict（Full strict）"
  else
    echo "[dry-run] 将 PATCH settings/ssl → strict"
  fi
fi

echo "== 4/5 DNS 记录 ($HOSTNAME) =="
rec_json="$(check < <(cf "$API/zones/$zone_id/dns_records?type=CNAME&name=$HOSTNAME"))"
rec_id="$(echo "$rec_json" | jq -r '.result[0].id // empty')"
if [ -z "$rec_id" ]; then
  if [ "$APPLY" -eq 1 ]; then
    check < <(cf -X POST "$API/zones/$zone_id/dns_records" --data \
      "$(jq -n --arg n "$HOSTNAME" --arg c "$CNAME_TARGET" \
         '{type:"CNAME", name:$n, content:$c, proxied:true, ttl:1}')") >/dev/null
    echo "✅ 已创建 Proxied CNAME → $CNAME_TARGET"
  else
    echo "[dry-run] 将创建 CNAME $HOSTNAME → $CNAME_TARGET（Proxied 橙色云）"
  fi
else
  rec_content="$(echo "$rec_json" | jq -r '.result[0].content')"
  rec_proxied="$(echo "$rec_json" | jq -r '.result[0].proxied')"
  echo "现有: CNAME → $rec_content  proxied=$rec_proxied"
  [ "$rec_content" != "$CNAME_TARGET" ] && echo "⚠ 记录指向 $rec_content，与预期 $CNAME_TARGET 不符，请人工确认！" >&2
  if [ "$rec_proxied" != "true" ]; then
    if [ "$APPLY" -eq 1 ]; then
      check < <(cf -X PATCH "$API/zones/$zone_id/dns_records/$rec_id" --data '{"proxied":true}') >/dev/null
      echo "✅ 已开启代理（橙色云）"
    else
      echo "[dry-run] 将 PATCH dns_records/$rec_id → proxied=true"
    fi
  fi
fi

echo "== 5/5 响应头 Transform Ruleset =="
RULESET_URL="$API/zones/$zone_id/rulesets/phases/http_response_headers_transform/entrypoint"
existing="$(cf "$RULESET_URL" | jq '{success, rules: (.result.rules // [])}')"
echo "现有规则数: $(echo "$existing" | jq '.rules | length')"

ruleset="$(jq -n --arg host "$HOSTNAME" '
  { name: "YYC3 security headers", kind: "zone", phase: "http_response_headers_transform",
    rules: [ {
      expression: ("(http.host eq \"" + $host + "\")"),
      description: "YYC3 security headers",
      action: "set_headers",
      action_parameters: { headers: [
        { name: "Strict-Transport-Security", operation: "set", value: "max-age=31536000; includeSubDomains" },
        { name: "X-Content-Type-Options",    operation: "set", value: "nosniff" },
        { name: "X-Frame-Options",           operation: "set", value: "DENY" },
        { name: "Referrer-Policy",           operation: "set", value: "strict-origin-when-cross-origin" },
        { name: "Permissions-Policy",        operation: "set", value: "camera=(), microphone=(), geolocation=()" }
      ]},
      enabled: true
    } ] }')"

if [ "$WITH_CSP_RO" -eq 1 ]; then
  ruleset="$(echo "$ruleset" | jq --arg csp \
    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.algolia.net https://*.algolianet.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" \
    '.rules += [{expression: .rules[0].expression, description: "CSP report-only", action: "set_headers",
                 action_parameters: {headers: [{name: "Content-Security-Policy-Report-Only", operation: "set", value: $csp}]},
                 enabled: true}]')"
fi

if [ "$APPLY" -eq 1 ]; then
  check < <(cf -X PUT "$RULESET_URL" --data "$ruleset") >/dev/null
  echo "✅ 响应头规则已写入（5 类头$( [ "$WITH_CSP_RO" -eq 1 ] && echo ' + CSP Report-Only' )）"
else
  echo "[dry-run] 将 PUT ruleset，规则预览:"
  echo "$ruleset" | jq -r '.rules[] | "  - " + .description'
fi

echo
echo "== 当前线上状态（https://$HOSTNAME/） =="
if [ "$APPLY" -eq 1 ]; then echo "（若刚切 NS/代理，DNS 生效需数分钟到数小时）"; sleep 3; fi
curl -sS -I --max-time 20 "https://$HOSTNAME/" | grep -Ei \
  '^(HTTP|server|cf-ray|strict-transport-security|content-security-policy|x-frame-options|x-content-type-options|referrer-policy|permissions-policy)' \
  || echo "（暂无响应头，代理未生效或 DNS 仍在传播）"
