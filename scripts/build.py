#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android 面试学习站静态构建脚本。
读取 posts/*.md，清洗仅供内部维护的 frontmatter 字段，生成纯静态 HTML 站点到 dist/。

设计原则（符合公开学习站协议）：
- 只读 posts/ 和模板，不依赖知识库私有内容。
- 不引入第三方依赖，仅用 Python 标准库。
- 导出时移除内部维护字段（type/status/publication_status），保留公开元信息。
- 生成首页、文章页、Day 导航、标签页、上一篇/下一篇、移动端布局。
"""
import html
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
DIST_DIR = ROOT / "dist"
TEMPLATE_DIR = ROOT / "templates"

# 允许保留并写入页面的 frontmatter 字段（公开元信息）
PUBLIC_FIELDS = {"title", "tags", "created", "updated", "sources", "day"}
# 导出时移除的内部维护字段
INTERNAL_FIELDS = {"type", "status", "publication_status", "github_pages_status",
                   "github_pages_published_at", "github_pages_url"}


def parse_frontmatter(text):
    """解析 YAML frontmatter（仅处理扁平 key 与简单列表，够用即可）。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    current_key = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key:
            value = stripped[2:].strip().strip('"').strip("'")
            if isinstance(meta.get(current_key), list):
                meta[current_key].append(value)
            else:
                meta[current_key] = [value]
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value == "":
                meta[key] = []
                current_key = key
            else:
                meta[key] = value
                current_key = key
    return meta, body


def md_to_html(md_text):
    """极简 Markdown → HTML 转换，覆盖学习站用到的语法子集。"""
    lines = md_text.split("\n")
    out = []
    in_code = False
    code_lang = ""
    in_list = False
    in_ol = False

    def flush_list():
        nonlocal in_list, in_ol
        if in_list:
            out.append("</ul>")
            in_list = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for raw in lines:
        line = raw.rstrip()
        # 代码块
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                info = line[3:].strip()
                code_lang = f' class="language-{html.escape(info)}"' if info else ""
                out.append(f'<pre><code{code_lang}>')
                in_code = True
            continue
        if in_code:
            out.append(html.escape(raw))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_list()
            level = len(m.group(1))
            text = inline(m.group(2))
            out.append(f"<h{level}>{text}</h{level}>")
            continue

        # 引用
        if line.startswith("> "):
            flush_list()
            out.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            continue

        # 分隔线
        if line.strip() in ("---", "***", "___"):
            flush_list()
            out.append("<hr>")
            continue

        # 无序列表
        if re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                flush_list()
                out.append("<ul>")
                in_list = True
            content = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline(content)}</li>")
            continue

        # 有序列表
        if re.match(r"^\s*\d+\.\s+", line):
            if not in_ol:
                flush_list()
                out.append("<ol>")
                in_ol = True
            content = re.sub(r"^\s*\d+\.\s+", "", line)
            out.append(f"<li>{inline(content)}</li>")
            continue

        # 空行
        if not line.strip():
            flush_list()
            out.append("")
            continue

        # 普通段落
        flush_list()
        out.append(f"<p>{inline(line)}</p>")

    flush_list()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def inline(text):
    """处理行内语法：code、bold、link、hashtag。"""
    # 转义 HTML
    text = html.escape(text, quote=False)
    # 行内代码 `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # 粗体 **text**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Markdown 链接 [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>',
                  text)
    # hashtag #标签
    text = re.sub(r"(^|\s)#([^\s#<]+)",
                  lambda m: f'{m.group(1)}<a class="tag" href="../tags.html#{html.escape(m.group(2))}">#{m.group(2)}</a>',
                  text)
    return text


def load_posts():
    """加载并清洗所有文章，按 day 排序。"""
    posts = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        # 清洗：只保留公开字段
        public_meta = {k: v for k, v in meta.items()
                       if k in PUBLIC_FIELDS and k not in INTERNAL_FIELDS}
        posts.append({
            "meta": public_meta,
            "body": body,
            "slug": md_file.stem,
            "raw_meta": meta,
        })
    posts.sort(key=lambda p: int(p["raw_meta"].get("day", 0)))
    return posts


def build():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    posts = load_posts()
    if not posts:
        raise SystemExit("No posts found in posts/")

    # 收集标签
    all_tags = {}
    for p in posts:
        tags = p["raw_meta"].get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            all_tags.setdefault(t, []).append(p)

    # 渲染每篇文章
    for i, p in enumerate(posts):
        prev = posts[i - 1] if i > 0 else None
        nxt = posts[i + 1] if i < len(posts) - 1 else None
        html_content = render_post(p, prev, nxt)
        out_dir = DIST_DIR / "post" / p["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html_content, encoding="utf-8")

    # 首页
    (DIST_DIR / "index.html").write_text(render_index(posts), encoding="utf-8")
    # 标签页
    (DIST_DIR / "tags.html").write_text(render_tags(all_tags, posts), encoding="utf-8")

    # 复制静态资源
    assets_src = ROOT / "assets"
    if assets_src.exists():
        for f in assets_src.glob("*"):
            shutil.copy(f, DIST_DIR / f.name)

    # 生成站点元数据 JSON（供客户端搜索用）
    search_index = []
    for p in posts:
        meta = p["raw_meta"]
        search_index.append({
            "slug": p["slug"],
            "title": meta.get("title", p["slug"]),
            "day": meta.get("day", ""),
            "tags": meta.get("tags", []) if isinstance(meta.get("tags"), list) else [meta.get("tags", "")],
            "summary": extract_summary(p["body"]),
        })
    (DIST_DIR / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Built {len(posts)} posts into {DIST_DIR}")


def extract_summary(body):
    """提取「摘要」段作为列表项简介。"""
    m = re.search(r"##\s*摘要.*?\n([\s\S]*?)(?=\n##\s|\Z)", body)
    if m:
        return re.sub(r"<[^>]+>", "", inline(m.group(1).strip()))[:200]
    # fallback：取第一段
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith(">"):
            return line[:200]
    return ""


SITE_TITLE = "Android 面试学习笔记"
SITE_SUBTITLE = "Kotlin · 协程 · Android 进阶 · 8 周系统复习"


def page_template(title, content, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} · {SITE_TITLE}</title>
<link rel="stylesheet" href="{extra_head or '../assets/style.css'}">
</head>
<body>
<nav class="topnav">
  <a class="brand" href="../index.html">{SITE_TITLE}</a>
  <div class="nav-links">
    <a href="../index.html">目录</a>
    <a href="../tags.html">标签</a>
  </div>
</nav>
<main>
{content}
</main>
<footer>
  <p>{SITE_TITLE} · 内容以 <a href="https://kotlinlang.org/docs/home.html">Kotlin 官方文档</a> 为准</p>
</footer>
</body>
</html>"""


def render_index(posts):
    items = []
    for p in posts:
        meta = p["raw_meta"]
        day = meta.get("day", "?")
        title = meta.get("title", p["slug"])
        summary = extract_summary(p["body"])
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        tags_html = "".join(f'<a class="tag" href="tags.html#{html.escape(t)}">#{html.escape(t)}</a>'
                            for t in tags)
        items.append(f"""
<article class="post-item">
  <h2><a href="post/{p["slug"]}/index.html">{html.escape(title)}</a></h2>
  <div class="meta">Day {html.escape(str(day))} · {html.escape(str(meta.get('updated', meta.get('created', ''))))}</div>
  <p class="summary">{html.escape(summary)}</p>
  <div class="tags">{tags_html}</div>
</article>""")
    content = f"""
<header class="hero">
  <h1>{SITE_TITLE}</h1>
  <p class="subtitle">{SITE_SUBTITLE}</p>
</header>
<div class="post-list">{''.join(items)}
</div>"""
    # 首页样式路径调整
    return page_template("首页", content, extra_head="assets/style.css").replace('href="../assets/style.css"', 'href="assets/style.css"').replace('href="../index.html"', 'href="index.html"').replace('href="../tags.html"', 'href="tags.html"')


def render_post(p, prev, nxt):
    meta = p["raw_meta"]
    title = meta.get("title", p["slug"])
    body_html = md_to_html(p["body"])
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    tags_html = "".join(f'<a class="tag" href="../tags.html#{html.escape(t)}">#{html.escape(t)}</a>'
                        for t in tags)
    sources = meta.get("sources", [])
    if isinstance(sources, str):
        sources = [sources]
    sources_html = ""
    if sources:
        sources_html = '<div class="sources"><strong>来源：</strong>' + ", ".join(
            f'<a href="{html.escape(s)}" rel="noopener">{html.escape(s)}</a>' for s in sources
        ) + '</div>'

    prev_html = ""
    if prev:
        prev_title = prev["raw_meta"].get("title", prev["slug"])
        prev_html = f'<a class="nav-prev" href="../{prev["slug"]}/index.html">← {html.escape(prev_title)}</a>'
    nxt_html = ""
    if nxt:
        nxt_title = nxt["raw_meta"].get("title", nxt["slug"])
        nxt_html = f'<a class="nav-next" href="../{nxt["slug"]}/index.html">{html.escape(nxt_title)} →</a>'

    content = f"""
<article class="post">
  <header class="post-header">
    <h1>{html.escape(title)}</h1>
    <div class="post-meta">Day {html.escape(str(meta.get('day', '')))} · 更新于 {html.escape(str(meta.get('updated', '')))}</div>
    <div class="tags">{tags_html}</div>
  </header>
  <div class="post-body">
{body_html}
  </div>
  {sources_html}
  <nav class="post-nav">
    {prev_html}
    {nxt_html}
  </nav>
</article>"""
    return page_template(title, content)


def render_tags(all_tags, posts):
    sections = []
    for tag in sorted(all_tags.keys()):
        items = []
        for p in all_tags[tag]:
            meta = p["raw_meta"]
            title = meta.get("title", p["slug"])
            items.append(f'<li><a href="post/{p["slug"]}/index.html">{html.escape(title)}</a> <span class="day-tag">Day {html.escape(str(meta.get("day", "")))}</span></li>')
        sections.append(f"""
<section id="{html.escape(tag)}" class="tag-section">
  <h2>#{html.escape(tag)}</h2>
  <ul class="tag-list">{''.join(items)}
  </ul>
</section>""")
    content = f"""
<header class="hero">
  <h1>标签</h1>
</header>
<div class="tags-page">{''.join(sections)}
</div>"""
    return page_template("标签", content, extra_head="assets/style.css").replace('href="../assets/style.css"', 'href="assets/style.css"').replace('href="../index.html"', 'href="index.html"').replace('href="../tags.html"', 'href="tags.html"')


if __name__ == "__main__":
    build()
