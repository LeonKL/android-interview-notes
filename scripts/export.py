#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从知识库草稿导出公开文章到 posts/。
清洗规则（符合公开学习站协议）：
- 移除仅供内部维护的 frontmatter 字段：type、status、publication_status、
  github_pages_* 等知识库进度/部署字段。
- 保留公开元信息：title、tags、created、updated、sources、day。
- 移除 frontmatter 中指向知识库内部的来源（chatgpt-conversation:// 等）。
- 文件名规范化为 day-NN.md。
"""
import re
import shutil
import sys
from pathlib import Path

KB_REPORTS = Path(r"E:/知识库/wiki/reports")
OUT_POSTS = Path(__file__).resolve().parent.parent / "posts"

# 内部维护字段，导出时移除
INTERNAL_FIELDS = {
    "type", "status", "publication_status",
    "github_pages_status", "github_pages_published_at", "github_pages_url",
}
# 公开字段，保留
PUBLIC_FIELDS = {"title", "tags", "created", "updated", "sources", "day"}


def parse_frontmatter_raw(text):
    """返回 (frontmatter 原始块文本, 正文)。"""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    fm = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    return fm, body


def clean_frontmatter(fm_text):
    """逐行清洗 frontmatter：移除内部字段和内部来源链接。"""
    lines = fm_text.splitlines()
    out = []
    skip_list = False  # 正在处理一个要移除的列表字段
    for line in lines:
        stripped = line.strip()
        # 列表项
        if stripped.startswith("- "):
            if skip_list:
                continue
            value = stripped[2:].strip()
            # 移除对话内部链接来源
            if "chatgpt-conversation://" in value or "raw/" in value or "AGENTS.md" in value:
                continue
            out.append(line)
            continue
        # key: value
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            if key in INTERNAL_FIELDS:
                # 如果这个字段下面跟着列表项，要跳过它们
                skip_list = m.group(2) == ""
                continue
            else:
                skip_list = False
                # sources: 为空时后面跟列表，正常；其他字段直接保留
                out.append(line)
                continue
        else:
            skip_list = False
            out.append(line)
    # 清理末尾空行
    return "\n".join(out).rstrip() + "\n"


def export():
    OUT_POSTS.mkdir(parents=True, exist_ok=True)
    # 清空旧文件（仅清 posts 目录，不动其他）
    for f in OUT_POSTS.glob("*.md"):
        f.unlink()

    count = 0
    for i in range(1, 10):
        src = KB_REPORTS / f"knowledge-planet-day-{i:02d}.md"
        if not src.exists():
            print(f"警告：源文件不存在 {src}", file=sys.stderr)
            continue
        text = src.read_text(encoding="utf-8")
        fm_text, body = parse_frontmatter_raw(text)
        cleaned_fm = clean_frontmatter(fm_text)
        out_text = f"---\n{cleaned_fm}---\n\n{body}"
        dst = OUT_POSTS / f"day-{i:02d}.md"
        dst.write_text(out_text, encoding="utf-8")
        count += 1
        print(f"导出 {src.name} -> posts/{dst.name}")
    print(f"\n共导出 {count} 篇文章到 {OUT_POSTS}")


if __name__ == "__main__":
    export()
