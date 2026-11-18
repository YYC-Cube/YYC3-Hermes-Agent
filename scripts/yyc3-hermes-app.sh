#!/usr/bin/env bash
# yyc3-hermes-app.sh — local app packaging for this fork (ADR-001 operational entry point).
#
# Builds a self-contained macOS launcher bundle that starts the Hermes web dashboard on
# 127.0.0.1 and opens it. No network egress beyond loopback; the dashboard is the same
# local management surface `hermes dashboard` serves.
#
#   bash scripts/yyc3-hermes-app.sh build       # (default) build ~/Applications/YYC3 Hermes.app
#   bash scripts/yyc3-hermes-app.sh install     # build + login autostart agent (dashboard at login)
#   bash scripts/yyc3-hermes-app.sh uninstall   # unload agent + remove app and plist
#   bash scripts/yyc3-hermes-app.sh status      # app presence, dashboard health, agent state
#   bash scripts/yyc3-hermes-app.sh open        # what the app does: start if needed, open the UI
#   bash scripts/yyc3-hermes-app.sh --help
#
# Only these paths are written:
#   ~/Applications/YYC3 Hermes.app
#   ~/Library/LaunchAgents/com.yyc3.hermes-app.plist   (install/uninstall only)
#   ~/Library/Logs/yyc3-hermes-app.log
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/YYC3 Hermes.app"
LABEL="com.yyc3.hermes-app"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/yyc3-hermes-app.log"
PORT="${YYC3_HERMES_PORT:-9119}"
URL="http://127.0.0.1:$PORT/"
HERMES_BIN="$HOME/.hermes/hermes-agent/venv/bin/hermes"
ICONSET="$REPO/pubilc/yyc3-icons/macos/AppIcon.iconset"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

health() { curl -fsS -o /dev/null --max-time 2 "${URL}health" 2>/dev/null; }

# ── launcher payload ────────────────────────────────────────────────────────
write_launcher() {
  local target="$1"
  cat > "$target" <<'LAUNCHER'
#!/bin/bash
# YYC3 Hermes launcher — inside the app bundle. Default: ensure the local dashboard is up,
# then open it. --daemon: run the dashboard in the foreground (used by the login agent).
set -uo pipefail
PORT="${YYC3_HERMES_PORT:-9119}"
URL="http://127.0.0.1:${PORT}/"
LOG="$HOME/Library/Logs/yyc3-hermes-app.log"
HERMES="$HOME/.hermes/hermes-agent/venv/bin/hermes"

# Finder/launchd start with a minimal PATH where python3 is the system 3.9 and uv/node
# are unreachable (same trap the maintenance wrapper documents).
export PATH="/opt/miniconda3/bin:/opt/homebrew/bin:/opt/homebrew/opt/node@22/bin:$HOME/.local/bin:$HOME/.go/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
say() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }

alert() {
  # argv form, not string interpolation: the message never becomes AppleScript source.
  /usr/bin/osascript \
    -e 'on run argv' \
    -e 'display alert "YYC³ Hermes" message (item 1 of argv)' \
    -e 'end run' -- "$1" >/dev/null 2>&1 || true
}

if [ ! -x "$HERMES" ]; then
  say "hermes binary missing: $HERMES"
  alert "未找到 hermes 运行时：$HERMES — 请先完成运行时安装。"
  exit 78
fi

if [ "${1:-}" = "--daemon" ]; then
  # Login start must be idempotent: a dashboard already serving this port (started by the
  # app, a manual `hermes dashboard`, or a previous agent tick) is success, not a port clash.
  # Exiting 0 also stops KeepAlive from restarting us into a BACKEND_PORT_IN_USE loop.
  if curl -fsS -o /dev/null --max-time 2 "${URL}health" 2>/dev/null; then
    say "daemon mode: dashboard already healthy on :$PORT — nothing to do"
    exit 0
  fi
  say "daemon mode: dashboard on port $PORT"
  exec "$HERMES" dashboard --no-open --port "$PORT"
fi

say "=== launch ==="
if ! curl -fsS -o /dev/null --max-time 2 "${URL}health" 2>/dev/null; then
  say "dashboard not healthy on :$PORT — starting it"
  nohup "$HERMES" dashboard --no-open --port "$PORT" >>"$LOG" 2>&1 &
  disown 2>/dev/null || true
  up=0
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null --max-time 2 "${URL}health" 2>/dev/null; then up=1; break; fi
    sleep 0.5
  done
  if [ "$up" != 1 ]; then
    say "dashboard did not become healthy within 60s"
    alert "本地 Dashboard 启动超时 — 日志：~/Library/Logs/yyc3-hermes-app.log"
    exit 1
  fi
fi
say "healthy — opening $URL"
/usr/bin/open "$URL"
LAUNCHER
  chmod +x "$target"
}

build_app() {
  local bin="$APP/Contents/MacOS" res="$APP/Contents/Resources"
  mkdir -p "$bin" "$res" || die "cannot create $APP"

  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>YYC3 Hermes</string>
  <key>CFBundleDisplayName</key><string>YYC³ Hermes</string>
  <key>CFBundleIdentifier</key><string>com.yyc3.hermes.app</string>
  <key>CFBundleExecutable</key><string>YYC3Hermes</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

  write_launcher "$bin/YYC3Hermes"

  if [ -d "$ICONSET" ] && command -v iconutil >/dev/null 2>&1; then
    if iconutil -c icns "$ICONSET" -o "$res/AppIcon.icns" 2>/dev/null; then
      say "icon: $res/AppIcon.icns"
    else
      say "icon: skipped (iconutil failed; bundle still valid)"
    fi
  else
    say "icon: skipped (iconset or iconutil unavailable)"
  fi
  # Finder caches bundle metadata; touching the root makes the new icon/argv show up.
  touch "$APP"
  say "built: $APP"
}

write_agent() {
  mkdir -p "$(dirname "$AGENT")"
  cat > "$AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$APP/Contents/MacOS/YYC3Hermes</string>
    <string>--daemon</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST
  say "agent written: $AGENT"
}

agent_loaded() { launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; }

do_status() {
  if [ -d "$APP" ]; then say "app:      present — $APP"; else say "app:      absent"; fi
  if health; then say "dashboard: healthy — $URL"; else say "dashboard: not running — $URL"; fi
  if agent_loaded; then say "autostart: loaded ($LABEL)"; elif [ -f "$AGENT" ]; then say "autostart: plist present, not loaded"; else say "autostart: not installed"; fi
  [ -f "$LOG" ] && say "log:      $LOG ($(wc -l < "$LOG" | tr -d ' ') lines)"
  return 0
}

case "${1:-build}" in
  build)     build_app ;;
  install)
    build_app
    write_agent
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$AGENT" || die "launchctl bootstrap failed: $AGENT"
    say "autostart loaded: $LABEL (dashboard starts at login)"
    ;;
  uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    rm -f "$AGENT"
    rm -rf "$APP"
    say "removed: $APP"
    say "removed: $AGENT"
    say "(dashboard process, if any, is left running — stop with: hermes dashboard --stop)"
    ;;
  status)    do_status ;;
  open)
    if health; then
      /usr/bin/open "$URL"; say "opened $URL"
    else
      say "dashboard not running; starting via the app launcher"
      /bin/bash "$APP/Contents/MacOS/YYC3Hermes" 2>/dev/null || die "launcher failed — run: bash scripts/yyc3-hermes-app.sh build"
    fi
    ;;
  -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command: $1 (try --help)" ;;
esac
