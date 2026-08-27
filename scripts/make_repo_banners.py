"""Generate llmwiki-suite GitHub repo visuals (dark editor aesthetic).

Outputs into assets/:
  banner.png        1280x628  README top hero
  social-preview.png 1600x630 GitHub social preview
  demo-usage.png    1400x760  terminal demo card for README

Pure Pillow. Fonts: Microsoft YaHei (CJK) + Consolas (code).
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

FD = "C:/Windows/Fonts"
YAHEI = os.path.join(FD, "msyh.ttc")
YAHEI_BOLD = os.path.join(FD, "msyhbd.ttc")
CONSOLAS = os.path.join(FD, "consola.ttf")


def F(path, size):
    return ImageFont.truetype(path, size)


CG = {
    "bg": (16, 18, 27),
    "panel": (26, 29, 41),
    "panel2": (36, 39, 55),
    "line": (56, 62, 84),
    "tx": (232, 234, 243),
    "muted": (158, 164, 193),
    "violet": (168, 141, 252),
    "violet_d": (112, 84, 205),
    "teal": (96, 234, 212),
    "amber": (250, 204, 102),
    "green": (126, 217, 139),
    "red": (247, 118, 118),
}


def dots(d, x0, y0, x1, n, color, r=2):
    for i in range(n):
        dd = 1.6 * math.sin(i * 2.3)
        x = x0 + (x1 - x0) * i / max(1, n - 1)
        d.ellipse([x - r, y0 + dd - r, x + r, y0 + dd + r], fill=color)


def module(d, cx, cy, s, color):
    x0, y0 = cx - s, cy - s
    sw = max(2, int(s * 0.08))
    d.rounded_rectangle([x0, y0, x0 + s, y0 + s * 1.3], radius=int(s * 0.16),
                        outline=color, width=sw)
    for yy in (0.4, 0.58, 0.76):
        d.line([x0 + s * 0.16, y0 + s * yy, x0 + s * 0.72, y0 + s * yy],
               fill=color, width=max(1, int(s * 0.05)))
    nx, ny = cx + s * 0.18, cy + s * 0.62
    d.ellipse([nx - s * 0.14, ny - s * 0.14, nx + s * 0.14, ny + s * 0.14],
              fill=CG["panel"], outline=color, width=sw)


def term_frame(img, x, y, w, h, title=""):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=CG["panel"],
                        outline=CG.get("line", (56, 62, 84)), width=1)
    for i, c in enumerate([CG["red"], CG["amber"], CG["green"]]):
        d.ellipse([x + 18 + i * 26, y + 18, x + 18 + i * 26 + 13, y + 31], fill=c)
    if title:
        d.text((x + 96, y + 14), title, font=F(CONSOLAS, 16), fill=CG["muted"])
    d.line([x, y + 50, x + w, y + 50], fill=(56, 62, 84), width=1)
    return d


def grid(img, step):
    d = ImageDraw.Draw(img)
    w, h = img.size
    for gx in range(0, w, step):
        d.line([gx, 0, gx, h], fill=(20, 23, 34))
    for gy in range(0, h, step):
        d.line([0, gy, w, gy], fill=(20, 23, 34))


def img_draw(img):
    return ImageDraw.Draw(img)


def make_banner(W=1280, H=628):
    img = Image.new("RGB", (W, H), CG["bg"])
    grid(img, 64)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=CG["violet"])

    module(d, 64, 60, 26, CG["violet"])
    d.text((104, 44), "llmwiki-suite", font=F(YAHEI_BOLD, 26), fill=CG["tx"])
    d.text((104, 76), "LLM-compiled personal wiki toolkit",
           font=F(CONSOLAS, 14), fill=CG["muted"])

    d.text((72, 172), "把纯 Markdown 笔记", font=F(YAHEI_BOLD, 60), fill=CG["tx"])
    d.text((72, 246), "编译成会问答的知识库", font=F(YAHEI_BOLD, 60), fill=CG["tx"])
    d.rounded_rectangle([72, 336, 72 + 286, 336 + 62], radius=14, fill=CG["violet_d"])
    d.text((94, 346), "pip install ", font=F(CONSOLAS, 26), fill=CG["tx"])
    d.text((276, 346), "llmwiki-suite[serve]", font=F(CONSOLAS, 26), fill=CG["green"])
    d.text((72, 432), "BM25 + wikilink-graph 检索 · lint 巡检 · eval 评估", font=F(YAHEI, 22), fill=CG["muted"])
    d.text((72, 470), "微信 · 企业微信 · 飞书 · Telegram 四通道问答", font=F(YAHEI, 22), fill=CG["muted"])

    tx, ty, tw, th = W - 470, 150, 400, 360
    term_frame(img, tx, ty, tw, th, "llmwiki 5-step quickstart")
    d = ImageDraw.Draw(img)
    y = ty + 72
    cf = F(CONSOLAS, 17)
    lines = [
        ("$ llmwiki init", CG["violet"], 0),
        ("  ✓ 生成 llmwiki.toml 脚手架", CG["muted"], 0),
        ("$ llmwiki ingest", CG["violet"], 0),
        ("  ✓ 42 篇笔记补 frontmatter", CG["muted"], 0),
        ("$ llmwiki index", CG["violet"], 0),
        ("  ✓ BM25 + wikilink 图  kb-index.json", CG["muted"], 0),
        ("$ llmwiki query \"如何接微信问答\"", CG["violet"], 0),
        ("  → llmwiki serve 扫码即聊", CG["teal"], 1),
    ]
    for text, col, hl in lines:
        if hl:
            d.rounded_rectangle([tx + 10, y - 4, tx + tw - 10, y + 26], radius=6,
                                fill=CG["panel2"])
            y += 6
        d.text((tx + 22, y), text, font=cf, fill=col)
        y += 36
    dots(img_draw(img), tx + 22, ty + th - 24, tx + tw - 22, 4, CG["teal"])
    img.save(os.path.join(ASSETS, "banner.png"), optimize=True)


def make_og(W=1600, H=630):
    img = Image.new("RGB", (W, H), CG["bg"])
    grid(img, 80)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=CG["violet"])

    module(d, 72, 92, 30, CG["violet"])
    d.text((128, 52), "llmwiki-suite", font=F(YAHEI_BOLD, 38), fill=CG["tx"])
    d.text((128, 104), "LLM-compiled personal wiki toolkit", font=F(CONSOLAS, 18), fill=CG["muted"])

    d.text((72, 230), "把一堆 Markdown 笔记", font=F(YAHEI, 46), fill=CG["tx"])
    d.text((72, 292), "变成能搜索、能问答、能自维护的个人知识库。", font=F(YAHEI, 46), fill=CG["tx"])
    d.rounded_rectangle([72, 392, 72 + 360, 392 + 56], radius=28, fill=CG["violet_d"])
    d.text((92, 400), "pip install llmwiki-suite", font=F(CONSOLAS, 22), fill=CG["tx"])
    d.text((382, 400), "MIT", font=F(CONSOLAS, 20), fill=CG["muted"])

    caps = [("Ingest", "补 frontmatter · 规范化 wikilink", CG["violet"]),
            ("Index", "BM25 + wikilink 图检索", CG["teal"]),
            ("Lint", "断链 / 词表巡检 · 自愈", CG["amber"]),
            ("Chat", "微信 · 企微 · 飞书 · Telegram", CG["green"])]
    yy = 210
    for name, desc, col in caps:
        round_rect_y = yy
        d.rounded_rectangle([W - 560, yy, W - 60, yy + 88], radius=16,
                            fill=CG["panel"], outline=CG["line"], width=1)
        d.rounded_rectangle([W - 540, yy + 18, W - 540 + 44, yy + 62], radius=8, fill=col)
        d.text((W - 472, yy + 16), name, font=F(YAHEI_BOLD, 26), fill=col)
        d.text((W - 472, yy + 52), desc, font=F(CONSOLAS, 16), fill=CG["muted"])
        yy += 104
    img.save(os.path.join(ASSETS, "social-preview.png"), optimize=True)


def make_term_demo(W=1360, H=800):
    img = Image.new("RGB", (W, H), CG["bg"])
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([28, 28, W - 28, H - 28], radius=20, fill=(22, 25, 36),
                        outline=CG["line"], width=2)
    d.text((70, 54), "demo — llmwiki 五步接入已有笔记库", font=F(CONSOLAS, 17), fill=CG["muted"])
    d.line([28, 92, W - 28, 92], fill=CG["line"], width=1)

    x0, y = 64, 150
    step_y = 54
    cf = F(CONSOLAS, 21)
    of = F(CONSOLAS, 20)
    lines = [
        ("$ llmwiki init", CG["violet"], True),
        ("✓ 生成 llmwiki.toml + .gitignore / pre-commit / CI 脚手架", CG["muted"], False),
        ("$ llmwiki ingest", CG["violet"], True),
        ("扫描 42 篇笔记 → 补 frontmatter → 规范化 wikilink ✓", CG["muted"], False),
        ("$ llmwiki index", CG["violet"], True),
        ("BM25 + wikilink 图 → kb-index.json ✓", CG["muted"], False),
        ("$ llmwiki lint", CG["violet"], True),
        ("断链 3 / 孤儿 1 / 词表越界 0（--sync-vocab 自愈）", CG["muted"], False),
        ("$ llmwiki query \"怎么接到微信问答\"", CG["violet"], True),
        ("→ llmwiki serve 起桥接服务，手机扫码即可在微信里提问", CG["teal"], False),
    ]
    d = ImageDraw.Draw(img)
    for text, col, cmd in lines:
        if cmd:
            d.text((x0, y), text, font=F(CONSOLAS, 21), fill=col)
        else:
            fnt = F(CONSOLAS, 20)
            d.text((x0, y), text, font=fnt, fill=col)
        y += step_y
    img.save(os.path.join(ASSETS, "demo-term.png"), optimize=True)


if __name__ == "__main__":
    make_banner()
    make_og()
    make_term_demo()
    print("OK ->", ASSETS)

def img_draw(img):
    return ImageDraw.Draw(img)
