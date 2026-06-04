#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

UA = os.getenv(
    "HOTDEAL_RADAR_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 HotdealRadar/1.7"
)
DELAY = float(os.getenv("HOTDEAL_RADAR_DELAY", "1.1"))
MAX_PER_SOURCE = int(os.getenv("HOTDEAL_RADAR_MAX_PER_SOURCE", "35"))
DETAIL_LIMIT = int(os.getenv("HOTDEAL_RADAR_DETAIL_LIMIT", "25"))

SOURCES = [
    {"name": "루리웹", "url": "https://bbs.ruliweb.com/market/board/1020", "base": "https://bbs.ruliweb.com", "enabled": True},
    {"name": "뽐뿌", "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu", "base": "https://www.ppomppu.co.kr", "enabled": True},
    {"name": "뽐뿌_해외", "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu4", "base": "https://www.ppomppu.co.kr", "enabled": True},
    {"name": "퀘이사존", "url": "https://quasarzone.com/bbs/qb_saleinfo", "base": "https://quasarzone.com", "enabled": True},
    {"name": "에펨코리아", "url": "https://www.fmkorea.com/hotdeal", "base": "https://www.fmkorea.com", "enabled": True},
    {"name": "클리앙_알뜰구매", "url": "https://www.clien.net/service/board/jirum", "base": "https://www.clien.net", "enabled": True},
    {"name": "딜바다", "url": "https://www.dealbada.com/bbs/board.php?bo_table=deal_domestic", "base": "https://www.dealbada.com", "enabled": True},
    # 네이버 카페는 로그인/권한 문제가 잦아 기본 비활성화합니다.
    {"name": "맘스홀릭", "url": "https://cafe.naver.com/imsanbu", "base": "https://cafe.naver.com", "enabled": False},
]

SHOP_DOMAINS = [
    "coupang.com", "smartstore.naver.com", "brand.naver.com", "shopping.naver.com",
    "gmarket.co.kr", "auction.co.kr", "11st.co.kr", "lotteon.com", "ssg.com",
    "wemakeprice.com", "tmon.co.kr", "aliexpress.com", "amazon.com", "amazon.co.jp",
    "musinsa.com", "oliveyoung.co.kr", "kurly.com", "costco.co.kr", "e-himart.co.kr",
    "lotteimall.com", "homeplus.co.kr", "emart.ssg.com", "temu.com", "naver.com", "store.kakao.com", "ohou.se", "29cm.co.kr", "zigzag.kr",
]
SOURCE_DOMAINS = ["ruliweb.com", "ppomppu.co.kr", "quasarzone.com", "fmkorea.com", "clien.net", "dealbada.com", "cafe.naver.com"]
BAD_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".ico")
SHOP_WORDS = ["쿠팡", "네이버", "지마켓", "G마켓", "옥션", "11번가", "롯데온", "홈플러스", "이마트", "알리", "SSG", "무신사", "하이마트", "올리브영", "다이소", "테무", "아마존", "코스트코", "컬리"]
HOT_WORDS = ["역대가", "핫딜", "특가", "체감가", "빅세일", "대란", "무료", "쿠폰", "할인"]
FREE_WORDS = ["무료배송", "무배", "무료 배송"]
END_WORDS = ["품절", "종료", "마감", "sold out"]
CATEGORY_WORDS = {
    "식품·간식": ["식품", "커피", "간식", "음료", "라면", "쌀", "고기", "닭가슴살", "과자", "우유", "밀키트", "냉동"],
    "생필품": ["세제", "휴지", "물티슈", "청소", "욕실", "샴푸", "치약", "건전지", "생활"],
    "주방·수납": ["주방", "수납", "정리함", "냄비", "프라이팬", "식기", "텀블러", "보관용기"],
    "육아": ["육아", "기저귀", "분유", "이유식", "아기", "젖병", "카시트", "유모차", "유아"],
    "반려동물": ["반려", "강아지", "고양이", "사료", "배변패드", "모래", "펫"],
    "뷰티·건강": ["뷰티", "화장품", "선크림", "마스크팩", "영양제", "건강", "향수", "바디"],
    "패션": ["패션", "의류", "신발", "패딩", "무신사", "운동화", "티셔츠"],
    "IT·가전": ["노트북", "태블릿", "SSD", "충전기", "케이블", "마우스", "키보드", "에어컨", "냉장고", "청소기", "TV", "세탁기", "건조기", "게임", "스팀"],
    "상품권·포인트": ["상품권", "네이버페이", "페이", "쿠폰", "적립", "해피머니", "컬쳐랜드"],
    "해외직구": ["알리", "AliExpress", "테무", "아마존", "직구", "해외"],
}

def main() -> None:
    deals: list[dict] = []
    statuses: list[dict] = []
    for src in SOURCES:
        if not src.get("enabled", True):
            statuses.append(make_status(src, "disabled", 0, 0, "기본 비활성화"))
            continue
        try:
            print(f"Collecting {src['name']} ...", flush=True)
            html = fetch(src["url"])
            items = parse_listing(html, src)[:MAX_PER_SOURCE]
            purchase_count = 0
            for idx, item in enumerate(items):
                if idx < DETAIL_LIMIT and not item.get("purchase_url"):
                    purl = find_purchase_url(item["source_url"])
                    if purl:
                        item["purchase_url"] = purl
                        item["purchase_domain"] = short_domain(purl)
                if item.get("purchase_url"):
                    purchase_count += 1
                    time.sleep(DELAY + random.random() * 0.4)
                item["score"] = calc_score(item)
                deals.append(item)
            statuses.append(make_status(src, "ok" if items else "empty", len(items), purchase_count, "수집 완료" if items else "후보 없음 또는 사이트 구조 변경"))
            print(f"  {src['name']}: {len(items)} deals, purchase links {purchase_count}", flush=True)
        except Exception as exc:
            print(f"  failed {src['name']}: {type(exc).__name__}: {exc}", flush=True)
            statuses.append(make_status(src, "failed", 0, 0, f"{type(exc).__name__}: {str(exc)[:150]}"))
        time.sleep(DELAY + random.random() * 0.5)

    deals = dedupe(deals)
    generated_at = datetime.now(timezone.utc).isoformat()
    write_json(DATA_DIR / "deals.json", {"generated_at": generated_at, "count": len(deals), "deals": deals})
    write_json(DATA_DIR / "sources.json", {"generated_at": generated_at, "sources": statuses})
    print(f"Saved {len(deals)} deals", flush=True)

def fetch(url: str) -> str:
    response = requests.get(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }, timeout=22)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text

def normalize_link(src: dict, href: str) -> str:
    # 중요: 뽐뿌처럼 href가 view.php로 시작하는 경우
    # root base가 아니라 현재 목록 URL 기준으로 합쳐야 /zboard/view.php가 됩니다.
    return urljoin(src.get("url") or src.get("base") or "", href or "")

def parse_listing(html: str, src: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.select("a[href]"):
        title = clean(a.get_text(" ", strip=True))
        url = normalize_link(src, a.get("href") or "")
        if not valid_candidate(title, url):
            continue
        key = normalize(title, url)
        if key in seen:
            continue
        seen.add(key)
        context = clean(parent_text(a))
        price = extract_price(title)
        direct_purchase = ""
        if is_good_external(url, src["url"]):
            direct_purchase = unwrap_url(url)
        item = {
            "id": sha(src["name"] + title + url),
            "title": title,
            "source": src["name"],
            "source_url": url,
            "url": url,
            "purchase_url": direct_purchase,
            "purchase_domain": short_domain(direct_purchase) if direct_purchase else "",
            "shop": guess_shop(title),
            "category": guess_category(title),
            "price_text": f"{price:,}원" if price else "가격 확인",
            "price_value": price,
            "comments": extract_comments(title + " " + context),
            "likes": extract_likes(context),
            "views": extract_views(context),
            "flags": guess_flags(title),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        out.append(item)
    return out

def find_purchase_url(source_url: str) -> str:
    try:
        html = fetch(source_url)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict] = []

    for a in soup.select("a[href]"):
        full = unwrap_url(urljoin(source_url, a.get("href") or ""))
        add_candidate(candidates, full, clean(a.get_text(" ", strip=True)), source_url)

    for raw in re.findall(r"https?://[^\s\"'<>]+", html):
        add_candidate(candidates, unwrap_url(raw), "", source_url)

    for tag in soup.find_all(True):
        for value in tag.attrs.values():
            if isinstance(value, list):
                value = " ".join(map(str, value))
            if not isinstance(value, str):
                continue
            for raw in re.findall(r"https?://[^\s\"'<>]+", value):
                add_candidate(candidates, unwrap_url(raw), "", source_url)

    candidates = [c for c in candidates if is_good_external(c["url"], source_url)]
    if not candidates:
        return ""
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[0]["url"]

def add_candidate(candidates: list[dict], url: str, text: str, source_url: str) -> None:
    if not url:
        return
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith("http"):
        return
    if urlparse(url).path.lower().endswith(BAD_EXT):
        return
    d = domain(url)
    score = 0
    if any(sd in d for sd in SHOP_DOMAINS):
        score += 100
    if any(w in (url + " " + text).lower() for w in ["goods", "product", "item", "deal", "shopping", "상품", "구매", "바로가기"]):
        score += 18
    if any(x in url.lower() for x in ["redirect", "link", "adcr", "lrl.kr"]):
        score += 5
    if any(bad in url.lower() for bad in ["login", "signup", "comment", "reply", "image", "thumbnail"]):
        score -= 80
    candidates.append({"url": url, "score": score})

def is_good_external(url: str, source_url: str) -> bool:
    d, sd = domain(url), domain(source_url)
    if not d or d == sd:
        return False
    if any(src in d for src in SOURCE_DOMAINS):
        return False
    if any(social in d for social in ["facebook.com", "instagram.com", "youtube.com", "twitter.com", "x.com", "kakao.com"]):
        return False
    return True

def unwrap_url(url: str) -> str:
    url = url.replace("&amp;", "&")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ["url", "u", "target", "to", "link", "redirect", "redirect_url", "returnUrl", "return_url", "r", "dest", "destination"]:
        if key in qs and qs[key]:
            inner = unquote(qs[key][0])
            if inner.startswith("http"):
                return unwrap_url(inner)
    return url

def valid_candidate(title: str, url: str) -> bool:
    if len(title) < 7 or len(title) > 190:
        return False
    if not url.startswith("http"):
        return False
    low = title.lower()
    if any(x in low for x in ["로그인", "회원가입", "공지사항", "이벤트 전체보기", "이전", "다음"]):
        return False
    signal_words = SHOP_WORDS + HOT_WORDS + FREE_WORDS + ["기저귀", "분유", "물티슈", "세제", "상품권", "ssd", "충전기"]
    return bool(extract_price(title) or any(w.lower() in low for w in signal_words))

def parent_text(a) -> str:
    p = a
    for _ in range(3):
        if p.parent:
            p = p.parent
    return p.get_text(" ", strip=True)

def extract_price(text: str) -> int:
    t = str(text).replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원?", t)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d{1,3}(?:\.\d{3})+)\s*원", str(text))
    if m:
        return int(m.group(1).replace(".", ""))
    m = re.search(r"(\d{3,9})\s*원", t)
    return int(m.group(1)) if m else 0

def extract_comments(text: str) -> int:
    for pattern in [r"댓글\s*(\d{1,4})", r"[\[(](\d{1,4})[\])]"]:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    return 0

def extract_likes(text: str) -> int:
    m = re.search(r"(추천|좋아요)\s*(\d{1,5})", text)
    return int(m.group(2)) if m else 0

def extract_views(text: str) -> int:
    m = re.search(r"(조회|조회수)\s*(\d{1,8})", text.replace(",", ""))
    return int(m.group(2)) if m else 0

def guess_shop(title: str) -> str:
    low = title.lower()
    for shop in SHOP_WORDS:
        if shop.lower() in low:
            return shop
    m = re.match(r"^\[([^\]]+)\]", title)
    return m.group(1) if m else ""

def guess_category(title: str) -> str:
    low = title.lower()
    for cat, words in CATEGORY_WORDS.items():
        if any(w.lower() in low for w in words):
            return cat
    return "생필품"

def guess_flags(title: str) -> list[str]:
    flags = []
    if any(w in title for w in FREE_WORDS):
        flags.append("무료배송")
    if any(w.lower() in title.lower() for w in END_WORDS):
        flags.append("품절" if "품절" in title else "종료")
    if any(w in title for w in HOT_WORDS):
        flags.append("인기")
    if 0 < extract_price(title) <= 10000:
        flags.append("만원 이하")
    return flags or ["신규"]

def calc_score(item: dict) -> int:
    score = 35
    score += min(28, item.get("likes", 0) * 1.2)
    score += min(18, item.get("comments", 0) * 0.6)
    score += min(12, item.get("views", 0) / 2500)
    flags = item.get("flags", [])
    if "무료배송" in flags:
        score += 5
    if any(w in item.get("title", "") for w in HOT_WORDS):
        score += 8
    if 0 < item.get("price_value", 0) <= 10000:
        score += 4
    if item.get("purchase_url"):
        score += 6
    if any(flag in ["품절", "종료"] for flag in flags):
        score -= 28
    return max(1, min(100, round(score)))

def dedupe(items: list[dict]) -> list[dict]:
    out, seen = [], set()
    for item in items:
        key = normalize(item["title"], item.get("purchase_url") or item["source_url"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda x: x.get("score", 0), reverse=True)
    return out[:240]

def normalize(title: str, url: str) -> str:
    return domain(url) + ":" + re.sub(r"\s+", "", title.lower())[:90]

def domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")

def short_domain(url: str) -> str:
    return domain(url).split(":")[0]

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]

def make_status(src: dict, status: str, count: int, purchase_count: int, msg: str) -> dict:
    return {
        "name": src["name"],
        "url": src["url"],
        "status": status,
        "count": count,
        "purchase_count": purchase_count,
        "message": msg,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
