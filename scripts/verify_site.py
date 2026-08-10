#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建后站点校验。
检查 dist/ 产物：资源存在、内部链接可解析、每页 H1 唯一、敏感内容扫描。
退出码 0 = 通过，非 0 = 发现问题，阻止发布。

设计意图：preflight.py 只检查源文件（且忽略 dist/），无法发现构建产物中的
路径错误或信息泄漏。本脚本在 build 之后运行，专门校验 dist/，补上这一环。
"""
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

DIST_DIR = Path(__file__).resolve().parent.parent / "dist"

# 敏感内容模式（与 preflight 一致，但这里是扫描产物，所有命中都是真实泄漏）
SENSITIVE_PATTERNS = [
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}", re.IGNORECASE), "GitHub Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{40,}", re.IGNORECASE), "GitHub PAT"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "私钥块"),
    (re.compile(r"AGENTS\.md"), "知识库维护协议引用"),
    (re.compile(r"chatgpt-conversation://"), "对话内部链接"),
    (re.compile(r"publication_status:", re.MULTILINE), "知识库内部 frontmatter 字段"),
    (re.compile(r"knowledge_planet_|public_learning_site_"), "知识库协议字段"),
    # 本地绝对路径（Windows 带用户名）
    (re.compile(r"[A-Z]:\\Users\\[^\\]+\\", re.IGNORECASE), "本地绝对路径"),
]


class LinkCollector(HTMLParser):
    """收集 HTML 中的 href/src 引用和 H1 标签。"""

    def __init__(self):
        super().__init__()
        self.links = []       # 内部链接（href 值）
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.h1_count += 1
        for attr_name, attr_val in attrs:
            if attr_name in ("href", "src") and attr_val:
                self.links.append(attr_val)


def verify():
    if not DIST_DIR.exists():
        print("verify_site 失败：dist/ 目录不存在，请先运行 build.py。")
        sys.exit(2)

    errors = []
    warnings_list = []
    html_files = list(DIST_DIR.rglob("*.html"))

    if not html_files:
        errors.append("dist/ 中没有 HTML 文件")

    for html_file in html_files:
        rel_path = html_file.relative_to(DIST_DIR)
        content = html_file.read_text(encoding="utf-8")

        # 1. 敏感内容扫描
        for pattern, name in SENSITIVE_PATTERNS:
            for m in pattern.finditer(content):
                errors.append(f"敏感内容 [{name}]: {rel_path} -> {m.group(0)[:60]}")

        # 2. 解析链接和 H1
        collector = LinkCollector()
        collector.feed(content)

        # 3. H1 唯一性检查（每页应有且仅有 1 个 H1）
        if collector.h1_count > 1:
            errors.append(f"H1 重复: {rel_path} 包含 {collector.h1_count} 个 <h1>（应为 1）")
        elif collector.h1_count == 0:
            warnings_list.append(f"H1 缺失: {rel_path}（应为 1）")

        # 4. 内部链接可解析性检查
        page_depth = len(rel_path.parts) - 1  # index.html 在根 = 0 深度
        for link in collector.links:
            # 跳过外链、锚点、协议链接
            if link.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            # 解析相对链接
            # 去掉锚点
            link_path = link.split("#")[0]
            if not link_path:
                continue
            target = (html_file.parent / link_path).resolve()
            try:
                target_rel = target.relative_to(DIST_DIR)
            except ValueError:
                errors.append(f"内部链接越界: {rel_path} -> {link}")
                continue
            if not target.exists():
                errors.append(f"内部链接失效: {rel_path} -> {link} (解析为 {target_rel})")

    # 5. 必需资源检查：assets/style.css 必须存在
    required_assets = ["assets/style.css"]
    for asset in required_assets:
        if not (DIST_DIR / asset).exists():
            errors.append(f"必需资源缺失: {asset}")

    # 6. 搜索索引检查
    search_index = DIST_DIR / "search-index.json"
    if not search_index.exists():
        errors.append("search-index.json 缺失")

    if warnings_list:
        print("站点校验警告：")
        for w in warnings_list:
            print(f"  ⚠ {w}")

    if errors:
        print("站点校验未通过：")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        msg = f"站点校验通过：{len(html_files)} 个 HTML 页面，链接/H1/资源/敏感内容均 OK。"
        if warnings_list:
            msg += f"（{len(warnings_list)} 个警告）"
        print(msg)
        sys.exit(0)


if __name__ == "__main__":
    verify()
