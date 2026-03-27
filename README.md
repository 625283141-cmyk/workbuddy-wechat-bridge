# WorkBuddy WeChat Bridge

将 WorkBuddy 自动化任务结果通过微信 ilinkai 协议推送到你的微信。

## 功能

- 监听 WorkBuddy `automation_runs` 数据库
- 检测自动化任务完成时，主动推送结果到微信
- 支持 macOS launchd 开机自启动
- 配置持久化，开机后自动恢复运行

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/YOUKNOWWHO/workbuddy-wechat-bridge.git
cd workbuddy-wechat-bridge
```

### 2. 安装依赖

```bash
pip3 install httpx aiosqlite
```

### 3. 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入你的凭证
```

### 4. 测试发送

```bash
python3 bridge.py --test "Hello from WorkBuddy Bridge!"
```

### 5. 启动守护进程

```bash
# 一次性运行
python3 bridge.py

# 或安装为 macOS 服务（开机自启）
./install.sh
```

## 配置说明

`config.json` 字段：

| 字段 | 说明 | 来源 |
|------|------|------|
| `bot_token` | ilinkai Bot Token | WorkBuddy 设置中查找 |
| `user_id` | 你的微信 userId | WorkBuddy 设置中查找 |
| `base_url` | ilinkai API 地址 | 固定为 `https://ilinkai.weixin.qq.com` |
| `db_path` | WorkBuddy 数据库路径 | 见下方默认值 |
| `poll_interval` | 轮询间隔（秒） | 默认 30 |

## 查找凭证

在 `~/Library/Application Support/WorkBuddy/User/settings.json` 中查找：

```json
"wecom.channels.weixinBot.extra": {
  "botToken": "xxx@im.bot:token",
  "userId": "o9cq8024xxx@im.wechat",
  "baseUrl": "https://ilinkai.weixin.qq.com"
}
```

- `botToken` 的 `:` 后即为 `bot_token`
- `userId` 直接填入 `user_id`

## 工作原理

```
WorkBuddy 自动化触发
    ↓
automation_runs 表状态更新为 ARCHIVED
    ↓
bridge.py 轮询检测到变化
    ↓
通过 ilinkai API 主动发送消息到微信
    ↓
你在微信 Clawbot 窗口收到消息
```

## macOS 服务管理

```bash
# 卸载服务
./uninstall.sh

# 查看运行状态
launchctl list | grep workbuddy-wechat-bridge

# 查看日志
tail -f ~/Library/Logs/workbuddy-wechat-bridge.log
```

## 许可证

MIT
