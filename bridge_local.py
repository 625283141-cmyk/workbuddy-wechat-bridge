#!/usr/bin/env python3
"""
WorkBuddy WeChat Bridge - Cassie 专用版
凭证硬编码在文件顶部，不上传 Git

使用方式：
  python3 bridge_local.py                        # 启动桥接服务
  python3 bridge_local.py --once                 # 单次轮询（用于测试）
  python3 bridge_local.py --test "消息内容"      # 发送测试消息
  python3 bridge_local.py --status               # 查看服务状态
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import random
import ssl
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import urllib.request

# ─── Cassie 专属凭证（勿上传 Git）─────────────────────
BOT_TOKEN = "271cd3e66797@im.bot:060000543474e63f0144e66fb181eda815f14b"
USER_ID   = "o9cq8024h2lYygHTVskCVEp4eBLo@im.wechat"
BASE_URL  = "https://ilinkai.weixin.qq.com"
# ──────────────────────────────────────────────────────

DB_PATH       = "/Users/YOUKNOWWHO/Library/Application Support/WorkBuddy/automations/automations.db"
POLL_INTERVAL = 30  # 秒
MAX_RETRIES   = 3

LOG_DIR = Path.home() / "Library" / "Logs" / "WorkBuddyBridge"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bridge.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("wb-bridge")


# ─── ilinkai API ──────────────────────────────────
def send_message(content: str) -> bool:
    """通过 ilinkai 协议发送微信消息"""
    uin_bytes = str(random.randint(0, 0xFFFFFFFF)).encode()
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {BOT_TOKEN}",
        "X-WECHAT-UIN": base64.b64encode(uin_bytes).decode(),
    }

    body = {
        "base_info": {"channel_version": "1.0.3"},
        "msg": {
            "from_user_id": "",
            "to_user_id": USER_ID,
            "client_id": f"wb-bridge-{uuid.uuid4().hex[:12]}",
            "message_type": 2,
            "message_state": 2,
            "context_token": "",
            "item_list": [{"type": 1, "text_item": {"text": content}}],
        },
    }

    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers["Content-Length"] = str(len(raw))

    req = urllib.request.Request(
        f"{BASE_URL}/ilink/bot/sendmessage",
        data=raw, headers=headers, method="POST"
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            text = resp.read().decode()
            result = json.loads(text) if text.strip() and text != "{}" else {"ret": 0}
            ok = result.get("ret") == 0
            logger.info(f"Send result ret={result.get('ret')}, ok={ok}")
            return ok
    except Exception as e:
        logger.error(f"Send failed: {e}")
        return False


# ─── 数据库监控 ────────────────────────────────────
async def poll_new_runs(last_run_id: Optional[str] = None) -> tuple[list, str]:
    """检查新增的 ARCHIVED 自动化运行"""
    if not os.path.exists(DB_PATH):
        logger.warning(f"数据库不存在：{DB_PATH}")
        return [], last_run_id or ""

    new_runs = []
    latest_run_id = last_run_id or ""

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall("""
                SELECT automation_id, status, read_at, created_at
                FROM automation_runs
                WHERE status = 'ARCHIVED' AND read_at IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 50
            """)
            if not rows:
                return [], latest_run_id

            for row in rows:
                run_id = f"{row['automation_id']}:{row['created_at']}"
                if last_run_id is None:
                    if not latest_run_id:
                        latest_run_id = run_id
                    continue
                if run_id != last_run_id:
                    new_runs.append({
                        "automation_id": row["automation_id"],
                        "created_at": row["created_at"],
                        "run_id": run_id,
                    })
                else:
                    break

            if rows:
                latest_run_id = f"{rows[0]['automation_id']}:{rows[0]['created_at']}"

    except Exception as e:
        logger.error(f"数据库读取失败: {e}")

    return new_runs, latest_run_id


def build_message(run: dict) -> str:
    """根据任务类型构建通知文案"""
    aid = run["automation_id"]
    ts = datetime.fromtimestamp(run["created_at"] / 1000)
    name_map = {
        "instreet": "InStreet 见闻汇报",
        "automation-4": "午餐灵感",
        "automation-5": "自动化测试",
    }
    title = name_map.get(aid, "WorkBuddy 任务")
    return (
        f"WorkBuddy 任务完成\n\n"
        f"任务: {title}\n"
        f"时间: {ts.strftime('%H:%M')}\n\n"
        f"请前往 WorkBuddy 查看详情。"
    )


# ─── 主循环 ────────────────────────────────────────
async def run():
    """主循环"""
    logger.info("=" * 50)
    logger.info("WorkBuddy WeChat Bridge 已启动（本地版）")
    logger.info(f"轮询间隔：{POLL_INTERVAL}秒")
    logger.info(f"数据库：{DB_PATH}")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 50)

    last_run_id = None
    errors = 0

    while True:
        try:
            new_runs, latest_id = await poll_new_runs(last_run_id)

            for run in reversed(new_runs):
                msg = build_message(run)
                ok = send_message(msg)
                if ok:
                    logger.info(f"通知已发送: {run['run_id']}")
                else:
                    logger.warning(f"发送失败: {run['run_id']}")
                    errors += 1

            if new_runs:
                last_run_id = latest_id

        except Exception as e:
            logger.error(f"轮询异常: {e}")
            errors += 1

        if errors >= 5:
            await asyncio.sleep(60)
            errors = 0

        await asyncio.sleep(POLL_INTERVAL)


# ─── CLI ───────────────────────────────────────────
def cmd_test(message: str):
    logger.info(f"发送测试消息：{message}")
    ok = send_message(message)
    print("✅ 发送成功！请检查微信。" if ok else "❌ 发送失败，请查看日志。")


def cmd_once():
    tasks, _ = asyncio.run(poll_new_runs(None))
    if not tasks:
        print("没有新的已完成任务。")
    else:
        print(f"发现 {len(tasks)} 个已完成任务：")
        for t in tasks:
            ts = datetime.fromtimestamp(t["created_at"] / 1000)
            print(f"  [{ts.strftime('%H:%M')}] {t['automation_id']}")


def cmd_status():
    print("=== 状态 ===")
    print(f"数据库：{DB_PATH}")
    print(f"数据库存在：{os.path.exists(DB_PATH)}")
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT COUNT(*) FROM automation_runs WHERE status='ARCHIVED' AND read_at IS NOT NULL"
        )
        print(f"已完成任务总数：{cur.fetchone()[0]}")
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WorkBuddy WeChat Bridge")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--test", type=str)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.test:
        cmd_test(args.test)
    elif args.status:
        cmd_status()
    elif args.once:
        cmd_once()
    else:
        asyncio.run(run())
