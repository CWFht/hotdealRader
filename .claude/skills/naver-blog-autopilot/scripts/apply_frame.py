#!/usr/bin/env python3
"""본문 이미지에 블로그 프레임(상·하단 그라데이션 띠)과 오른쪽 위 도장을 입힌다.

사용: python apply_frame.py <images 폴더 또는 파일...> --frame profiles/<블로그>.frame.json
                           [--include-thumbnail]

- 띠는 이미지 위·아래 가장자리를 덮는다(크기는 그대로).
- 이미 프레임을 입힌 파일은 건너뛴다(파일 안에 표시를 남긴다). 원본은 <폴더>/_raw/에 보관한다.
- 도장: 프레임 설정의 stamp.image 파일(스킬 폴더 기준 경로)이 있으면 그 원본을 쓰고,
  없으면 설정의 글자·색으로 그린다.
- 썸네일(skip_prefixes, 기본 00_)은 --include-thumbnail을 줘야 입힌다.
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

MARK = "blog-frame-applied"
EXTS = {".png", ".jpg", ".jpeg", ".webp"}
BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def rgb(hexstr):
    h = hexstr.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient(w, h, c1, c2):
    a, b = rgb(c1), rgb(c2)
    row = Image.new("RGB", (w, 1))
    row.putdata([tuple(round(a[k] + (b[k] - a[k]) * x / max(w - 1, 1)) for k in range(3)) for x in range(w)])
    return row.resize((w, h))


def font(size):
    for f in BOLD_FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def draw_stamp(size, cfg):
    """size×size 투명 배경 도장. 4배로 그려서 줄여 가장자리를 매끈하게 한다."""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    color = rgb(cfg.get("color", "#d9261c")) + (255,)
    lw = max(2, round(s * 0.075))
    d.rounded_rectangle([lw // 2, lw // 2, s - lw // 2 - 1, s - lw // 2 - 1], radius=round(s * 0.16), outline=color, width=lw)
    lines = cfg.get("text", [])
    if lines:
        fs = round(s * 0.74 / len(lines))
        f = font(fs)
        boxes = [d.textbbox((0, 0), t, font=f) for t in lines]
        widest = max(b[2] - b[0] for b in boxes)
        limit = s - lw * 4
        if widest > limit:
            f = font(max(8, round(fs * limit / widest)))
            boxes = [d.textbbox((0, 0), t, font=f) for t in lines]
        line_h = max(b[3] - b[1] for b in boxes)
        gap = round(line_h * 0.14)
        y = (s - (line_h * len(lines) + gap * (len(lines) - 1))) / 2
        for t, b in zip(lines, boxes):
            d.text(((s - (b[2] - b[0])) / 2 - b[0], y - b[1]), t, font=f, fill=color)
            y += line_h + gap
    return im.resize((size, size), Image.LANCZOS)


def stamp_image(size, cfg, skill_dir):
    src = cfg.get("image")
    if src and (skill_dir / src).exists():
        im = Image.open(skill_dir / src).convert("RGBA")
        w = round(im.width * size / im.height)
        return im.resize((w, size), Image.LANCZOS), True
    return draw_stamp(size, cfg), False


def is_framed(im):
    info = im.info or {}
    c = info.get("comment", b"")
    c = c.decode("utf-8", "ignore") if isinstance(c, bytes) else str(c)
    return info.get("frame") == MARK or MARK in c


def apply(path, cfg, skill_dir):
    im = Image.open(path)
    if is_framed(im):
        return "건너뜀(이미 적용)"
    raw_dir = path.parent / "_raw"
    raw_dir.mkdir(exist_ok=True)
    shutil.copy2(path, raw_dir / path.name)
    im = im.convert("RGB")
    w, h = im.size
    th = max(4, round(h * cfg["top"]["height_ratio"]))
    bh = max(4, round(h * cfg["bottom"]["height_ratio"]))
    im.paste(gradient(w, th, cfg["top"]["from"], cfg["top"]["to"]), (0, 0))
    im.paste(gradient(w, bh, cfg["bottom"]["from"], cfg["bottom"]["to"]), (0, h - bh))
    used_original = None
    st = cfg.get("stamp")
    if st:
        size = max(8, round(th * st.get("height_ratio_of_top", 0.76)))
        simg, used_original = stamp_image(size, st, skill_dir)
        x = w - round(w * st.get("right_margin_ratio", 0.016)) - simg.width
        im.paste(simg, (x, (th - simg.height) // 2), simg)
    if path.suffix.lower() == ".png":
        meta = PngInfo()
        meta.add_text("frame", MARK)
        im.save(path, pnginfo=meta)
    elif path.suffix.lower() in (".jpg", ".jpeg"):
        im.save(path, quality=95, comment=MARK.encode())
    else:
        im.save(path)
    return "적용" + ("" if used_original is None else (" (도장 원본)" if used_original else " (도장 그림)"))


def main():
    args = sys.argv[1:]
    if "--frame" not in args:
        print(__doc__)
        sys.exit(2)
    i = args.index("--frame")
    frame_path = Path(args[i + 1])
    include_thumb = "--include-thumbnail" in args
    targets = [a for k, a in enumerate(args) if k not in (i, i + 1) and not a.startswith("--")]
    skill_dir = Path(__file__).resolve().parent.parent
    if not frame_path.exists() and (skill_dir / frame_path).exists():
        frame_path = skill_dir / frame_path
    cfg = json.loads(frame_path.read_text(encoding="utf-8"))
    skip = () if include_thumb else tuple(cfg.get("skip_prefixes", ["00_"]))
    files = []
    for t in targets:
        p = Path(t)
        files += sorted(f for f in p.iterdir() if f.suffix.lower() in EXTS) if p.is_dir() else [p]
    for f in files:
        if skip and f.name.startswith(skip):
            print(f"건너뜀(썸네일): {f.name}")
            continue
        print(f"{apply(f, cfg, skill_dir)}: {f.name}")


if __name__ == "__main__":
    main()
