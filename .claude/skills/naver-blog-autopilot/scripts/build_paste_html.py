#!/usr/bin/env python3
"""원고.md → 스마트에디터 ONE 붙여넣기용 HTML.

사용: python build_paste_html.py posts/<폴더>/원고.md
출력: 같은 폴더의 '<제목>_스마트에디터_붙여넣기.html'

스마트에디터는 붙여넣을 때 h 태그와 class를 버리거나 줄이므로, 모든 서식을
<p> + 인라인 스타일로 만든다. 소제목 19px, 본문 16px, 강조는 굵게+밑줄+노란 음영.
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from postlib import as_list, load  # noqa: E402

P = 'style="font-size:16px;line-height:1.8;margin:0;"'
H = 'style="font-size:19px;line-height:1.6;margin:0;"'
MARK = 'style="font-size:13px;line-height:1.6;margin:0;background-color:#e7f1ff;color:#1a56b0;padding:4px 8px;"'
TD = 'style="border:1px solid #c9c9c9;padding:8px 10px;font-size:15px;line-height:1.6;"'
TH = 'style="border:1px solid #c9c9c9;padding:8px 10px;font-size:15px;line-height:1.6;background-color:#f3f5f7;"'
EM = '<b><u><span style="background-color:#fff3a3">{}</span></u></b>'
GAP = f"<p {P}>&nbsp;</p>"


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", lambda m: EM.format(m.group(1)), t)
    return t


def table_html(rows):
    out = ['<table style="border-collapse:collapse;width:100%;">']
    for i, r in enumerate(rows):
        cell = "th" if i == 0 else "td"
        style = TH if i == 0 else TD
        out.append("<tr>" + "".join(f"<{cell} {style}>{inline(c)}</{cell}>" for c in r) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def render(meta, blocks):
    h2s = [b["text"] for b in blocks if b["kind"] == "h2"]
    out = []
    for b in blocks:
        k = b["kind"]
        if k == "p":
            out += [f"<p {P}>{inline(b['text'])}</p>", GAP]
        elif k == "h2":
            out += [GAP, f"<p {H}><b>{inline(b['text'])}</b></p>", GAP]
        elif k == "hr":
            out.append("<hr>")
        elif k == "toc":
            out += [table_html([["목차"]] + [[h] for h in h2s]), GAP]
        elif k == "table":
            out += [table_html(b["rows"]), GAP]
        elif k == "list":
            for n, it in enumerate(b["items"], 1):
                bullet = f"{n}." if it["ordered"] else "•"
                out.append(f"<p {P}>{bullet} {inline(it['text'])}</p>")
            out.append(GAP)
        elif k == "img":
            out += [f"<p {MARK}>{html.escape(b['raw'])}</p>", GAP]
        elif k == "link":
            url, label = b["url"], html.escape(b["label"])
            if url.startswith("http"):
                out += [f'<p {P}><a href="{html.escape(url)}">{label} 가격·옵션 확인하기</a></p>', GAP]
            else:
                out += [f"<p {MARK}>🔗 여기에 제휴 링크 삽입 │ {label}</p>", GAP]
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 붙여넣기용</title>
<style>
body{{margin:0;background:#f4f5f7;font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#222}}
.bar{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 16px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;z-index:2}}
.bar button{{font-size:15px;padding:10px 14px;border:0;border-radius:8px;background:#03c75a;color:#fff;font-weight:700;cursor:pointer}}
.bar button.sub{{background:#444}}
.bar span{{font-size:13px;color:#666}}
.wrap{{max-width:760px;margin:16px auto;padding:0 16px}}
.box{{background:#fff;border-radius:12px;padding:20px;margin-bottom:16px}}
.label{{font-size:12px;color:#888;margin:0 0 8px}}
#title{{font-size:22px;font-weight:700;margin:0;line-height:1.4}}
#tags{{font-size:15px;line-height:1.7;margin:0;word-break:keep-all}}
ul.steps{{margin:0;padding-left:18px;font-size:14px;line-height:1.8;color:#444}}
</style></head><body>
<div class="bar">
<button onclick="copyText('title',this)">① 제목 복사</button>
<button onclick="copyHtml(this)">② 본문 복사</button>
<button class="sub" onclick="copyText('tags',this)">③ 태그 복사</button>
<span id="msg"></span>
</div>
<div class="wrap">
<div class="box"><p class="label">제목 (네이버 제목 칸에 붙여넣기)</p><p id="title">{title}</p>{cands}</div>
<div class="box"><p class="label">본문 (② 본문 복사 → 스마트에디터 본문에 붙여넣기 → 파란 줄 자리에 이미지 삽입 후 그 줄 삭제)</p>
<div id="body">
{body}
</div></div>
<div class="box"><p class="label">태그</p><p id="tags">{tags}</p></div>
<div class="box"><p class="label">발행 순서</p><ul class="steps">
<li>① 제목 복사 → 네이버 글쓰기 제목 칸</li>
<li>② 본문 복사 → 본문 칸에 붙여넣기</li>
<li>파란 줄(📷 이미지 NN) 자리에 images 폴더의 같은 번호 파일을 넣고 파란 줄은 지우기</li>
<li>③ 태그 복사 → 발행 창의 태그 칸</li>
<li>대표 이미지를 00_썸네일로 지정하고 발행</li>
</ul></div>
</div>
<script>
function done(btn,ok){{var m=document.getElementById('msg');m.textContent=ok?'복사됨: '+btn.textContent:'복사 실패 — 직접 드래그해서 복사하세요';setTimeout(function(){{m.textContent=''}},2500)}}
function selectNode(el){{var r=document.createRange();r.selectNodeContents(el);var s=getSelection();s.removeAllRanges();s.addRange(r)}}
function copyText(id,btn){{var el=document.getElementById(id);var t=el.innerText;
 if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).then(function(){{done(btn,true)}},function(){{selectNode(el);done(btn,document.execCommand('copy'))}})}}
 else{{selectNode(el);done(btn,document.execCommand('copy'))}}}}
function copyHtml(btn){{var el=document.getElementById('body');
 try{{var item=new ClipboardItem({{'text/html':new Blob([el.innerHTML],{{type:'text/html'}}),'text/plain':new Blob([el.innerText],{{type:'text/plain'}})}});
 navigator.clipboard.write([item]).then(function(){{done(btn,true)}},function(){{selectNode(el);done(btn,document.execCommand('copy'))}})}}
 catch(e){{selectNode(el);done(btn,document.execCommand('copy'))}}}}
</script></body></html>
"""


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = Path(sys.argv[1])
    meta, blocks = load(path)
    title = str(meta.get("title", "제목 없음"))
    cands = as_list(meta.get("title_candidates"))
    cand_html = ""
    if cands:
        cand_html = '<p class="label" style="margin-top:12px">다른 후보</p>' + "".join(
            f'<p style="font-size:14px;margin:2px 0;color:#555">{html.escape(str(c))}</p>' for c in cands)
    tags = " ".join("#" + str(t).replace(" ", "") for t in as_list(meta.get("tags")))
    page = PAGE.format(title=html.escape(title), cands=cand_html, body=render(meta, blocks), tags=html.escape(tags))
    safe = re.sub(r'[\\/:*?"<>|]', "", title)[:40].strip()
    out = path.parent / f"{safe}_스마트에디터_붙여넣기.html"
    out.write_text(page, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
