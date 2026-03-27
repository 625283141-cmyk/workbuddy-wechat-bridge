#!/usr/bin/env python3
"""
setup_github.py - 将项目推送到 GitHub
运行一次即可，之后正常 git 推送即可
"""

import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

import json, urllib.request, urllib.parse

TOKEN = "YOUR_GITHUB_TOKEN_HERE"  # <-- 替换为你的 GitHub Personal Access Token
OWNER = "625283141-cmyk"
REPO = "workbuddy-wechat-bridge"
DESCRIPTION = "WorkBuddy automation to WeChat bridge via ilinkai protocol"
PRIVATE = False

def main():
    # 1. 创建仓库
    req = urllib.request.Request(
        "https://api.github.com/user/repos",
        data=json.dumps({
            "name": REPO,
            "description": Description,
            "private": PRIVATE,
            "auto_init": False,
        }).encode(),
        headers={
            "Authorization": f"token {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "workbuddy-wechat-bridge",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"✅ Repo created: {data.get('html_url')}")
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        if "name already exists" in body.get("message", ""):
            print("ℹ️  Repo already exists, skipping creation")
        else:
            print(f"❌ 创建仓库失败: {body}")
            return

    # 2. 初始化 git 并推送
    import subprocess, os
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(proj_dir)

    subprocess.run(["git", "init"], check=True)
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit: WorkBuddy WeChat Bridge"], check=True)
    subprocess.run([
        "git", "remote", "add", "origin",
        f"https://{OWNER}:{TOKEN}@github.com/{OWNER}/{REPO}.git"
    ], check=True)
    subprocess.run(["git", "branch", "-M", "main"], check=True)
    subprocess.run(["git", "push", "-u", "origin", "main", "--force"], check=True)
    print("✅ Pushed to GitHub!")

if __name__ == "__main__":
    main()
