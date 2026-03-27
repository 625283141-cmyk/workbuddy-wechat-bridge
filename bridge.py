#!/usr/bin/env python3
"""
WorkBuddy WeChat Bridge
监听 WorkBuddy 自动化任务完成，主动推送结果到微信
"""

import asyncio
import base64
import json
import logging
import os
import random
import sqlite3
import ssl
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
import urllib.request

# ─── 配置 ──────────────────────────────────────────
DEFAULT_DB_PATH = (
    "/Users/YOUKNOWWHO/Library/Application Support/WorkBuddy"
    "/automations/automations.db"
)
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"
POLL_INTERVAL = 30  # 秒


@dataclass
class Config:
    bot_token: str
    user_id: str
    base_url: str = "https://ilinkai.weixin.qq.com"
    db_path: str = DEFAULT_DB_PATH
    poll_interval: int = POLL_INTERVAL

    @classmethod
    def from_file(cls, path: Path) -> "Config":
        with open(path) as f:
            data = json.load(f)
        return cls(
            bot_token=data["bot_token"],
            user_id=data["user_id"],
            base_url=data.get("base_url", "https://ilinkai.weixin.qq.com"),
            db_path=data.get("db_path", DEFAULT_DB_PATH),
            poll_interval=data.get("poll_interval", POLL_INTERVAL),
        )


# ─── 日志 ──────────────────────────────────────────
LOG_DIR = Path.home() / "Library" / "Logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "workbuddy-wechat-bridge.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("wb-bridge")


# ─── ilinkai API ──────────────────────────────────
class ILinkAIClient:
    """微信 ilinkai 协议客户端"""

    def __init__(self, bot_token: str, user_id: str,
                 base_url: str = "https://ilinkai.weixin.qq.com"):
        self.bot_token = bot_token
        self.user_id = user_id
        self.base_url = base_url
        self.channel_version = "1.0.3"

    def _build_headers(self) -> dict:
        uin_bytes = str(random.randint(0, 0xFFFFFFFF)).encode()
        return {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {self.bot_token}",
            "X-WECHAT-UIN": base64.b64encode(uin_bytes).decode(),
        }

    def _post(self, endpoint: str, body: dict) -> dict:
        body["base_info"] = {"channel_version": self.channel_version}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = self._build_headers()
        headers["Content-Length"] = str(len(raw))

        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=raw,
            headers=headers,
            method="POST",
        )
        ctx = ssl._create_unverified_context()
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
            text = resp.read().decode()
            return json.loads(text) if text.strip() and text != "{}" else {"ret": 0}
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            log.error(f"HTTP {e.code}: {body_text}")
            return {"ret": e.code, "error": body_text}
        except Exception as e:
            log.error(f"Request failed: {e}")
            return {"ret": -1, "error": str(e)}

    def send_text(self, text: str,
                  context_token: Optional[str] = None) -> bool:
        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": self.user_id,
                "client_id": f"wb-bridge-{uuid.uuid4().hex[:12]}",
                "message_type": 2,
                "message_state": 2,
                "context_token": context_token or "",
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }
        }
        result = self._post("/ilink/bot/sendmessage", body)
        ok = result.get("ret") == 0
        log.info(f"Send result ret={result.get('ret')}, ok={ok}")
        return ok

    def get_updates(self) -> list:
        """获取新消息（包含 context_token）"""
        body = {"get_updates_buf": ""}
        result = self._post("/ilink/bot/getupdates", body)
        return result.get("msgs", [])


# ─── 数据库监控 ────────────────────────────────────
async def check_new_runs(db_path: str,
                         last_run_id: Optional[str] = None
                         ) -> tuple[list[dict], str]:
    """检查新增的 ARCHIVED 自动化运行"""
    new_runs = []
    latest_id = last_run_id or ""

    try:
        async with aiosqlite.connect(db_path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT automation_id, status, read_at, created_at, runs_json
                FROM automation_runs
                WHERE status = 'ARCHIVED' AND read_at IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 50
                """
            )
            if not rows:
                return [], latest_id

            for row in rows:
                automation_id, status, read_at, created_at, _ = row
                run_id = f"{automation_id}:{created_at}"

                if last_run_id is None:
                    if not latest_id:
                        latest_id = run_id
                    continue

                if run_id != last_run_id:
                    new_runs.append({
                        "automation_id": automation_id,
                        "status": status,
                        "created_at": created_at,
                        "read_at": read_at,
                        "run_id": run_id,
                    })
                else:
                    break

            if rows:
                latest_id = f"{rows[0][0]}:{rows[0][3]}"

    except Exception as e:
        log.error(f"Database error: {e}")

    return new_runs, latest_id


def build_message(run: dict, cfg: Config) -> str:
    """根据任务类型构建通知文案"""
    aid = run["automation_id"]
    ts = datetime.fromtimestamp(run["created_at"] / 1000)
    name_map = {
        "instreet": "InStreet 见闻汇报",
        "automation-4": "午餐灵感",
        "automation-5": "自动化测试",
    }
    title = name_map.get(aid, "WorkBuddy 任务")
    return (f"WorkBuddy 任务完成\n\n"
            f"任务: {title}\n"
            f"时间: {ts.strftime('%H:%M')}\n\n"
            f"请前往 WorkBuddy 查看详情。")


# ─── 主循环 ────────────────────────────────────────
async def main_loop(cfg: Config):
    client = ILinkAIClient(cfg.bot_token, cfg.user_id, cfg.base_url)
    last_run_id = None
    errors = 0

    log.info("Bridge started")
    log.info(f"DB: {cfg.db_path}")

    while True:
        try:
            new_runs, latest_id = await check_new_runs(cfg.db_path, last_run_id)

            for run in reversed(new_runs):
                msg = build_message(run, cfg)
                if client.send_text(msg):
                    log.info(f"Notified: {run['run_id']}")
                else:
                    log.warning(f"Failed: {run['run_id']}")
                    errors += 1

            if new_runs:
                last_run_id = latest_id

        except Exception as e:
            log.error(f"Poll error: {e}")
            errors += 1

        if errors >= 5:
            await asyncio.sleep(60)
            errors = 0

        await asyncio.sleep(cfg.poll_interval)


# ─── CLI ───────────────────────────────────────────
import argparse

def cli():
    parser = argparse.ArgumentParser(description="WorkBuddy WeChat Bridge")
    parser.add_argument("--test", "-t", metavar="TEXT",
                        help="发送测试消息后退出")
    parser.add_argument("--config", "-c", type=Path,
                        default=DEFAULT_CONFIG_PATH,
                        help="配置文件路径")
    args = parser.parse_args()

    if not Path(args.config).exists():
        print(f"配置文件不存在: {args.config}")
        return

    cfg = Config.from_file(args.config)
    client = ILinkAIClient(cfg.bot_token, cfg.user_id, cfg.base_url)

    if args.test:
        ok = client.send_text(args.test)
        print("发送成功" if ok else "发送失败，请查看日志")
        return

    try:
        asyncio.run(main_loop(cfg))
    except KeyboardInterrupt:
        log.info("Stopped")


if __name__ == "__main__":
    cli()
