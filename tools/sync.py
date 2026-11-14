#!/usr/bin/env python3
"""cinema-log 同步脚本：以 shows.json 为唯一数据源，自动生成首页与 README。

用法：
    python3 tools/sync.py            # 重新生成 index.html 与 README.md
    python3 tools/sync.py --check    # 只校验，不写文件

新增一部剧的流程：
    1. 在 archive/<新剧>/ 放入网页版 HTML、关系图 PNG、文字版 .md，海报放进 cover/；
    2. 在 shows.json 里按已有格式加一行；
    3. 运行本脚本，首页统计数字、卡片、筛选按钮与 README 表格会自动同步；
    4. 提交推送。
"""

import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 筛选按钮里平台的固定顺序；shows.json 里出现的新平台会自动追加在后面。
PLATFORM_ORDER = ["HBO", "Netflix", "Disney+", "Apple TV+", "AMC", "Showtime"]

# 类型筛选按钮的固定顺序；shows.json 里出现的新类型会自动追加在后面。
GENRE_ORDER = ["剧情", "喜剧", "科幻", "犯罪", "惊悚", "奇幻", "动画", "古装", "冒险", "动作", "战争"]


def q(path: str) -> str:
    """把仓库相对路径转成 URL 编码形式（中文文件名在链接里需要编码）。"""
    return urllib.parse.quote(path)


def year_span(shows):
    starts, ends = [], []
    for s in shows:
        years = s["years"].replace("–", "-").replace("—", "-")
        parts = years.split("-", 1)
        starts.append(int(parts[0]))
        if len(parts) > 1 and parts[1].strip():
            ends.append(int(parts[1]))
    return f"{min(starts)}–{max(ends)}"


def span_years(shows):
    starts, ends = [], []
    for s in shows:
        years = s["years"].replace("–", "-").replace("—", "-")
        parts = years.split("-", 1)
        starts.append(int(parts[0]))
        if len(parts) > 1 and parts[1].strip():
            ends.append(int(parts[1]))
    return max(ends) - min(starts) + 1


def check_files(shows):
    """校验每部剧引用的文件是否都存在，返回缺失列表。"""
    missing = []
    for s in shows:
        for rel in [
            f"archive/{s['id']}/{s['html_file']}",
            f"archive/{s['id']}/{s['png_file']}",
            f"archive/{s['id']}/{s['text_file']}",
            f"cover/{s['id'].lower()}.jpg",
        ]:
            if not (ROOT / rel).exists():
                missing.append(rel)
        quiz = s.get("quiz")
        if quiz and not (ROOT / f"archive/{s['id']}/{quiz['file']}").exists():
            missing.append(f"archive/{s['id']}/{quiz['file']}")
    return missing


def render_cards(shows):
    cards = []
    for s in shows:
        cover = f"cover/{s['id'].lower()}.jpg"
        html_url = q(f"archive/{s['id']}/{s['html_file']}")
        search = f"{s['title_cn']} {s['title_en'].lower()}"
        quiz_tag = ""
        if s.get("quiz"):
            quiz_tag = f"      <span class=\"quiz-tag\">📝 {s['quiz']['label']}</span>\n"
        genres = s.get("genres", [])
        genres_attr = " ".join(genres)
        genres_html = ""
        if genres:
            tags = "".join(f"<span>{g}</span>" for g in genres)
            genres_html = f"      <p class=\"genres\">{tags}</p>\n"
        status = s.get("status", "已完结")
        status_cls = "ongoing" if status == "追更中" else "done"
        cards.append(f"""  <article class="card" data-title="{search}" data-platform="{s['platform']}" data-genres="{genres_attr}">
    <a class="poster" href="{html_url}">
      <img src="{cover}" alt="《{s['title_cn']}》海报" loading="lazy">
      <span class="platform">{s['platform']}</span>
      <span class="status {status_cls}">{status}</span>
    </a>
    <div class="card-body">
      <h2>{s['title_cn']} <span>{s['title_en']}</span></h2>
      <p class="meta"><b>{s['characters']}</b> 位人物 · {s['years']} · {s['seasons']} · <span class="rating">★ {s.get('douban', '—')}</span></p>
      <p class="desc">{s['desc']}</p>
{genres_html}{quiz_tag}      <div class="links">
        <a class="web" href="{html_url}">网页版</a>
        <a class="alt" href="archive/{s['id']}/{s['png_file']}">关系图长图</a>
        <a class="alt" href="archive/{s['id']}/{s['text_file']}">文字版</a>
      </div>
    </div>
  </article>""")
    return "\n\n".join(cards)


def render_chips(shows):
    platforms = list(PLATFORM_ORDER)
    for s in shows:
        if s["platform"] not in platforms:
            platforms.append(s["platform"])
    chips = ['    <button class="chip active" data-platform="all">全部</button>']
    chips += [
        f'    <button class="chip" data-platform="{p}">{p}</button>' for p in platforms
    ]
    return "\n".join(chips)


def render_genre_chips(shows):
    genres = []
    for s in shows:
        for g in s.get("genres", []):
            if g not in genres:
                genres.append(g)
    genres.sort(key=lambda g: GENRE_ORDER.index(g) if g in GENRE_ORDER else len(GENRE_ORDER))
    chips = ['    <button class="chip active" data-genre="all">全部类型</button>']
    chips += [f'    <button class="chip" data-genre="{g}">{g}</button>' for g in genres]
    return "\n".join(chips)


def render_hero_bg(shows):
    imgs = "".join(
        f'<img src="cover/{s["id"].lower()}.jpg" alt="" loading="lazy">'
        for s in shows
    )
    return f'<div class="hero-bg" aria-hidden="true">{imgs}</div>'


def render_index(shows):
    total_chars = sum(s["characters"] for s in shows)
    platforms = {s["platform"] for s in shows}
    ongoing = sum(1 for s in shows if s.get("status") == "追更中")
    latest = max(shows, key=lambda s: (s["added"], shows.index(s)))
    latest_line = f"持续更新中 · 最近新增《{latest['title_cn']}》（{latest['added']}）"
    tpl = INDEX_TEMPLATE
    tpl = tpl.replace("__STAT_SHOWS__", str(len(shows)))
    tpl = tpl.replace("__STAT_CHARS__", str(total_chars))
    tpl = tpl.replace("__STAT_PLATFORMS__", str(len(platforms)))
    tpl = tpl.replace("__STAT_ONGOING__", str(ongoing))
    tpl = tpl.replace("__STAT_SPAN__", year_span(shows))
    tpl = tpl.replace("__STAT_SPAN_YEARS__", str(span_years(shows)))
    tpl = tpl.replace("__CHIPS__", render_chips(shows))
    tpl = tpl.replace("__GENRE_CHIPS__", render_genre_chips(shows))
    tpl = tpl.replace("__HERO_BG__", render_hero_bg(shows))
    tpl = tpl.replace("__CARDS__", render_cards(shows))
    tpl = tpl.replace("__LATEST__", latest_line)
    return tpl


def render_table_rows(shows):
    rows = []
    for s in shows:
        cover = f"cover/{s['id'].lower()}.jpg"
        html_url = q(f"archive/{s['id']}/{s['html_file']}")
        links = (
            f"[网页版]({html_url}) · "
            f"[长图](archive/{s['id']}/{s['png_file']}) · "
            f"[文字版](archive/{s['id']}/{s['text_file']})"
        )
        if s.get("quiz"):
            quiz_url = q(f"archive/{s['id']}/{s['quiz']['file']}")
            links += f" · [选择题测验]({quiz_url})"
        rows.append(
            f"| <img src=\"{cover}\" width=\"54\" alt=\"{s['title_cn']}\"> "
            f"| **{s['title_cn']}** · {s['title_en']}<br>★ {s.get('douban', '—')} | {s['platform']} "
            f"| {s['years']} | {s['seasons']} · {s.get('status', '已完结')} | {s['characters']} | {links} |"
        )
    return "\n".join(rows)


def render_tree(shows):
    lines = []
    for i, s in enumerate(shows):
        branch = "└──" if i == len(shows) - 1 else "├──"
        extra = "、选择题测验" if s.get("quiz") else ""
        lines.append(
            f"    {branch} {s['id']}/ # {s['title_cn']}：网页版 HTML{extra}、关系图 PNG、文字版"
        )
    return "\n".join(lines)


def render_readme(shows):
    tpl = README_TEMPLATE
    tpl = tpl.replace("__SHOW_COUNT__", str(len(shows)))
    tpl = tpl.replace("__TOTAL_CHARS__", str(sum(s["characters"] for s in shows)))
    tpl = tpl.replace("__YEAR_SPAN__", year_span(shows))
    tpl = tpl.replace("__TABLE_ROWS__", render_table_rows(shows))
    tpl = tpl.replace(
        "__DESCS__",
        "\n".join(
            f"- **{s['title_cn']}**（{' / '.join(s.get('genres', []))}） — {s['desc']}"
            for s in shows
        ),
    )
    tpl = tpl.replace("__TREE__", render_tree(shows))
    return tpl


INDEX_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0b0e14">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<title>观影日志 · 人物关系图</title>
<style>
  :root {
    --bg: #0b0e14;
    --surface: #141926;
    --surface-2: #1a2133;
    --border: #262f45;
    --text: #eef1f8;
    --muted: #9aa6bf;
    --faint: #6b7794;
    --accent: #e8b64c;
    --accent-2: #5ea8ff;
    --max-w: 1440px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    line-height: 1.6;
  }

  /* ---------- Hero ---------- */
  .hero {
    position: relative;
    overflow: hidden;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    padding: 72px 20px 44px;
  }
  .hero-bg { position: absolute; inset: 0; display: flex; }
  .hero-bg img {
    flex: 1 1 0;
    min-width: 0;
    height: 100%;
    object-fit: cover;
    object-position: center 18%;
    filter: saturate(.9) brightness(.8);
  }
  .hero-bg::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(11, 14, 20, .9) 0%, rgba(11, 14, 20, .74) 50%, rgba(11, 14, 20, .95) 100%);
  }
  .hero-inner {
    position: relative;
    z-index: 1;
    max-width: var(--max-w);
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 48px;
  }
  .hero-copy { max-width: 660px; }
  .hero .kicker {
    display: inline-block;
    font-size: 12px;
    letter-spacing: 4px;
    color: var(--accent);
    border: 1px solid rgba(232, 182, 76, .45);
    border-radius: 999px;
    padding: 5px 14px;
    margin-bottom: 18px;
  }
  .hero h1 { font-size: 44px; letter-spacing: 3px; line-height: 1.25; text-shadow: 0 2px 28px rgba(0, 0, 0, .6); }
  .hero h1 span {
    background: linear-gradient(135deg, #f6d47c, #e8b64c 45%, #c98f2b);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }
  .logo { width: 64px; height: 64px; margin: 0 0 18px; }
  .logo svg { width: 100%; height: 100%; display: block; filter: drop-shadow(0 6px 16px rgba(0, 0, 0, .4)); }
  .hero p { color: #c9d1de; max-width: 640px; margin: 14px 0 0; font-size: 15px; text-shadow: 0 1px 12px rgba(0, 0, 0, .85); }
  .stats {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .stat {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0 20px;
    min-width: 0;
    box-shadow: none;
    text-align: center;
  }
  .stat b { display: block; font-size: 34px; color: var(--accent); line-height: 1.15; text-shadow: 0 2px 16px rgba(0, 0, 0, .6); }
  .stat span { font-size: 12px; color: var(--muted); }

  /* ---------- Toolbar ---------- */
  .toolbar {
    max-width: var(--max-w);
    margin: 0 auto;
    padding: 28px 20px 8px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    align-items: stretch;
  }
  .toolbar-top {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .search {
    flex: 0 1 380px;
    height: 44px;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0 18px;
    transition: border-color .15s ease, box-shadow .15s ease;
  }
  .search:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(232, 182, 76, .18); }
  .search input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text);
    font-size: 14px;
    height: 100%;
  }
  .search input::placeholder { color: var(--faint); }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .filter-rows { display: flex; flex-direction: column; gap: 10px; }
  .filter-label { color: var(--faint); font-size: 13px; flex-shrink: 0; width: 34px; }
  .chip {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--muted);
    border-radius: 999px;
    padding: 0 15px;
    height: 36px;
    display: inline-flex;
    align-items: center;
    font-size: 13px;
    cursor: pointer;
    transition: all .15s ease;
  }
  .chip:hover { border-color: var(--accent-2); color: var(--text); }
  .chip.active { background: var(--accent); border-color: var(--accent); color: #1a1405; font-weight: 600; }
  .count { color: var(--faint); font-size: 13px; }
  .cols-control { display: flex; align-items: center; gap: 6px; }
  .cols-control > span { color: var(--faint); font-size: 13px; }
  .cols-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--muted);
    border-radius: 8px;
    padding: 6px 11px;
    font-size: 13px;
    cursor: pointer;
    transition: all .15s ease;
  }
  .cols-btn:hover { border-color: var(--accent-2); color: var(--text); }
  .cols-btn.active { background: var(--accent); border-color: var(--accent); color: #1a1405; font-weight: 600; }

  /* ---------- Grid ---------- */
  .grid {
    max-width: var(--max-w);
    margin: 0 auto;
    padding: 20px 20px 30px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 24px;
  }
  .grid[data-cols="2"] { grid-template-columns: repeat(2, 1fr); }
  .grid[data-cols="3"] { grid-template-columns: repeat(3, 1fr); }
  .grid[data-cols="4"] { grid-template-columns: repeat(4, 1fr); }
  .grid[data-cols="5"] { grid-template-columns: repeat(5, 1fr); }
  @media (max-width: 1100px) {
    .grid[data-cols="4"], .grid[data-cols="5"] { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 900px) {
    .grid[data-cols="3"], .grid[data-cols="4"], .grid[data-cols="5"] { grid-template-columns: repeat(2, 1fr); }
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    text-decoration: none;
    color: inherit;
    transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
    animation: fadeUp .55s cubic-bezier(.22, .61, .36, 1) backwards;
  }
  .card:nth-child(2) { animation-delay: .04s; }
  .card:nth-child(3) { animation-delay: .08s; }
  .card:nth-child(4) { animation-delay: .12s; }
  .card:nth-child(5) { animation-delay: .16s; }
  .card:nth-child(6) { animation-delay: .20s; }
  .card:nth-child(7) { animation-delay: .24s; }
  .card:nth-child(8) { animation-delay: .28s; }
  .card:nth-child(9) { animation-delay: .32s; }
  .card:nth-child(10) { animation-delay: .36s; }
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(14px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .card:hover { transform: translateY(-5px); border-color: var(--accent); box-shadow: 0 16px 36px rgba(0, 0, 0, .45); }
  .poster { position: relative; color: var(--text); overflow: hidden; }
  .poster:visited { color: var(--text); }
  .poster img { width: 100%; aspect-ratio: 2 / 3; object-fit: cover; display: block; background: #0d1117; transition: transform .35s ease; }
  .card:hover .poster img { transform: scale(1.06); }
  .platform {
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(11, 14, 20, .82);
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, .18);
    border-radius: 999px;
    padding: 4px 11px;
    font-size: 12px;
    letter-spacing: .5px;
  }
  .status {
    position: absolute;
    top: 12px;
    right: 12px;
    border-radius: 999px;
    padding: 4px 11px;
    font-size: 12px;
    letter-spacing: .5px;
  }
  .status.done { background: rgba(11, 14, 20, .82); backdrop-filter: blur(4px); border: 1px solid rgba(255, 255, 255, .18); color: var(--muted); }
  .status.ongoing { background: var(--accent); border: 1px solid var(--accent); color: #1a1405; font-weight: 600; }
  .rating { color: var(--accent); font-weight: 600; }
  .genres { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .genres span {
    font-size: 12px;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 10px;
  }
  .card-body { padding: 18px 18px 16px; display: flex; flex-direction: column; flex: 1; }
  .card-body h2 { font-size: 20px; line-height: 1.35; }
  .card-body h2 span { color: var(--muted); font-size: 13px; font-weight: 400; margin-left: 6px; }
  .meta { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .meta b { color: var(--accent); font-weight: 600; }
  .desc { color: #c9d1de; font-size: 14px; line-height: 1.7; margin-top: 9px; flex: 1; }
  .links {
    display: flex;
    gap: 8px;
    margin-top: 14px;
    padding-top: 13px;
    border-top: 1px solid var(--border);
  }
  .links a {
    flex: 1;
    text-align: center;
    font-size: 13px;
    padding: 7px 4px;
    border-radius: 8px;
    text-decoration: none;
    transition: all .15s ease;
  }
  .links a.web { background: var(--accent); color: #1a1405; font-weight: 600; }
  .links a.web:hover { filter: brightness(1.1); }
  .links a.alt { background: var(--surface-2); color: var(--muted); border: 1px solid var(--border); }
  .links a.alt:hover { color: var(--text); border-color: var(--accent-2); }
  .quiz-tag {
    display: inline-block;
    margin-top: 10px;
    font-size: 12px;
    color: var(--accent-2);
    border: 1px solid var(--accent-2);
    border-radius: 999px;
    padding: 3px 10px;
    align-self: flex-start;
  }
  .empty {
    grid-column: 1 / -1;
    text-align: center;
    color: var(--faint);
    padding: 48px 0;
    font-size: 15px;
  }

  footer {
    max-width: var(--max-w);
    margin: 0 auto;
    padding: 8px 20px 56px;
    color: var(--faint);
    font-size: 13px;
    line-height: 1.9;
    text-align: center;
  }
  footer a { color: var(--accent-2); text-decoration: none; }
  footer a:hover { text-decoration: underline; }

  @media (max-width: 900px) {
    .hero-inner { flex-direction: column; align-items: flex-start; gap: 30px; }
    .stats { justify-content: flex-start; }
  }
  @media (max-width: 560px) {
    .hero { padding: 44px 16px 32px; }
    .hero h1 { font-size: 29px; letter-spacing: 2px; }
    .stat { padding: 0 12px; }
    .stat b { font-size: 28px; }
    .grid[data-cols="2"], .grid[data-cols="3"], .grid[data-cols="4"], .grid[data-cols="5"] { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<header class="hero">
__HERO_BG__
  <div class="hero-inner">
    <div class="hero-copy">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 64 64">
          <rect width="64" height="64" rx="14" fill="#0b0e14"/>
          <path d="M13 22 L17 11 H51 L47 22 Z" fill="#e8b64c"/>
          <line x1="25" y1="11" x2="21" y2="22" stroke="#0b0e14" stroke-width="2.5"/>
          <line x1="35" y1="11" x2="31" y2="22" stroke="#0b0e14" stroke-width="2.5"/>
          <line x1="45" y1="11" x2="41" y2="22" stroke="#0b0e14" stroke-width="2.5"/>
          <rect x="13" y="22" width="38" height="29" rx="4" fill="#1a2133" stroke="#e8b64c" stroke-width="2"/>
          <polygon points="27,30 27,43 39,36.5" fill="#e8b64c"/>
        </svg>
      </div>
      <span class="kicker">CINEMA LOG · 观影日志</span>
      <h1>看过的剧，<span>人物关系</span>都在这里</h1>
      <p>每部剧一份可交互的网页版人物关系图、一张关系图长图、一份文字版。点海报进入网页版，卡片下方可直达长图与文字版。</p>
    </div>
    <div class="stats">
      <div class="stat"><b>__STAT_SHOWS__</b><span>部剧集</span></div>
      <div class="stat"><b>__STAT_CHARS__</b><span>位人物</span></div>
      <div class="stat"><b>__STAT_PLATFORMS__</b><span>个平台</span></div>
      <div class="stat"><b>__STAT_ONGOING__</b><span>部追更中</span></div>
      <div class="stat"><b>__STAT_SPAN__</b><span>跨度 __STAT_SPAN_YEARS__ 年</span></div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-top">
    <label class="search">🔍 <input id="q" type="search" placeholder="搜剧名，如 曼达洛人 / Succession…" aria-label="搜索剧集"></label>
    <div class="cols-control" id="cols-control">
      <span>每行</span>
      <button class="cols-btn active" data-cols="auto">自动</button>
      <button class="cols-btn" data-cols="2">2</button>
      <button class="cols-btn" data-cols="3">3</button>
      <button class="cols-btn" data-cols="4">4</button>
      <button class="cols-btn" data-cols="5">5</button>
    </div>
    <span class="count" id="count"></span>
  </div>
  <div class="filter-rows">
    <div class="filters" id="filters">
      <span class="filter-label">平台</span>
__CHIPS__
    </div>
    <div class="filters" id="genre-filters">
      <span class="filter-label">类型</span>
__GENRE_CHIPS__
    </div>
  </div>
</div>

<main class="grid" id="grid">

__CARDS__

  <p class="empty" id="empty" hidden>没有找到匹配的剧，换个关键词试试。</p>
</main>

<footer>
  <p>每部剧的完整资料在 <a href="https://github.com/1990jtf/cinema-log">cinema-log</a> 仓库的 archive 文件夹中：网页版 HTML、关系图长图 PNG、文字版 .md，海报在 cover 文件夹中。</p>
  <p>__LATEST__</p>
  <p>豆瓣评分为第一季评分（豆瓣按季打分，无整部剧总分）。</p>
</footer>

<script>
  const cards = [...document.querySelectorAll('.card')];
  const countEl = document.getElementById('count');
  const emptyEl = document.getElementById('empty');
  const qInput = document.getElementById('q');
  let platform = 'all';
  let genre = 'all';

  function applyFilter() {
    const q = qInput.value.trim().toLowerCase();
    let shown = 0;
    for (const card of cards) {
      const okPlatform = platform === 'all' || card.dataset.platform === platform;
      const okGenre = genre === 'all' || (card.dataset.genres || '').split(' ').includes(genre);
      const okQuery = !q || card.dataset.title.includes(q);
      const show = okPlatform && okGenre && okQuery;
      card.style.display = show ? '' : 'none';
      if (show) shown++;
    }
    emptyEl.hidden = shown > 0;
    countEl.textContent = shown === cards.length ? '' : `共 ${shown} 部`;
  }

  document.getElementById('filters').addEventListener('click', (e) => {
    const btn = e.target.closest('.chip');
    if (!btn) return;
    document.querySelectorAll('#filters .chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    platform = btn.dataset.platform;
    applyFilter();
  });
  document.getElementById('genre-filters').addEventListener('click', (e) => {
    const btn = e.target.closest('.chip');
    if (!btn) return;
    document.querySelectorAll('#genre-filters .chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    genre = btn.dataset.genre;
    applyFilter();
  });
  qInput.addEventListener('input', applyFilter);
  applyFilter();

  const grid = document.getElementById('grid');
  const colsControl = document.getElementById('cols-control');
  function setCols(n) {
    if (n === 'auto') { delete grid.dataset.cols; } else { grid.dataset.cols = n; }
    colsControl.querySelectorAll('.cols-btn').forEach(b => b.classList.toggle('active', b.dataset.cols === n));
    try { localStorage.setItem('cinema-log-cols', n); } catch (e) {}
  }
  colsControl.addEventListener('click', (e) => {
    const btn = e.target.closest('.cols-btn');
    if (!btn) return;
    setCols(btn.dataset.cols);
  });
  try { const saved = localStorage.getItem('cinema-log-cols'); if (saved) setCols(saved); } catch (e) {}
</script>
</body>
</html>
"""

README_TEMPLATE = """# cinema-log · 观影日志

> 看过的电影电视剧，人物关系图都整理在这里。每部剧有一份**可交互的网页版人物关系图**、一张**关系图长图**和一份**文字版**。

🌐 **在线浏览：https://1990jtf.github.io/cinema-log/**

| 📺 剧集 | 👥 人物 | 🗓️ 跨度 |
| --- | --- | --- |
| **__SHOW_COUNT__ 部** | **__TOTAL_CHARS__ 位** | __YEAR_SPAN__ |

---

## 剧集一览

| 海报 | 剧名 | 平台 | 年份 | 季数 | 人物 | 资料 |
| --- | --- | --- | --- | --- | --- | --- |
__TABLE_ROWS__

> 豆瓣评分为第一季评分（豆瓣按季打分，无整部剧总分）。

---

## 一句话简介

__DESCS__

---

## 目录结构

```
cinema-log/
├── index.html          # 首页：海报卡片导航（GitHub Pages 入口），支持搜索、平台与类型筛选
├── favicon.svg         # 网站图标（场记板）
├── README.md           # 本文件
├── shows.json          # 各剧信息：唯一数据源，改这里再跑 tools/sync.py
├── tools/sync.py       # 同步脚本：由 shows.json 生成首页与 README
├── cover/              # 各剧官方海报
├── .nojekyll           # GitHub Pages 配置：不使用 Jekyll
└── archive/            # 各剧资料，每部剧一个文件夹
__TREE__
```

## 新增一部剧

1. 在 `archive/<新剧>/` 放入网页版 HTML、关系图 PNG、文字版 `.md`，海报放进 `cover/`；
2. 在 `shows.json` 里按已有格式加一行（剧名、平台、年份、季数、人物数、一句话简介、文件名、加入日期、豆瓣评分、类型、追更状态）；
3. 运行 `python3 tools/sync.py`，首页统计数字、卡片、筛选按钮与 README 表格会自动同步；
4. 检查脚本输出的提示，确认没有缺失文件；
5. 提交推送（或告诉 Muse 推送）。
"""


def main():
    check_only = "--check" in sys.argv
    with open(ROOT / "shows.json", encoding="utf-8") as f:
        shows = json.load(f)

    ids = [s["id"] for s in shows]
    if len(ids) != len(set(ids)):
        print("错误：shows.json 里有重复的 id")
        return 1

    missing = check_files(shows)
    if missing:
        print("缺失文件（共 %d 个）：" % len(missing))
        for m in missing:
            print("  -", m)
        if not check_only:
            print("已停止，未写文件。请先补齐文件再运行。")
        return 1

    if check_only:
        print(
            "校验通过：%d 部剧，%d 位人物，%d 个平台，%s"
            % (
                len(shows),
                sum(s["characters"] for s in shows),
                len({s["platform"] for s in shows}),
                year_span(shows),
            )
        )
        return 0

    (ROOT / "index.html").write_text(render_index(shows), encoding="utf-8")
    (ROOT / "README.md").write_text(render_readme(shows), encoding="utf-8")
    print(
        "已同步：%d 部剧，%d 位人物，%d 个平台，%s → index.html、README.md"
        % (
            len(shows),
            sum(s["characters"] for s in shows),
            len({s["platform"] for s in shows}),
            year_span(shows),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
