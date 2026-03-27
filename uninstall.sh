#!/bin/bash
# uninstall.sh - 卸载 workbuddy-wechat-bridge

LABEL="com.cassie.workbuddy-wechat-bridge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "🗑️  卸载 WorkBuddy WeChat Bridge..."

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST"
    echo "✅ Service stopped"
fi

rm -f "$PLIST"
echo "✅ Service file removed"
echo "⚠️  配置文件和代码需要手动删除"
