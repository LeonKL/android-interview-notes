#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布前扫描：白名单检查 + 敏感信息扫描。
协议要求：推送前执行白名单检查，扫描密码/Token/Cookie/私钥/本地绝对路径/对话提示词/未授权业务信息。
退出码 0 = 通过，非 0 = 发现风险，阻止发布。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 公开站允许的顶层文件/目录白名单
ALLOWED_TOPLEVEL = {
    "posts", "assets", "scripts", ".github", ".gitignore",
    "README.md", "LICENSE",
}
# 本地构建产物，不进仓库（已在 .gitignore），扫描时忽略
IGNORED_TOPLEVEL = {"dist", "__pycache__", ".git"}

# 允许出现在 posts/ 里的文章（草稿导出后的文件名）。
# 静态白名单：发布新文章时，必须先在此处追加对应文件名，且获得用户明确发布授权。
# 之所以用静态白名单而非「放行所有 posts/*.md」，是为了在 CI 阶段就拦截未经授权的文章。
ALLOWED_POSTS = {f"day-{i:02d}.md" for i in range(1, 9)}

# 敏感信息模式
SENSITIVE_PATTERNS = [
    (r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9]{20,}", "GitHub Token"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----", "私钥"),
    (r"(?:password|passwd|pwd)\s*[=:]\s*\S+", "疑似密码"),
    (r"(?:secret|api[_-]?key)\s*[=:]\s*[A-Za-z0-9_\-]{16,}", "疑似密钥"),
    (r"(?:cookie)\s*[=:]\s*\S{16,}", "疑似 Cookie"),
    # 本地 Windows 绝对路径（含用户名）
    (r"[A-Z]:\\Users\\[^\\]+\\", "本地绝对路径（含用户目录）"),
    # 智能体内部协议引用
    (r"AGENTS\.md", "知识库维护协议引用"),
    (r"chatgpt-conversation://", "对话内部链接"),
    (r"knowledge-planet-day-NN\.md", "草稿文件名模板引用"),
    (r"\[\[.+\|.+?\]\]", "Obsidian 内部 wiki 链接"),
    # 知识库内部维护字段
    (r"^publication_status:", "知识库内部 frontmatter 字段"),
    (r"^knowledge_planet_", "知识库进度协议字段"),
    (r"^public_learning_site_", "知识库部署协议字段"),
]
SENSITIVE_RES = [(re.compile(p, re.MULTILINE | re.IGNORECASE), name)
                 for p, name in SENSITIVE_PATTERNS]

# 允许提及的 URL 协议和域名（白名单内的链接放行）
URL_ALLOW = re.compile(r"https://(?:kotlinlang\.org|developer\.android\.com|docs\.github\.com|cli\.github\.com)/")


def scan():
    errors = []

    # 1. 白名单：列出仓库根下所有顶层条目（忽略构建产物和缓存）
    for entry in ROOT.iterdir():
        name = entry.name
        if name in IGNORED_TOPLEVEL:
            continue
        if name not in ALLOWED_TOPLEVEL:
            errors.append(f"白名单外顶层条目: {name}")

    # 2. posts/ 里只允许白名单内的文章
    posts_dir = ROOT / "posts"
    if posts_dir.exists():
        for f in posts_dir.iterdir():
            if f.name not in ALLOWED_POSTS:
                errors.append(
                    f"白名单外文章: posts/{f.name}。"
                    f"如需发布新文章，须先获得用户明确授权，"
                    f"再在 scripts/preflight.py 的 ALLOWED_POSTS 中追加 '{f.name}'。"
                )

    # 3. 敏感信息扫描：扫描内容文件和站点配置（不扫描 scripts/ 内的清洗规则字符串字面量）
    #    scripts/ 里会出现 "AGENTS.md" "chatgpt-conversation://" 等字符串，那是清洗逻辑用来
    #    识别并移除内部内容的，不是泄漏；真正要保证的是导出产物（posts/、dist/）里没有这些。
    scan_dirs = [ROOT / "posts", ROOT / "assets",
                 ROOT / ".github", ROOT / "README.md", ROOT / ".gitignore"]
    scanned = 0
    for target in scan_dirs:
        if target.is_file():
            files = [target]
        else:
            files = list(target.rglob("*"))
        for f in files:
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            scanned += 1
            for pattern, name in SENSITIVE_RES:
                for m in pattern.finditer(content):
                    # 放行：URL_ALLOW 命中且本质是官方文档链接
                    snippet = m.group(0)
                    if URL_ALLOW.search(snippet):
                        continue
                    rel = f.relative_to(ROOT)
                    errors.append(f"敏感信息 [{name}]: {rel} -> {snippet[:60]}")

    # 4. 单独扫描 scripts/ 的 Python 字符串字面量：只检查会被输出到站点的风险，
    #    跳过清洗规则本身的模式串。具体地，扫描 scripts/ 是否含真实凭据（非字面量占位）。
    scripts_dir = ROOT / "scripts"
    if scripts_dir.exists():
        # 只查真实凭据模式，不查清洗规则占位符
        real_credential_patterns = [
            (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "真实 GitHub Token"),
            (re.compile(r"github_pat_[A-Za-z0-9_]{40,}"), "真实 GitHub PAT"),
            (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "私钥块"),
        ]
        for f in scripts_dir.rglob("*.py"):
            try:
                content = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            scanned += 1
            for pattern, name in real_credential_patterns:
                for m in pattern.finditer(content):
                    rel = f.relative_to(ROOT)
                    errors.append(f"敏感信息 [{name}]: {rel} -> {m.group(0)[:60]}")

    if errors:
        print("发布前扫描未通过：")
        for e in errors:
            print(f"  - {e}")
        print(f"\n共扫描 {scanned} 个文本文件，发现 {len(errors)} 处问题。")
        sys.exit(1)
    else:
        print(f"发布前扫描通过：白名单与敏感信息检查均 OK（扫描 {scanned} 个文件）。")
        sys.exit(0)


if __name__ == "__main__":
    scan()
