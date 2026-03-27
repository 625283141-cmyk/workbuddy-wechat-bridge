#!/bin/bash
# install.sh - 安装 workbuddy-wechat-bridge 为 macOS launchd 服务

set -e

LABEL="com.cassie.workbuddy-wechat-bridge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIDGE_PY="$SCRIPT_DIR/bridge.py"
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/workbuddy-wechat-bridge.log"

echo "📦 安装 WorkBuddy WeChat Bridge..."

# 创建日志目录
mkdir -p "$LOG_DIR"

# 生成 plist
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$BRIDGE_PY</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF

echo "✅ Service file created: $PLIST"

# 加载服务
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✅ Bridge installed and running!"
echo "📄 日志: tail -f $LOG_FILE"
echo ""
echo "常用命令:"
echo "  查看状态: launchctl list | grep $LABEL"
echo "  重启服务: launchctl kickstart -k gui/\$(id -u) && launchctl load $PLIST"
echo "  卸载服务: ./uninstall.sh"
