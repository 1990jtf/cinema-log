#!/usr/bin/env python3
"""Render the archived Markdown transcripts as standalone HTML reading pages."""

import argparse
import json
import re
from html import escape
from string import Template

from sync import ROOT, q, reader_filename, versioned_asset

WESTWORLD_ANCHORS = {
    "容易混淆的身份": "identity",
    "四季时间线": "timeline",
    "人物索引": "characters",
    "40 条核心关系": "core-relations",
    "资料来源": "sources",
}


def heading_text(inline):
    return "".join(
        child.content for child in inline.children if child.type in {"text", "code_inline"}
    )


def section_links(tokens, anchors):
    links = []
    used = set()
    for i, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag != "h2":
            continue
        label = heading_text(tokens[i + 1])
        slug = anchors.get(label) or re.sub(r"[^\w-]+", "-", label.lower()).strip("-") or "section"
        section_id = slug
        suffix = 2
        while section_id in used:
            section_id = f"{slug}-{suffix}"
            suffix += 1
        used.add(section_id)
        token.attrSet("id", section_id)
        links.append(f'      <a href="#{escape(section_id)}">{escape(label)}</a>')
    if not links:
        return ""
    return '\n    <nav class="text-toc" aria-label="文字版目录">\n' + "\n".join(links) + "\n    </nav>\n"


def render_reader(show, markdown, template, stylesheet):
    folder = ROOT / "archive" / show["id"]
    source = folder / show["text_file"]
    tokens = markdown.parse(source.read_text(encoding="utf-8-sig"))
    title = f"《{show['title_cn']}》人物关系图 · 文字版"
    if tokens and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        title = heading_text(tokens[1])
        tokens = tokens[3:]

    first_section = next(
        (i for i, token in enumerate(tokens) if token.type == "heading_open" and token.tag == "h2"), 0
    )
    intro, body = tokens[:first_section], tokens[first_section:]
    if intro and intro[-1].type == "hr":
        intro = intro[:-1]
    chart = q(show["html_file"])
    long_image = q(show["png_file"])
    resource_links = f"[交互网页版]({chart}) · [高清长图]({long_image})"
    if len(intro) >= 3 and intro[-2].content == resource_links:
        intro = intro[:-3]
    anchors = WESTWORLD_ANCHORS if show["id"] == "Westworld" else {}
    toc = section_links(body, anchors)
    for token in body:
        if token.type == "th_open":
            token.attrSet("scope", "col")

    name, bracket, rest = title.partition("》")
    heading = escape(title)
    if bracket and rest:
        heading = f"<span>{escape(name + bracket)}</span><span>{escape(rest)}</span>"

    intro_html = markdown.renderer.render(intro, markdown.options, {}).strip()
    if intro_html:
        intro_html = f'      <div class="text-intro">\n{intro_html}\n      </div>'
    if show["id"] == "Westworld":
        chart += "#relations"
    result = template.substitute(
        title=escape(title),
        title_cn=escape(show["title_cn"]),
        source_comment=escape(source.name.replace("--", "-")),
        stylesheet=escape(stylesheet),
        heading=heading,
        intro=intro_html,
        chart=escape(chart),
        long_image=escape(long_image),
        markdown=escape(q(show["text_file"])),
        toc=toc,
        body=markdown.renderer.render(body, markdown.options, {}).rstrip(),
    )
    return folder / reader_filename(show), result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check HTML against Markdown without writing files")
    args = parser.parse_args()
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        parser.exit(1, "请在虚拟环境中安装生成依赖：python3 -m pip install -r tools/requirements-readers.txt\n")

    markdown = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable("table")
    shows = json.loads((ROOT / "shows.json").read_text(encoding="utf-8"))
    template = Template((ROOT / "tools/reader.template.html").read_text(encoding="utf-8"))
    stylesheet = "../../" + versioned_asset("assets/reader.css")
    pages = [render_reader(show, markdown, template, stylesheet) for show in shows]

    if args.check:
        stale = [path for path, html in pages if not path.is_file() or path.read_text(encoding="utf-8") != html]
        if stale:
            for path in stale:
                print("待生成：", path.relative_to(ROOT))
            return 1
        print(f"已校验 {len(pages)} 个文字阅读页")
    else:
        for path, html in pages:
            path.write_text(html, encoding="utf-8")
        print(f"已生成 {len(pages)} 个文字阅读页")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
