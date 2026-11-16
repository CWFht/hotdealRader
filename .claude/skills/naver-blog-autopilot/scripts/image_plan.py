#!/usr/bin/env python3
"""원고의 이미지 구성을 표(이미지구성.md)와 한 장짜리 미리보기(이미지구성_미리보기.png)로 만든다.

사용: python image_plan.py posts/<폴더>/원고.md
- 본문 마커 순서대로 번호, 넣을 자리(소제목), 장면, 제작 방식, 상태를 정리한다.
- 아직 없는 이미지는 미리보기에 회색 빈칸으로 표시해 무엇을 더 준비해야 하는지 한눈에 보이게 한다.
- 표는 표준 출력으로도 나오므로 납품 메시지에 그대로 붙인다.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from postlib import load  # noqa: E402

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]


def font(size):
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = Path(sys.argv[1])
    base = path.parent
    meta, blocks = load(path)
    img_dir = base / "images"
    files = {}
    if img_dir.is_dir():
        for f in sorted(img_dir.iterdir()):
            m = re.match(r"(\d{2})_", f.name)
            if m and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                files[int(m.group(1))] = f

    def names(spec, key):
        p = base / spec
        if not p.exists():
            return set()
        return {int(c["file"][:2]) for c in json.loads(p.read_text(encoding="utf-8")).get(key, [])
                if c.get("file", "")[:2].isdigit()}
    cards, gpts = names("cards.json", "cards"), names("gpt_images.json", "images")

    rows, section = [], "도입"
    if 0 in files or 0 in cards:
        rows.append((0, "대표 이미지", "썸네일", "디자인 카드" if 0 in cards else "직접 준비"))
    for b in blocks:
        if b["kind"] == "h2":
            section = b["text"]
        elif b["kind"] == "img" and b["media"] == "이미지":
            n, desc = b["no"], b["desc"]
            if n in cards:
                how = "디자인 카드"
            elif n in gpts:
                how = "GPT 이미지"
            elif re.search(r"공식 이미지", desc):
                how = "공식 이미지 (직접 준비)"
            elif re.search(r"직접 촬영|캡처", desc):
                how = "직접 촬영·캡처"
            else:
                how = "미정"
            rows.append((n, section, desc, how))

    lines = ["| 번호 | 넣을 자리 | 장면 | 제작 방식 | 상태 | 파일 |", "| --- | --- | --- | --- | --- | --- |"]
    todo = []
    for n, sec, desc, how in rows:
        f = files.get(n)
        if f:
            state = "완료"
        elif how == "GPT 이미지":
            state = "생성 필요 (프롬프트 있음)"
        else:
            state = "준비 필요"
        if not f:
            todo.append(f"{n:02d}")
        lines.append(f"| {n:02d} | {sec} | {desc} | {how} | {state} | {f.name if f else '-'} |")
    done = sum(1 for r in rows if r[0] in files)
    summary = f"이미지 {len(rows)}장 중 {done}장 완료" + (f", 준비 필요: {', '.join(todo)}" if todo else "")
    text = f"# 이미지 구성: {meta.get('title', '')}\n\n{summary}\n\n" + "\n".join(lines) + "\n"
    (base / "이미지구성.md").write_text(text, encoding="utf-8")
    print(summary)
    print("\n".join(lines))

    # 미리보기: 3열 격자, 번호 순서대로
    if rows:
        cw, ch, pad, cols = 480, 320, 16, 3
        n_rows = (len(rows) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw + (cols + 1) * pad, n_rows * ch + (n_rows + 1) * pad), "#e9ecf0")
        d = ImageDraw.Draw(sheet)
        for i, (n, sec, desc, how) in enumerate(rows):
            x, y = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + pad)
            f = files.get(n)
            if f:
                im = Image.open(f).convert("RGB")
                im.thumbnail((cw, ch))
                sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
            else:
                d.rectangle([x, y, x + cw - 1, y + ch - 1], fill="#ffffff", outline="#b8bec8", width=3)
                d.text((x + cw / 2, y + ch / 2), "?", font=font(120), fill="#c5cad3", anchor="mm")
            d.rectangle([x, y, x + 64, y + 44], fill="#16181d" if f else "#d9261c")
            d.text((x + 32, y + 22), f"{n:02d}", font=font(26), fill="#ffffff", anchor="mm")
        out = base / "이미지구성_미리보기.png"
        sheet.save(out)
        print(out)


if __name__ == "__main__":
    main()
