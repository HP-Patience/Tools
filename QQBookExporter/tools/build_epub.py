#!/usr/bin/env python3
"""把导出的 Markdown 章节打包成 EPUB，并顺带生成一个用于打印 PDF 的合并 HTML。

用法：
    python tools/build_epub.py <导出目录> [--title 书名] [--author 作者]

只依赖标准库。
"""
import html
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone

CSS = """
body { font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", serif;
       line-height: 1.8; margin: 0 1.2em; color: #222; }
h1, h2, h3, h4 { font-family: "Heiti SC", "Noto Sans CJK SC", sans-serif;
       line-height: 1.4; margin: 1.6em 0 0.8em; page-break-after: avoid; }
h1 { font-size: 1.8em; }
h2 { font-size: 1.5em; }
h3 { font-size: 1.25em; }
h4 { font-size: 1.1em; }
p { margin: 0 0 0.9em; text-align: justify; text-indent: 2em; }
blockquote { margin: 1em 2em; padding-left: 1em; border-left: 3px solid #ccc;
       color: #555; font-style: italic; }
blockquote p { text-indent: 0; }
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
p > em:only-child { display: block; text-align: center; text-indent: 0;
       color: #666; font-size: 0.92em; }
""".strip()


def inline(text):
    """行内标记 -> XHTML 片段（先转义再替换，避免注入）。"""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_body(markdown):
    blocks = [b.strip("\n") for b in re.split(r"\n\s*\n", markdown.strip()) if b.strip()]
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        # 纯图片块
        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", lines[0])
        if img and len(lines) == 1:
            alt, src = img.group(1), img.group(2)
            out.append(f'<div class="img"><img src="{html.escape(src)}" alt="{html.escape(alt)}"/></div>')
            continue

        # 标题
        heading = re.fullmatch(r"(#{1,6})\s+(.*)", lines[0])
        if heading and len(lines) == 1:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            continue

        # 引文
        if all(ln.startswith("> ") for ln in lines):
            inner = " ".join(ln[2:] for ln in lines)
            out.append(f"<blockquote><p>{inline(inner)}</p></blockquote>")
            continue

        out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "\n".join(out)


def read_chapters(book_dir):
    files = sorted(f for f in os.listdir(book_dir) if re.match(r"^\d{3}-.*\.md$", f))
    chapters = []
    for name in files:
        seq = name[:3]
        title = name[4:-3]
        with open(os.path.join(book_dir, name), encoding="utf-8") as fh:
            chapters.append({"seq": seq, "title": title, "markdown": fh.read()})
    return chapters


CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CHAPTER_RE = re.compile(r"^第([0-9]+|[零〇一二三四五六七八九十百]+)章[\s\u3000]*(.*)$")
SECTION_RE = re.compile(r"^第([0-9]+|[零〇一二三四五六七八九十百]+)节[\s\u3000]*(.*)$")


def cn_to_int(text):
    """中文数字转整数，支持 一~九百九十九 的常见写法。"""
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if "百" in text:
        head, _, tail = text.partition("百")
        hundreds = CN_DIGITS.get(head, 1) if head else 1
        rest = cn_to_int(tail) if tail else 0
        return hundreds * 100 + (rest or 0)
    if "十" in text:
        head, _, tail = text.partition("十")
        tens = CN_DIGITS.get(head, 1) if head else 1
        ones = CN_DIGITS.get(tail, 0) if tail else 0
        return tens * 10 + ones
    total = 0
    for ch in text:
        if ch not in CN_DIGITS:
            return None
        total = total * 10 + CN_DIGITS[ch]
    return total


def rewrite_headings(markdown, chapter_label=None, section_label=None):
    """把正文里以「第X章 / 第X节」开头的标题替换成 1 / 1.1 形式。"""
    out = []
    for line in markdown.split("\n"):
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            marks, text = heading.group(1), heading.group(2)
            m = CHAPTER_RE.match(text.strip())
            if m and chapter_label:
                line = f"{marks} {chapter_label} {m.group(2).strip()}"
            else:
                m = SECTION_RE.match(text.strip())
                if m and section_label:
                    line = f"{marks} {section_label} {m.group(2).strip()}"
        out.append(line)
    return "\n".join(out)


def collapse_duplicates(chapters):
    """书里的「篇扉页」会同时占两个目录项、正文完全相同，这里合并成一篇。"""
    docs = []
    for chapter in chapters:
        key = re.sub(r"\s+", "", chapter["markdown"])
        if docs and docs[-1]["key"] == key:
            docs[-1]["titles"].append(chapter["title"])
            continue
        docs.append({
            "key": key,
            "markdown": chapter["markdown"],
            "titles": [chapter["title"]],
        })
    return docs


def number_documents(docs, enabled=True):
    """给章 / 节加 1、1.1 形式的编号；篇、封面、后记等保持原样。"""
    chapter_no = 0
    for doc in docs:
        raw_titles = [t.strip() for t in doc["titles"]]
        if any(SECTION_RE.match(t) for t in raw_titles):
            doc["kind"] = "section"
        elif any(CHAPTER_RE.match(t) for t in raw_titles):
            doc["kind"] = "chapter"
        else:
            doc["kind"] = "other"

        chapter_label = None
        section_label = None
        titles = []

        for title in raw_titles:
            if enabled:
                m = CHAPTER_RE.match(title)
                if m and cn_to_int(m.group(1)) is not None:
                    chapter_no = cn_to_int(m.group(1))
                    chapter_label = str(chapter_no)
                    titles.append(f"{chapter_label} {m.group(2).strip()}")
                    continue

                m = SECTION_RE.match(title)
                if m and cn_to_int(m.group(1)) is not None and chapter_no:
                    section_label = f"{chapter_no}.{cn_to_int(m.group(1))}"
                    titles.append(f"{section_label} {m.group(2).strip()}")
                    continue

            titles.append(title)

        doc["titles"] = titles
        if enabled and (chapter_label or section_label):
            doc["markdown"] = rewrite_headings(
                doc["markdown"], chapter_label=chapter_label, section_label=section_label
            )
    return docs


def xhtml_doc(title, body):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
        'lang="zh-CN" xml:lang="zh-CN">\n'
        f"<head><meta charset=\"utf-8\"/><title>{html.escape(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def build_epub(book_dir, out_path, title, author, number=True):
    chapters = read_chapters(book_dir)
    if not chapters:
        raise SystemExit(f"没找到章节文件：{book_dir}")
    docs = number_documents(collapse_duplicates(chapters), enabled=number)

    book_id = f"urn:uuid:{uuid.uuid4()}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
    ]
    spine = []
    nav_items = []
    ncx_items = []

    # 图片清单
    images_dir = os.path.join(book_dir, "images")
    image_files = []
    if os.path.isdir(images_dir):
        for root, _, files in os.walk(images_dir):
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, book_dir).replace(os.sep, "/")
                image_files.append(rel)
                media = "image/png" if rel.lower().endswith(".png") else "image/jpeg"
                manifest.append(
                    f'<item id="img{len(image_files)}" href="{html.escape(rel)}" media-type="{media}"/>'
                )

    play = 0
    for index, doc_item in enumerate(docs, start=1):
        href = f"ch{index:03d}.xhtml"
        body = md_to_body(doc_item["markdown"])
        doc = xhtml_doc(doc_item["titles"][0], body)
        manifest.append(
            f'<item id="ch{index:03d}" href="{href}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="ch{index:03d}"/>')
        # 合并掉的重复章节仍保留自己的目录项，指向同一页
        for nav_title in doc_item["titles"]:
            play += 1
            nav_items.append(f'<li><a href="{href}">{html.escape(nav_title)}</a></li>')
            ncx_items.append(
                f'<navPoint id="np{play}" playOrder="{play}">'
                f'<navLabel><text>{html.escape(nav_title)}</text></navLabel>'
                f'<content src="{href}"/></navPoint>'
            )

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>zh-CN</dc:language>
    <dc:date>{now}</dc:date>
    <meta property="dcterms:modified">{now}</meta>
  </metadata>
  <manifest>
    {chr(10).join("    " + m for m in manifest)}
  </manifest>
  <spine toc="ncx">
    {chr(10).join("    " + s for s in spine)}
  </spine>
</package>
"""

    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN">
<head><meta charset="utf-8"/><title>目录</title></head>
<body>
  <nav epub:type="toc" id="toc"><h1>目录</h1><ol>
    {chr(10).join("    " + n for n in nav_items)}
  </ol></nav>
</body>
</html>
"""

    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{book_id}"/></head>
  <docTitle><text>{html.escape(title)}</text></docTitle>
  <navMap>
    {chr(10).join("    " + n for n in ncx_items)}
  </navMap>
</ncx>
"""

    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

    with zipfile.ZipFile(out_path, "w") as zf:
        # mimetype 必须是第一个条目且不压缩
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        for index, doc_item in enumerate(docs, start=1):
            zf.writestr(
                f"OEBPS/ch{index:03d}.xhtml",
                xhtml_doc(doc_item["titles"][0], md_to_body(doc_item["markdown"])),
                compress_type=zipfile.ZIP_DEFLATED,
            )
        for rel in image_files:
            zf.write(os.path.join(book_dir, rel), f"OEBPS/{rel}", compress_type=zipfile.ZIP_DEFLATED)

    return {"chapters": len(docs), "entries": len(chapters), "images": len(image_files), "path": out_path}


def build_print_html(book_dir, out_path, title, author, number=True):
    docs = number_documents(collapse_duplicates(read_chapters(book_dir)), enabled=number)
    # 章扉页独占一页，同章的小节连续排版，避免大量半空页
    groups = []
    previous_kind = None
    for doc_item in docs:
        body = md_to_body(doc_item["markdown"])
        if doc_item["kind"] == "section" and previous_kind == "section":
            groups[-1].append(body)
        else:
            groups.append([body])
        previous_kind = doc_item["kind"]

    parts = [f'<section class="chapter">{"".join(group)}</section>' for group in groups]

    doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 20mm 18mm; }}
body {{ font-family: "Songti SC", "SimSun", serif; font-size: 11.5pt; line-height: 1.75; color: #1a1a1a; }}
h1, h2, h3, h4 {{ font-family: "Microsoft YaHei", "SimHei", sans-serif; line-height: 1.4;
  margin: 1.4em 0 0.7em; break-after: avoid; }}
h1 {{ font-size: 22pt; }}
h2 {{ font-size: 17pt; }}
h3 {{ font-size: 14pt; }}
h4 {{ font-size: 12pt; }}
p {{ margin: 0 0 0.75em; text-align: justify; text-indent: 2em; }}
blockquote {{ margin: 0.9em 2.5em; padding-left: 1em; border-left: 3px solid #ccc; color: #555; }}
blockquote p {{ text-indent: 0; }}
img {{ max-width: 100%; max-height: 235mm; height: auto; display: block; margin: 0.9em auto; break-inside: avoid; }}
p > em:only-child {{ display: block; text-align: center; text-indent: 0; color: #666; font-size: 0.9em; }}
section.chapter {{ break-before: page; }}
section.chapter:first-of-type {{ break-before: auto; }}
section.chapter:first-of-type:has(.img) {{
  display: flex; align-items: center; justify-content: center; height: 250mm;
}}
section.chapter:first-of-type:has(.img) .img {{ margin: 0; }}
</style></head>
<body>
{chr(10).join(parts)}
</body></html>
"""
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return out_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    book_dir = sys.argv[1]
    title = "未知书名"
    author = "未知作者"
    number = True
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--title" and i + 1 < len(args):
            title = args[i + 1]
        if arg == "--author" and i + 1 < len(args):
            author = args[i + 1]
        if arg == "--no-number":
            number = False

    base = os.path.join(book_dir, title)
    epub_path = base + ".epub"
    html_path = os.path.join(book_dir, "_print.html")

    info = build_epub(book_dir, epub_path, title, author, number=number)
    build_print_html(book_dir, html_path, title, author, number=number)
    print(f"EPUB: {epub_path}（{info['entries']} 条目 → {info['chapters']} 篇，{info['images']} 张图，编号：{'开' if number else '关'}）")
    print(f"打印用 HTML: {html_path}")


if __name__ == "__main__":
    main()
