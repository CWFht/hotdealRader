#!/usr/bin/env python3
"""gpt_images.json → 'GPT_이미지_프롬프트.md' (+ OPENAI_API_KEY가 있으면 이미지 생성).

사용: python gpt_images.py posts/<폴더>/gpt_images.json [--no-api]

프롬프트 파일은 항상 만든다. 사용자가 ChatGPT에 한 블록씩 붙여 넣으면 같은 결과를 얻는다.
API 모델은 환경 변수 OPENAI_IMAGE_MODEL로 바꿀 수 있다(기본 gpt-image-1).
형식은 references/images.md 참고.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

GUARD = "이미지 안에 글자, 숫자, 로고, 워터마크를 넣지 않는다. 실제 브랜드 제품 디자인을 따라 그리지 않는다."
RATIO = {"1536x1024": "가로 3:2", "1024x1024": "정사각형 1:1", "1024x1536": "세로 2:3"}


def full_prompt(img, style):
    parts = [img["prompt"].strip()]
    if style:
        parts.append("스타일: " + style.strip())
    parts.append(GUARD)
    return " ".join(parts)


def generate(prompt, size, key, model):
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps({"model": model, "prompt": prompt, "size": size, "n": 1}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        item = json.load(r)["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    with urllib.request.urlopen(item["url"], timeout=120) as r:
        return r.read()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    spec_path = Path(args[0]).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    base = spec_path.parent
    out_dir = base / spec.get("out_dir", "images")
    out_dir.mkdir(parents=True, exist_ok=True)
    style = spec.get("style", "")
    images = spec.get("images", [])

    md = ["# GPT 이미지 프롬프트", "",
          "ChatGPT에 아래 블록을 하나씩 붙여 넣어 이미지를 만들고, 적힌 파일 이름으로 `images/` 폴더에 저장하세요.",
          "파일 이름 앞의 번호가 본문의 `📷 이미지 NN` 번호입니다.", ""]
    for img in images:
        size = img.get("size", "1536x1024")
        md += [f"## {img['file']}", "", f"- 넣을 자리: {img.get('alt', '')}", f"- 크기: {size} ({RATIO.get(size, size)})", "",
               "```", f"{RATIO.get(size, size)} 비율의 이미지를 만들어 줘. {full_prompt(img, style)}", "```", ""]
    (base / "GPT_이미지_프롬프트.md").write_text("\n".join(md), encoding="utf-8")
    print(f"프롬프트 {len(images)}개 → {base / 'GPT_이미지_프롬프트.md'}")

    key = os.environ.get("OPENAI_API_KEY")
    if "--no-api" in sys.argv or not key:
        if not key:
            print("OPENAI_API_KEY가 없어 이미지는 만들지 않았습니다. 프롬프트 파일을 사용자에게 전달하세요.")
        return
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
    failed = 0
    for img in images:
        target = out_dir / img["file"]
        if target.exists():
            print(f"건너뜀(이미 있음): {target.name}")
            continue
        try:
            target.write_bytes(generate(full_prompt(img, style), img.get("size", "1536x1024"), key, model))
            print(f"생성: {target.name}")
        except (urllib.error.URLError, KeyError, ValueError, OSError) as e:
            failed += 1
            detail = e.read().decode()[:200] if isinstance(e, urllib.error.HTTPError) else str(e)
            print(f"실패: {target.name} — {detail}", file=sys.stderr)
    if failed:
        print(f"{failed}장 실패. 프롬프트 파일로 직접 만들도록 검수 포인트에 적으세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
