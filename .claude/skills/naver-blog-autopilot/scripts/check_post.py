#!/usr/bin/env python3
"""원고.md 발행 전 검수.

사용: python check_post.py posts/<폴더>/원고.md [--json]
FAIL이 하나라도 있으면 종료 코드 1. 결과는 같은 폴더의 '검수리포트.md'에도 저장한다.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from postlib import as_list, load, plain, sentences  # noqa: E402

DEFAULT_LENGTH = (1400, 1800)

# (표현, 허용 횟수) — references/human-voice.md의 표와 맞춘다
AI_PHRASES = [
    (r"에 대해 알아보겠습니다|에 대해 알아볼게요|에 대해 살펴보겠습니다|알아보도록 하겠습니다", 0),
    (r"결론적으로|종합하면|종합해 보면|요약하자면|정리하자면", 0),
    (r"라고 할 수 있습니다|라고 볼 수 있습니다|것으로 보입니다", 1),
    (r"왜 그럴까요\?|무엇일까요\?|어떨까요\?", 1),
    (r"다양한", 1), (r"효과적인|효율적인", 1), (r"완벽한|최고의|혁신적인|놀라운", 0),
    (r"뿐만 아니라", 1), (r"단순한 [^.]{1,20}이 아니라|단순히 [^.]{1,20}이 아니라", 0),
    (r"도움이 되셨|도움이 되었기를|도움이 되길", 0),
    (r"궁금한 점은 댓글|댓글로 남겨 ?주세요|댓글 남겨 ?주세요", 0),
    (r"많으실 텐데요|계시죠\?|있으신가요\?", 0),
    (r"하는 것이 좋습니다|하는 것이 좋아요", 1),
    (r"그런데", 1), (r"결국", 1), (r"진짜 중요한 건", 1),
    (r"첫째,|둘째,|셋째,", 0),
]

EXPERIENCE = r"써 ?보니|써 ?봤|사용해 ?보니|사용해 ?봤|직접 써|직접 사용|제 경우엔|제가 겪|내돈내산|구매해서 써|먹어 ?보니|해 ?봤더니"
AD_FAIL = r"최저가|역대급|무조건|100 ?%|내돈내산"
AD_WARN = r"완벽|최고|1위|유일|치료|예방|완치|부작용 ?없|효능|보장"
CLICK_BAIT = r"광고[를 ]?(한 번 ?)?(클릭|눌러)|배너[를 ]?(클릭|눌러)"
ENDING_RE = re.compile(r"(습니다|입니다|해요|예요|이에요|어요|아요|네요|죠|거든요|세요|까요)[.?!…]*$")


def count_chars(blocks):
    text = ""
    for b in blocks:
        if b["kind"] in ("p", "h2", "aside"):
            text += plain(b["text"]) + "\n"
        elif b["kind"] == "list":
            text += "\n".join(plain(i["text"]) for i in b["items"]) + "\n"
    with_space = len(text.replace("\n", ""))
    no_space = len(re.sub(r"\s", "", text))
    return no_space, with_space, text


def kw_count(text, kw):
    """띄어쓰기 차이를 무시하고 센다."""
    squeezed = re.sub(r"\s", "", text)
    return squeezed.count(re.sub(r"\s", "", kw))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    path = Path(args[0])
    meta, blocks = load(path)
    res = []  # (level, 항목, 내용)

    def add(level, item, msg):
        res.append((level, item, msg))

    title = str(meta.get("title", ""))
    main_kw = str(meta.get("main_keyword", ""))
    sub_kws = as_list(meta.get("sub_keywords"))
    ptype = str(meta.get("type", "info"))
    has_exp = meta.get("experience") is True
    disclosure = str(meta.get("disclosure", "")).strip()
    closing = str(meta.get("closing_heading", "")).strip()
    lo, hi = DEFAULT_LENGTH
    length = as_list(meta.get("length"))
    if len(length) == 2:
        lo, hi = int(length[0]), int(length[1])

    no_space, with_space, body_text = count_chars(blocks)
    paras = [b for b in blocks if b["kind"] == "p"]
    h2s = [b["text"] for b in blocks if b["kind"] == "h2"]
    imgs = [b for b in blocks if b["kind"] == "img"]
    links = [b for b in blocks if b["kind"] == "link"]

    # --- 필수 항목
    for key in ("title", "main_keyword"):
        if not meta.get(key):
            add("FAIL", "front matter", f"`{key}`가 비어 있음")

    # --- 분량
    lvl = "PASS" if lo <= no_space <= hi else "FAIL"
    add(lvl, "분량", f"공백 제외 {no_space:,}자 / 공백 포함 {with_space:,}자 (기준 {lo:,}~{hi:,})")

    # --- 제목
    tlen = len(title)
    add("PASS" if tlen <= 40 else "WARN", "제목 길이", f"{tlen}자 (30자 안팎 권장, 40자 초과 시 검색 결과에서 잘림)")
    if main_kw and title:
        pos = re.sub(r"\s", "", title).find(re.sub(r"\s", "", main_kw))
        if pos == -1:
            words = main_kw.split()
            if all(w in title for w in words):
                add("WARN", "제목 키워드", f"메인 키워드 '{main_kw}'의 단어가 제목에 흩어져 있음")
            else:
                add("FAIL", "제목 키워드", f"제목에 메인 키워드 '{main_kw}'가 없음")
        else:
            half = len(re.sub(r"\s", "", title)) / 2
            add("PASS" if pos <= half else "WARN", "제목 키워드", f"메인 키워드 위치: {'앞쪽' if pos <= half else '뒤쪽 — 앞으로 옮기기'}")
    if title and not re.search(r"\d|방법|법\b|차이|비교|이유|기준|정리|해결|순서|후기|추천|가이드|체크", title):
        add("WARN", "제목 가치", "숫자·방법·대상·결과 중 하나가 제목에 보이지 않음")
    cands = as_list(meta.get("title_candidates"))
    if len(cands) < 2:
        add("WARN", "제목 후보", f"다른 후보 {len(cands)}개 (2개 권장)")

    # --- 키워드
    if main_kw:
        n = kw_count(body_text, main_kw)
        lvl = "PASS" if 4 <= n <= 7 else ("WARN" if 3 <= n <= 9 else "FAIL")
        add(lvl, "메인 키워드 횟수", f"'{main_kw}' {n}회 (기준 4~7회)")
        first = plain(paras[0]["text"]) if paras else ""
        if ptype == "brandconnect" and len(paras) > 1 and disclosure and disclosure in first:
            first = plain(paras[1]["text"])
        ok = kw_count(first, main_kw) > 0
        add("PASS" if ok else "FAIL", "도입 키워드", "도입 첫 문단에 메인 키워드 " + ("있음" if ok else "없음"))
        n_h2 = sum(1 for h in h2s if kw_count(h, main_kw) or any(kw_count(h, s) for s in sub_kws)
                   or any(w in h for w in main_kw.split()))
        add("PASS" if n_h2 >= 1 else "WARN", "소제목 키워드", f"키워드·연관어가 든 소제목 {n_h2}개 (1~2개 권장)")
    for s in sub_kws:
        n = kw_count(body_text, s)
        add("PASS" if n >= 1 else "WARN", "보조 키워드", f"'{s}' {n}회")
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", title):
        # 조사를 떼고 비교하고, 서술어(…요/…다/…까)는 약속이 아니므로 건너뛴다
        if re.search(r"(요|다|까|죠|다면|라면|하면|되면|하는|리는|되는)$", w) or w in ("정리", "총정리", "가이드", "완벽", "한눈에"):
            continue
        w = re.sub(r"(으로|에서|까지|부터|이나|은|는|이|가|을|를|에|의|도|로|과|와|만)$", "", w) if len(w) > 2 else w
        if len(w) >= 2 and kw_count(body_text, w) == 0:
            add("WARN", "제목 약속", f"제목의 '{w}'가 본문에 없음")

    # --- 구조
    add("PASS" if 3 <= len(h2s) <= 6 else "WARN", "소제목 수", f"{len(h2s)}개 (3~5개 + 마무리)")
    if closing:
        ok = bool(h2s) and h2s[-1] == closing
        add("PASS" if ok else "FAIL", "마무리 소제목", f"마지막 소제목이 '{closing}'" + ("" if ok else "가 아님"))
    long_p = [(i + 1, len(sentences(p["text"]))) for i, p in enumerate(paras) if len(sentences(p["text"])) > 3]
    if long_p:
        add("WARN", "문단 길이", "3문장 넘는 문단: " + ", ".join(f"{i}번째({n}문장)" for i, n in long_p[:8]))
    else:
        add("PASS", "문단 길이", "모든 문단 3문장 이하")
    run, worst = 0, 0
    for i, b in enumerate(blocks):
        run = run + 1 if b["kind"] == "p" else 0
        worst = max(worst, run)
    if worst >= 5:
        add("WARN", "글 덩어리", f"이미지·표·소제목 없이 문단 {worst}개가 이어지는 구간이 있음")
    if not any(b["kind"] == "toc" for b in blocks):
        add("WARN", "목차", "[목차] 줄이 없음")

    # --- 어미 반복
    ends, streak, prev, max_streak = [], 0, None, 0
    for p in paras:
        for s in sentences(p["text"]):
            m = ENDING_RE.search(s.strip())
            ends.append(m.group(1) if m else None)
    for e in ends:
        streak = streak + 1 if (e and e == prev) else 1
        prev = e
        if e:
            max_streak = max(max_streak, streak)
    add("PASS" if max_streak < 4 else "WARN", "어미 반복", f"같은 어미 최대 {max_streak}회 연속 (4회부터 단조롭게 읽힘)")

    # --- AI 표현
    hits = []
    for pat, allowed in AI_PHRASES:
        found = re.findall(pat, body_text)
        if len(found) > allowed:
            sample = found[0] if isinstance(found[0], str) else pat
            hits.append(f"'{sample}' {len(found)}회(허용 {allowed})")
    add("FAIL" if hits else "PASS", "AI 표현", "; ".join(hits) if hits else "기준 이하")
    if re.search(r"[!?]{2,}", body_text):
        add("WARN", "문장 부호", "느낌표·물음표 연속 사용")
    emo = re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", body_text)
    if emo:
        add("WARN", "이모지", f"본문 이모지 {len(emo)}개 — 프로필이 허용하는지 확인")

    # --- 경험
    exp = re.findall(EXPERIENCE, body_text)
    if exp and not has_exp:
        add("FAIL", "경험 문장", f"경험 메모 없이 1인칭 경험 표현 사용: {', '.join(sorted(set(exp)))}")
    elif exp:
        add("PASS", "경험 문장", f"경험 표현 {len(exp)}회 (experience: true)")

    # --- 이미지
    photo = [b for b in imgs if b["media"] == "이미지"]
    nums = [b["no"] for b in photo]
    add("PASS" if len(photo) >= 4 else "WARN", "이미지 수", f"본문 이미지 마커 {len(photo)}개 (5~8개 권장)")
    if nums and nums != list(range(1, len(nums) + 1)):
        add("FAIL", "이미지 번호", f"번호가 01부터 순서대로가 아님: {nums}")
    img_dir = path.parent / "images"
    if img_dir.is_dir() and photo:
        have = {int(m.group(1)) for f in img_dir.iterdir() if (m := re.match(r"(\d{2})_", f.name))}
        missing = [n for n in nums if n not in have]
        manual = [b["no"] for b in photo if re.search(r"직접 촬영|공식 이미지|캡처", b["desc"])]
        need = [n for n in missing if n not in manual]
        if need:
            add("WARN", "이미지 파일", f"images/에 파일 없는 번호: {need}")
        if manual:
            add("INFO", "사용자 준비 이미지", f"직접 넣을 자리: {manual}")

    # --- 수익·광고 규정
    if re.search(CLICK_BAIT, body_text):
        add("FAIL", "애드포스트", "광고 클릭 유도 표현 — 약관 위반")
    if ptype == "brandconnect":
        if not disclosure:
            add("FAIL", "대가성 문구", "front matter `disclosure`가 비어 있음")
        else:
            first_block = next((b for b in blocks if b["kind"] in ("p", "h2", "img", "link")), None)
            ok = bool(first_block) and first_block["kind"] == "p" and plain(first_block["text"]).strip().startswith(disclosure)
            add("PASS" if ok else "FAIL", "대가성 문구", "본문 첫 줄에 원문 그대로 " + ("있음" if ok else "없음"))
            if body_text.count(disclosure) == 0 and ok is False:
                pass
        if not links:
            add("FAIL", "제휴 링크", "🔗 링크 줄이 없음")
        else:
            ph = [l for l in links if not l["url"].startswith("http")]
            add("WARN" if ph else "PASS", "제휴 링크", f"{len(links)}곳" + (f", 그중 {len(ph)}곳은 실제 링크로 교체 필요" if ph else ""))
            if len(links) > 3:
                add("WARN", "제휴 링크", "링크 4곳 이상 — 2~3곳 권장")
        bad = sorted(set(re.findall(AD_FAIL, body_text + title)))
        if bad:
            add("FAIL", "광고 표현", f"쓰지 않는 표현: {', '.join(bad)}")
        warn = sorted(set(re.findall(AD_WARN, body_text + title)))
        if warn:
            add("WARN", "광고 표현", f"근거 확인 필요: {', '.join(warn)}")
        if not re.search(r"단점|아쉬운|안 맞|맞지 않|권하지 않|비추", body_text):
            add("WARN", "균형", "단점·안 맞는 사람에 대한 내용이 보이지 않음")
        if re.search(r"\d[\d,]*\s*원", body_text) and not re.search(r"기준|작성일|\d{4}[.\-년]", body_text):
            add("WARN", "가격", "가격에 기준 날짜가 없음")
    else:
        if links:
            add("WARN", "정보 글 링크", "type: info인데 🔗 링크가 있음 — 제휴 링크면 type을 brandconnect로")
        if disclosure:
            add("WARN", "대가성 문구", "type: info인데 disclosure가 있음")

    asides = [b for b in blocks if b["kind"] == "aside"]
    sites = [b for b in blocks if b["kind"] == "site"]
    if len(asides) > 3:
        add("WARN", "곁들임 박스", f"{len(asides)}개 — 3개를 넘으면 강조가 흐려짐")
    else:
        add("PASS" if asides else "INFO", "곁들임 박스", f"{len(asides)}개 (팁·주의·참고·요약, 글당 1~3개 권장)")
    add("PASS" if sites else "INFO", "공식 바로가기", f"{len(sites)}곳 (신청·확인할 공식 페이지가 있으면 1~2곳)")
    if len(sites) > 3:
        add("WARN", "공식 바로가기", "외부 링크 4곳 이상 — 꼭 필요한 곳만")

    tags = as_list(meta.get("tags"))
    add("PASS" if 5 <= len(tags) <= 10 else "WARN", "태그", f"{len(tags)}개 (5~10개)")

    # --- 출력
    fails = sum(1 for r in res if r[0] == "FAIL")
    warns = sum(1 for r in res if r[0] == "WARN")
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    if "--json" in sys.argv:
        print(json.dumps({"verdict": verdict, "chars_no_space": no_space, "chars_with_space": with_space,
                          "results": [{"level": l, "item": i, "detail": d} for l, i, d in res]},
                         ensure_ascii=False, indent=1))
    else:
        mark = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "INFO": "ℹ️ "}
        print(f"[{verdict}] {title}")
        for l, i, d in res:
            print(f" {mark[l]} {l:4} {i}: {d}")
        print(f"FAIL {fails} / WARN {warns}")
    report = [f"# 검수 리포트: {title}", "", f"- 판정: **{verdict}** (FAIL {fails}, WARN {warns})",
              f"- 글 종류: {ptype} / 프로필: {meta.get('profile', '-')}",
              f"- 키워드: {main_kw} / {', '.join(map(str, sub_kws))}", "",
              "| 판정 | 항목 | 내용 |", "| --- | --- | --- |"]
    report += [f"| {l} | {i} | {d} |" for l, i, d in res]
    (path.parent / "검수리포트.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
