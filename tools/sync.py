#!/usr/bin/env python3
"""cinema-log 同步脚本：以 shows.json 为唯一数据源，自动生成首页与 README。

用法：
    python3 tools/sync.py            # 重新生成 index.html 与 README.md
    python3 tools/sync.py --check    # 只校验，不写文件

新增一部剧的流程：
    1. 在 archive/<新剧>/ 放入网页版 HTML、关系图 PNG、文字版 .md，海报放进 cover/；
    2. 在 shows.json 里按已有格式加一行；
    3. 运行本脚本，首页统计数字、剧集卡片、筛选选项和 README 表格会自动同步；
    4. 提交推送。
"""

import json
import sys
import urllib.parse
from datetime import datetime
from hashlib import sha256
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 平台筛选的固定顺序，新平台会自动追加在后面。
PLATFORM_ORDER = ["HBO", "Netflix", "Disney+", "Apple TV+", "AMC", "Showtime"]

# 类型筛选的固定顺序，新类型会自动追加在后面。
GENRE_ORDER = ["剧情", "喜剧", "科幻", "犯罪", "惊悚", "奇幻", "动画", "古装", "冒险", "动作", "战争"]

SPOTLIGHT_IDS = ("Succession", "Mandalorian", "Pantheon")


def q(path: str) -> str:
    """把仓库相对路径转成 URL 编码形式（中文文件名在链接里需要编码）。"""
    return urllib.parse.quote(path)


def year_span(shows):
    starts, ends = [], []
    for show in shows:
        years = show["years"].replace("–", "-").replace("—", "-")
        start, separator, end = years.partition("-")
        starts.append(int(start))
        ends.append(int(end) if end.strip() else datetime.now().year if separator else int(start))
    return f"{min(starts)}–{max(ends)}"


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


def archive_url(show, filename):
    return q(f"archive/{show['id']}/{filename}")


def render_cards(shows):
    cards = []
    for show in shows:
        title = escape(show["title_cn"])
        cover = q(f"cover/{show['id'].lower()}.jpg")
        poster = f'<img src="{cover}" width="500" height="750" alt="" loading="lazy" decoding="async" fetchpriority="low">'
        chart = archive_url(show, show["html_file"])
        long_image = archive_url(show, show["png_file"])
        text = archive_url(show, show["text_file"])
        status = escape(show.get("status", "已完结"))
        genres = show.get("genres", [])
        tags = " · ".join(escape(genre) for genre in genres)
        genre_data = escape(json.dumps(genres, ensure_ascii=False))
        english = escape(show["title_en"])
        platform = escape(show["platform"])
        rating = show.get("douban")
        rating_badge = (
            f'<span class="rating" aria-label="第一季豆瓣评分 {rating}"><span aria-hidden="true">★</span> {rating}</span>'
            if rating is not None else ""
        )
        quiz = show.get("quiz")
        quiz_link = ""
        if quiz:
            quiz_url = archive_url(show, quiz["file"])
            quiz_link = f'\n              <a class="quiz-link" href="{quiz_url}">{escape(quiz["label"])} <span aria-hidden="true">↗</span></a>'
        cards.append(f"""        <article class="card" data-title="{title} {english}" data-platform="{platform}" data-genres="{genre_data}" data-status="{status}">
          <a class="poster" href="{chart}" aria-label="查看《{title}》人物关系图">
            <template>{poster}</template>
            <noscript>{poster}</noscript>
            <span class="poster-platform">{platform}</span>
            {rating_badge}
          </a>
          <div class="card-body">
            <h3>{title}</h3>
            <p class="english-title" lang="en">{english}</p>
            <p class="card-meta"><span>{escape(show['years'])}</span><span>{escape(show['seasons'])}</span><span class="status">{status}</span></p>
            <p class="description">{escape(show['desc'])}</p>
            <p class="card-details"><span>{tags}</span><span>{show['characters']} 位人物</span></p>
            <div class="card-links" role="group" aria-label="《{title}》资料">
              <a class="chart-link" href="{chart}">关系图 <span aria-hidden="true">↗</span></a>
              <a href="{long_image}">长图</a>
              <a href="{text}">文字版</a>{quiz_link}
            </div>
          </div>
        </article>""")
    return "\n\n".join(cards)


def render_options(values, preferred_order=()):
    values = list(dict.fromkeys(values))
    ordered = [value for value in preferred_order if value in values]
    ordered.extend(value for value in values if value not in ordered)
    return "\n".join(f'          <option value="{escape(value)}">{escape(value)}</option>' for value in ordered)


def versioned_asset(path):
    version = sha256((ROOT / path).read_bytes()).hexdigest()[:12]
    return f"{path}?v={version}"


def spotlight_media(show):
    media_dir = ROOT / "archive" / show["id"] / "assets"
    backdrop = media_dir / "backdrop.jpg"
    if not backdrop.is_file():
        backdrop = ROOT / "cover" / f"{show['id'].lower()}.jpg"
    return backdrop, media_dir / "backdrop-mobile.webp", media_dir / "spotlight.webp"


def render_spotlight_panel(show, panel_id, is_latest, backdrop, mobile_backdrop, thumb_url):
    mobile_source = ""
    if mobile_backdrop.is_file():
        mobile_url = q(mobile_backdrop.relative_to(ROOT).as_posix())
        mobile_source = f'<source media="(max-width: 700px)" srcset="{mobile_url}">\n              '
    backdrop_url = q(backdrop.relative_to(ROOT).as_posix())
    priority = ' fetchpriority="high"' if is_latest else ''
    preview_style = '' if is_latest else f' style="--art-preview: url({thumb_url})"'
    label = "最近收录" if is_latest else "焦点剧集"
    chart = archive_url(show, show["html_file"])
    rating = show.get("douban")
    rating_text = (
        f'<span class="hero-rating" role="img" aria-label="第一季豆瓣评分 {rating}"><span aria-hidden="true">★</span> {rating}</span>'
        if rating is not None else ""
    )
    return f"""        <div class="hero-panel" id="{panel_id}">
          <picture class="hero-media"{preview_style}>
            {mobile_source}<img class="hero-image" src="{backdrop_url}" alt=""{priority}>
          </picture>
          <div class="hero-content wrap">
            <div class="hero-copy">
              <p class="hero-kicker">{label}</p>
              <h2>{escape(show['title_cn'])}</h2>
              <p class="hero-en" lang="en">{escape(show['title_en'])}</p>
              <div class="hero-meta">
                <span class="hero-platform">{escape(show['platform'])}</span>
                <span>{escape(show['years'])}</span>
                <span>{escape(show['seasons'])}</span>
                {rating_text}
              </div>
              <p class="hero-description">{escape(show.get('spotlight_desc', show['desc']))}</p>
              <div class="hero-actions">
                <a class="hero-button" href="{chart}">查看人物关系图 <span aria-hidden="true">↗</span></a>
                <a class="hero-button secondary" href="#catalog">浏览剧集 <span aria-hidden="true">↓</span></a>
              </div>
            </div>
          </div>
        </div>"""


def render_spotlight(shows):
    latest = max(reversed(shows), key=lambda show: show["added"])
    by_id = {show["id"]: show for show in shows}
    selection = [latest] + [by_id[show_id] for show_id in SPOTLIGHT_IDS if show_id in by_id and show_id != latest["id"]]
    panels, buttons = [], []
    for index, show in enumerate(selection):
        panel_id = f"spotlight-{index}"
        active = index == 0
        backdrop, mobile_backdrop, thumbnail = spotlight_media(show)
        if not thumbnail.is_file():
            thumbnail = ROOT / "cover" / f"{show['id'].lower()}.jpg"
        thumb_url = q(thumbnail.relative_to(ROOT).as_posix())
        panel = render_spotlight_panel(show, panel_id, active, backdrop, mobile_backdrop, thumb_url)
        if not active:
            panel = f'        <template data-panel="{panel_id}">\n{panel}\n        </template>'
        panels.append(panel)
        buttons.append(f"""            <button type="button" data-spotlight="{panel_id}" aria-pressed="{str(active).lower()}">
              <img src="{thumb_url}" width="168" height="94" alt="" loading="lazy" decoding="async" fetchpriority="low">
              <span>{escape(show['title_cn'])}</span>
            </button>""")
    return "\n".join(panels), "\n".join(buttons) if len(buttons) > 1 else ""


def render_index(shows):
    spotlight_panels, spotlight_buttons = render_spotlight(shows)
    replacements = {
        "SITE_CSS": versioned_asset("assets/index.css"),
        "SITE_SCRIPT": versioned_asset("assets/index.js"),
        "STAT_SHOWS": str(len(shows)),
        "STAT_CHARS": str(sum(show["characters"] for show in shows)),
        "STAT_SPAN": year_span(shows),
        "PLATFORM_OPTIONS": render_options((show["platform"] for show in shows), PLATFORM_ORDER),
        "GENRE_OPTIONS": render_options((genre for show in shows for genre in show.get("genres", [])), GENRE_ORDER),
        "STATUS_OPTIONS": render_options((show.get("status", "已完结") for show in shows), ("已完结", "追更中")),
        "SPOTLIGHT_PANELS": spotlight_panels,
        "SPOTLIGHT_BUTTONS": spotlight_buttons,
        "CARDS": render_cards(shows),
    }
    template = (ROOT / "tools" / "index.template.html").read_text(encoding="utf-8")
    for name, value in replacements.items():
        template = template.replace(f"__{name}__", value)
    return template


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
├── index.html          # 首页：剧集目录（GitHub Pages 入口），支持搜索与筛选
├── favicon.svg         # 网站图标（场记板）
├── README.md           # 本文件
├── shows.json          # 各剧信息：唯一数据源，改这里再跑 tools/sync.py
├── tools/              # 首页模板与同步脚本
├── assets/             # 首页与存档页的公共样式、脚本
├── cover/              # 各剧官方海报
├── .nojekyll           # GitHub Pages 配置：不使用 Jekyll
└── archive/            # 各剧资料，每部剧一个文件夹
__TREE__
```

## 新增一部剧

1. 在 `archive/<新剧>/` 放入网页版 HTML、关系图 PNG、文字版 `.md`，海报放进 `cover/`；
2. 在 `shows.json` 里按已有格式加一行（剧名、平台、年份、季数、人物数、一句话简介、文件名、加入日期、豆瓣评分、类型、追更状态）；
3. 运行 `python3 tools/sync.py`，首页统计数字、剧集卡片、筛选选项和 README 表格会自动同步；
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
