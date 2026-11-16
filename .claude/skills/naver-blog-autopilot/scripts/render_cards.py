#!/usr/bin/env python3
"""cards.json → 디자인 카드 HTML/PNG.

사용: python render_cards.py posts/<폴더>/cards.json
출력: <out_dir>/<file>.png (브라우저가 없으면 <out_dir>/_html/<file>.html만)

PNG는 Playwright(파이썬 또는 Node)로 찍는다. 둘 다 없으면 HTML만 남기고 종료 코드 3.
형식은 references/images.md 참고.
"""
import base64
import html
import json
import mimetypes
import shutil
import subprocess
import sys
from pathlib import Path

SIZES = {"thumbnail": (1024, 1024), "list": (1536, 1024), "table": (1536, 1024)}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(w)spx;height:%(h)spx;overflow:hidden}
body{font-family:%(font)s,'Pretendard','Noto Sans KR','Apple SD Gothic Neo','Malgun Gothic','NanumGothic','WenQuanYi Zen Hei',sans-serif;
 color:#16181d;background:#fff;word-break:keep-all;-webkit-font-smoothing:antialiased}
.card{width:100%%;height:100%%;display:flex;flex-direction:column;position:relative}
.top{height:18px;background:%(color)s}
.bottom{height:84px;display:flex;align-items:center;justify-content:space-between;padding:0 56px;
 font-size:30px;color:#6b7280;border-top:2px solid #eef0f3}
.bottom b{color:%(color)s}
.main{flex:1;padding:64px 80px 40px;display:flex;flex-direction:column;justify-content:center;min-height:0}
h1{font-size:88px;line-height:1.25;font-weight:800;letter-spacing:-2px;margin-bottom:56px}
h1 i{font-style:normal;color:%(color)s}
ol,ul{list-style:none;display:flex;flex-direction:column;gap:%(gap)spx}
li{display:flex;align-items:center;gap:30px;font-size:%(isize)spx;line-height:1.3;font-weight:600}
li .n{flex:none;width:1.5em;height:1.5em;border-radius:50%%;background:%(color)s;color:#fff;
 display:flex;align-items:center;justify-content:center;font-size:.8em;font-weight:800}
li .d{flex:none;width:.42em;height:.42em;border-radius:50%%;background:%(color)s;margin:0 8px}
table{width:100%%;border-collapse:collapse;font-size:%(tfs)spx}
th{background:%(color)s;color:#fff;font-weight:700;padding:.65em .6em;text-align:center}
td{padding:.65em .6em;border-bottom:2px solid #e5e7eb;text-align:center;line-height:1.3}
td:first-child{font-weight:700;background:#f6f7f9;white-space:nowrap}
.note{margin-top:32px;font-size:30px;color:#6b7280}
/* thumbnail */
.thumb h1{max-width:100%%}
.thumb{align-items:center;justify-content:center;text-align:center;padding:80px;background:%(bg)s;background-size:cover;background-position:center}
.thumb .shade{position:absolute;inset:0;background:%(shade)s}
.thumb>*{position:relative}
.kicker{display:inline-block;font-size:46px;font-weight:700;padding:14px 36px;border-radius:999px;background:%(color)s;color:#fff;margin-bottom:40px}
.thumb h1{font-size:%(tsize)spx;line-height:1.2;margin-bottom:36px;color:%(tcolor)s;white-space:pre}
.thumb .sub{font-size:52px;font-weight:600;color:%(scolor)s}
.thumb .brand{position:absolute;bottom:52px;left:0;right:0;font-size:34px;color:%(scolor)s;opacity:.85}
"""


def esc(s):
    return html.escape(str(s), quote=False)


def data_uri(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def build(card, brand, base):
    ctype = card.get("type", "list")
    if ctype not in SIZES:
        raise ValueError(f"알 수 없는 type: {ctype}")
    w, h = SIZES[ctype]
    color = card.get("color") or brand.get("color", "#1f6feb")
    name = brand.get("name", "")
    font = "'" + brand.get("font", "Pretendard") + "'"
    v = dict(w=w, h=h, color=color, font=font, bg="#f3f6fb", shade="transparent",
             tsize=112, tcolor="#16181d", scolor="#4b5563", gap=34, isize=60, tfs=48)
    n_items = len(card.get("items", []))
    v["isize"] = 66 if n_items <= 3 else (58 if n_items == 4 else 50)
    v["gap"] = 44 if n_items <= 3 else 32
    n_rows = len(card.get("rows", []))
    v["tfs"] = 52 if n_rows <= 3 else (46 if n_rows == 4 else 40)
    widest = max((sum(len(str(c)) for c in r) for r in card.get("rows", [])), default=0)
    if widest > 20:
        v["tfs"] = min(v["tfs"], 44 if widest <= 26 else 38)
    title = str(card.get("title", ""))
    if ctype == "thumbnail":
        longest = max((len(x) for x in title.split("\n")), default=1)
        v["tsize"] = 156 if longest <= 7 else (132 if longest <= 9 else (112 if longest <= 11 else 90))
        if card.get("background"):
            v["bg"] = f"url('{data_uri(base / card['background'])}')"
            v["shade"] = "rgba(0,0,0,.45)"
            v["tcolor"], v["scolor"] = "#fff", "#f1f5f9"
        body = (f'<div class="card thumb"><div class="shade"></div>'
                + (f'<div class="kicker">{esc(card["kicker"])}</div>' if card.get("kicker") else "")
                + f"<h1>{esc(title)}</h1>"
                + (f'<div class="sub">{esc(card["sub"])}</div>' if card.get("sub") else "")
                + (f'<div class="brand">{esc(name)}</div>' if name else "") + "</div>")
    else:
        if ctype == "list":
            tag = "ol" if card.get("numbered") else "ul"
            lis = "".join(
                f'<li><span class="{"n" if card.get("numbered") else "d"}">{i if card.get("numbered") else ""}</span>'
                f"<span>{esc(it)}</span></li>" for i, it in enumerate(card.get("items", []), 1))
            inner = f"<{tag}>{lis}</{tag}>"
        else:
            head = "".join(f"<th>{esc(c)}</th>" for c in card.get("head", []))
            rows = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in card.get("rows", []))
            inner = f"<table><tr>{head}</tr>{rows}</table>"
        note = f'<div class="note">{esc(card["note"])}</div>' if card.get("note") else ""
        body = (f'<div class="card"><div class="top"></div><div class="main"><div class="fit"><h1>{esc(title)}</h1>{inner}{note}</div></div>'
                f'<div class="bottom"><b>{esc(name)}</b><span>{esc(card.get("footer", ""))}</span></div></div>')
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">'
            f"<style>{CSS % v}</style></head><body>{body}<script>{FIT_JS}</script></body></html>")
    return page, w, h


# 글자가 넘치면 스스로 줄인다: 본문 카드는 전체 배율, 썸네일은 제목 글자 크기
FIT_JS = """
function fit(){var m=document.querySelector('.main'),f=document.querySelector('.fit');
if(m&&f){var z=1;f.style.zoom=1;while((m.scrollHeight>m.clientHeight+2||m.scrollWidth>m.clientWidth+2)&&z>0.6){z-=0.03;f.style.zoom=z}}
var t=document.querySelector('.thumb'),h=t&&t.querySelector('h1');
if(h){var s=parseFloat(getComputedStyle(h).fontSize),max=t.clientWidth-160;while(h.scrollWidth>max&&s>56){s-=4;h.style.fontSize=s+'px'}}
document.body.dataset.fit='1'}
(document.fonts&&document.fonts.ready?Promise.race([document.fonts.ready,new Promise(function(r){setTimeout(r,4000)})]):Promise.resolve()).then(fit);
"""

NODE_JS = r"""
const {chromium}=require('playwright');
(async()=>{const jobs=JSON.parse(process.argv[1]);const b=await chromium.launch();
for(const j of jobs){const p=await b.newPage({viewport:{width:j.w,height:j.h}});
await p.goto('file://'+j.html,{waitUntil:'load'});
await p.waitForSelector('body[data-fit]',{timeout:8000}).catch(()=>{});
const over=await p.evaluate(()=>{const m=document.querySelector('.main,.thumb');return m?m.scrollHeight>m.clientHeight+2||m.scrollWidth>m.clientWidth+2:false});
await p.screenshot({path:j.png});console.log((over?'OVERFLOW ':'OK ')+j.png);await p.close()}
await b.close()})().catch(e=>{console.error(e.message);process.exit(1)});
"""


def shoot(jobs):
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            for j in jobs:
                pg = br.new_page(viewport={"width": j["w"], "height": j["h"]})
                pg.goto("file://" + j["html"], wait_until="load")
                try:
                    pg.wait_for_selector("body[data-fit]", timeout=8000)
                except Exception:
                    pass
                over = pg.evaluate("()=>{const m=document.querySelector('.main,.thumb');return m?m.scrollHeight>m.clientHeight+2||m.scrollWidth>m.clientWidth+2:false}")
                pg.screenshot(path=j["png"])
                print(("OVERFLOW " if over else "OK ") + j["png"])
            br.close()
        return True
    except ImportError:
        pass
    except Exception as e:  # 브라우저 미설치 등
        print(f"python playwright 실패: {e}", file=sys.stderr)
    if shutil.which("node"):
        r = subprocess.run(["node", "-e", NODE_JS, json.dumps(jobs)], capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode == 0:
            return True
        print(f"node playwright 실패: {r.stderr.strip()[:300]}", file=sys.stderr)
    return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    spec_path = Path(sys.argv[1]).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    base = spec_path.parent
    out_dir = base / spec.get("out_dir", "images")
    html_dir = out_dir / "_html"
    html_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for card in spec.get("cards", []):
        page, w, h = build(card, spec.get("brand", {}), base)
        name = Path(card["file"]).stem
        hp = html_dir / f"{name}.html"
        hp.write_text(page, encoding="utf-8")
        jobs.append({"html": str(hp), "png": str(out_dir / f"{name}.png"), "w": w, "h": h})
    if not jobs:
        print("cards가 비어 있음")
        return
    if shoot(jobs):
        print(f"카드 {len(jobs)}장 완료. OVERFLOW로 표시된 카드는 문구를 줄이거나 나눠서 다시 렌더링하세요.")
    else:
        print(f"브라우저를 찾지 못해 HTML만 만들었습니다: {html_dir}\n"
              "브라우저에서 열어 화면 캡처하거나, Playwright가 있는 환경에서 다시 실행하세요.")
        sys.exit(3)


if __name__ == "__main__":
    main()
