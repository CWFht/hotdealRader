"""원고.md 파서. check_post.py와 build_paste_html.py가 함께 쓴다."""
import re
import sys
from pathlib import Path

IMG_RE = re.compile(r"^(📷|🎞|🎬)\s*(이미지|GIF|MP4)\s*(\d+)\s*[│|]\s*(.+)$")
LINK_RE = re.compile(r"^🔗\s*링크\s*[│|]\s*(.+?)\s*[│|]\s*(.+?)\s*$")
SITE_RE = re.compile(r"^🌐\s*바로가기\s*[│|]\s*(.+?)\s*[│|]\s*(https?://\S+)\s*$")
ASIDE_RE = re.compile(r"^>\s*\[(팁|주의|참고|요약)\]\s*(.+)$")
HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
SENT_END_RE = re.compile(r"(?<=[.?!…])\s+|(?<=[다요죠까네])\.\s*")


def _scalar(v):
    v = v.split(" #")[0].strip() if not v.strip().startswith(('"', "'")) else v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _inline_list(v):
    inner = v.strip()[1:-1]
    return [_scalar(x) for x in inner.split(",") if x.strip()]


def parse_front_matter(text):
    """PyYAML 없이 읽는 단순 front matter: 스칼라, [a, b] 목록, '- ' 블록 목록."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head, body = text[3:end], text[end + 4:]
    meta, key = {}, None
    for raw in head.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        m = re.match(r"^\s+-\s+(.*)$", raw) or re.match(r"^-\s+(.*)$", raw)
        if m and key:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(_scalar(m.group(1)))
            continue
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        stripped = val.split(" #")[0].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            meta[key] = _inline_list(stripped)
        elif stripped == "":
            meta[key] = ""
        else:
            meta[key] = _scalar(val)
    return meta, body.lstrip("\n")


def parse_blocks(body):
    """본문을 블록 목록으로 나눈다.
    kind: h2 | p | img | link | site | aside | hr | table | toc | list
    """
    blocks, para, table, items = [], [], [], []

    def flush():
        nonlocal para, table, items
        if para:
            blocks.append({"kind": "p", "text": " ".join(para)})
            para = []
        if table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table]
            rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            blocks.append({"kind": "table", "rows": rows})
            table = []
        if items:
            blocks.append({"kind": "list", "items": items})
            items = []

    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("|"):
            if para or items:
                flush()
            table.append(line)
            continue
        if table:
            flush()
        m_item = re.match(r"^(\d+[.)]|[-*•])\s+(.*)$", line)
        if m_item and not HR_RE.match(line):
            if para:
                flush()
            ordered = m_item.group(1)[0].isdigit()
            items.append({"ordered": ordered, "text": m_item.group(2)})
            continue
        if items:
            flush()
        if line.startswith("## "):
            flush()
            blocks.append({"kind": "h2", "text": line[3:].strip()})
        elif line.startswith("# "):
            flush()  # 제목은 front matter의 title을 쓴다
        elif HR_RE.match(line):
            flush()
            blocks.append({"kind": "hr"})
        elif line == "[목차]":
            flush()
            blocks.append({"kind": "toc"})
        elif IMG_RE.match(line):
            flush()
            m = IMG_RE.match(line)
            blocks.append({"kind": "img", "media": m.group(2), "no": int(m.group(3)),
                           "desc": m.group(4).strip(), "raw": line})
        elif SITE_RE.match(line):
            flush()
            m = SITE_RE.match(line)
            blocks.append({"kind": "site", "label": m.group(1), "url": m.group(2)})
        elif ASIDE_RE.match(line):
            flush()
            m = ASIDE_RE.match(line)
            blocks.append({"kind": "aside", "label": m.group(1), "text": m.group(2).strip()})
        elif LINK_RE.match(line):
            flush()
            m = LINK_RE.match(line)
            blocks.append({"kind": "link", "label": m.group(1), "url": m.group(2)})
        else:
            para.append(line)
    flush()
    return blocks


def plain(text):
    """마크다운 강조·링크 표기를 걷어낸 글자."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return re.sub(r"(\*\*|__|\*|`)", "", text)


def sentences(text):
    parts = re.split(r"(?<=[.?!…])\s+", plain(text).strip())
    return [p for p in parts if p.strip()]


def load(path):
    text = Path(path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    return meta, parse_blocks(body)


def as_list(v):
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)
