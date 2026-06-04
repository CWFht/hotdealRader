#!/usr/bin/env python3
"""
Hotdeal Radar crawler

주의:
- 공개 게시글 목록에서 제목/링크/날짜/반응 정보 정도만 수집합니다.
- 로그인, CAPTCHA, 차단 우회, 과도한 요청은 하지 않습니다.
- 각 사이트의 robots.txt와 이용약관을 확인한 뒤 사용하세요.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "deals.json"

USER_AGENT = os.environ.get(
    "HOTDEAL_RADAR_UA",
    "HotdealRadar/0.1 (+personal-use; respectful-crawler)"
)
REQUEST_DELAY_SECONDS = float(os.environ.get("HOTDEAL_RADAR_DELAY", "1.5"))
MAX_PER_SOURCE = int(os.environ.get("HOTDEAL_RADAR_MAX_PER_SOURCE", "35"))

SOURCES = [
    {
        "name": "루리웹",
        "url": "https://bbs.ruliweb.com/market/board/1020",
        "base": "https://bbs.ruliweb.com",
        "enabled": True,
    },
    {
        "name": "뽐뿌",
        "url": "https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu",
        "base": "https://www.ppomppu.co.kr",
        "enabled": True,
    },
    {
        "name": "퀘이사존",
        "url": "https://quasarzone.com/bbs/qb_saleinfo",
        "base": "https://quasarzone.com",
        "enabled": True,
    },
    {
        "name": "에펨코리아",
        "url": "https://www.fmkorea.com/hotdeal",
        "base": "https://www.fmkorea.com",
        "enabled": True,
    },
]

SHOP_WORDS = [
    "쿠팡", "네이버", "네이버페이", "지마켓", "G마켓", "옥션", "11번가", "롯데온", "홈플러스", "이마트",
    "알리", "AliExpress", "SSG", "티몬", "위메프", "무신사", "컬리", "하이마트", "스팀", "PSN"
]

CATEGORY_WORDS = {
    "식품": ["식품", "음식", "커피", "간식", "음료", "라면", "쌀", "고기", "닭가슴살", "아몬드브리즈", "컵라면"],
    "생활": ["생활", "세제", "휴지", "물티슈", "청소", "수납", "욕실", "주방", "정리함"],
    "육아": ["육아", "기저귀", "분유", "이유식", "아기", "유아", "장난감", "물티슈"],
    "IT": ["IT", "PC", "노트북", "태블릿", "SSD", "충전기", "케이블", "마우스", "키보드", "게임", "플스", "스팀"],
    "가전": ["가전", "에어컨", "냉장고", "청소기", "로봇청소기", "TV", "세탁기", "건조기"],
    "패션": ["패션", "의류", "신발", "패딩", "티셔츠", "가방", "무신사"],
    "캠핑": ["캠핑", "레저", "텐트", "의자", "랜턴"],
    "상품권": ["상품권", "네이버페이", "페이", "쿠폰", "적립"],
}

END_WORDS = ["품절", "종료", "마감", "sold out"]
FREE_SHIPPING_WORDS = ["무료배송", "무배", "배송비무료"]
HOT_WORDS = ["역대가", "핫딜", "특가", "체감가", "빅세일", "대란", "무료"]


@dataclass
class Deal:
    title: str
    url: str
    source: str
    shop: str = ""
    category: str = "생활"
    price_text: str = "가격 확인"
    price_value: int = 0
    comments: int = 0
    likes: int = 0
    views: int = 0
    flags: list[str] | None = None
    created_at: str = ""

    def to_dict(self) -> dict:
        raw = {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "shop": self.shop,
            "category": self.category,
        }
        stable = hashlib.sha1(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        return {
            "id": stable,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "shop": self.shop,
            "category": self.category,
            "price_text": self.price_text,
            "price_value": self.price_value,
            "comments": self.comments,
            "likes": self.likes,
            "views": self.views,
            "flags": self.flags or ["신규"],
            "score": calculate_score(self),
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
        }


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    all_deals: list[Deal] = []

    for source in SOURCES:
        if not source.get("enabled"):
            continue
        try:
            print(f"Collecting: {source['name']} {source['url']}")
            html = fetch(source["url"])
            deals = parse_listing(html, source)
            print(f"  found {len(deals)} candidates")
            all_deals.extend(deals[:MAX_PER_SOURCE])
        except Exception as exc:
            print(f"  failed: {source['name']}: {exc}")
        time.sleep(REQUEST_DELAY_SECONDS + random.random())

    deduped = dedupe(all_deals)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(deduped),
        "deals": [deal.to_dict() for deal in deduped],
    }

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(deduped)} deals to {OUTPUT}")


def fetch(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
    }
    res = requests.get(url, headers=headers, timeout=18)
    res.raise_for_status()
    if not res.encoding or res.encoding.lower() == "iso-8859-1":
        res.encoding = res.apparent_encoding
    return res.text


def parse_listing(html: str, source: dict) -> list[Deal]:
    soup = BeautifulSoup(html, "html.parser")
    base = source.get("base") or source["url"]
    source_name = source["name"]

    # 게시판 목록은 구조가 자주 바뀌므로, 링크 중심의 휴리스틱으로 후보를 골라냅니다.
    anchors = soup.select("a[href]")
    deals: list[Deal] = []
    seen = set()

    for a in anchors:
        title = clean(a.get_text(" ", strip=True))
        href = a.get("href", "")
        url = urljoin(base, href)

        if not is_valid_candidate(title, url, source_name):
            continue

        key = normalize_key(title, url)
        if key in seen:
            continue
        seen.add(key)

        context = clean(parent_text(a))
        comments = extract_comments(title + " " + context)
        likes = extract_likes(context)
        views = extract_views(context)
        price_value = extract_price(title)
        price_text = f"{price_value:,}원" if price_value else "가격 확인"

        deals.append(
            Deal(
                title=title,
                url=url,
                source=source_name,
                shop=guess_shop(title),
                category=guess_category(title),
                price_text=price_text,
                price_value=price_value,
                comments=comments,
                likes=likes,
                views=views,
                flags=guess_flags(title),
                created_at=guess_datetime(context),
            )
        )

    return deals


def is_valid_candidate(title: str, url: str, source_name: str) -> bool:
    if len(title) < 8 or len(title) > 180:
        return False
    if "공지" in title and len(title) < 35:
        return False
    if not url.startswith("http"):
        return False

    parsed = urlparse(url)
    if not parsed.netloc:
        return False

    # 실제 핫딜 제목에는 쇼핑몰명, 가격, 무료/특가 표현 중 하나가 들어가는 경우가 많음
    has_signal = (
        any(word.lower() in title.lower() for word in SHOP_WORDS)
        or extract_price(title) > 0
        or any(word in title for word in HOT_WORDS + FREE_SHIPPING_WORDS)
    )
    if not has_signal:
        return False

    return True


def parent_text(anchor) -> str:
    parent = anchor
    for _ in range(4):
        if parent.parent:
            parent = parent.parent
    return parent.get_text(" ", strip=True)


def dedupe(deals: Iterable[Deal]) -> list[Deal]:
    out = []
    seen = set()
    for deal in deals:
        key = normalize_key(deal.title, deal.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(deal)

    out.sort(key=lambda d: calculate_score(d), reverse=True)
    return out[:180]


def normalize_key(title: str, url: str) -> str:
    # 제목에 붙는 댓글 수나 괄호 일부를 제거해 중복 가능성을 줄임
    t = re.sub(r"\(\d+\)", "", title)
    t = re.sub(r"\s+", "", t).lower()
    domain = urlparse(url).netloc
    return f"{domain}:{t[:80]}"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_price(text: str) -> int:
    normalized = text.replace(",", "")
    man = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원?", normalized)
    if man:
        return int(float(man.group(1)) * 10000)

    # 4,900원 / 14130원 / 969.570원 같은 표기도 일부 보정
    dot_price = re.search(r"(\d{1,3}(?:\.\d{3})+)\s*원", text)
    if dot_price:
        return int(dot_price.group(1).replace(".", ""))

    won = re.search(r"(\d{1,9})\s*원", normalized)
    if won:
        value = int(won.group(1))
        # 너무 작은 적립금은 가격으로 보지 않음
        if value >= 100:
            return value
    return 0


def extract_comments(text: str) -> int:
    patterns = [r"\((\d{1,4})\)", r"댓글\s*(\d{1,4})"]
    for p in patterns:
        m = re.search(p, text)
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
    lower = title.lower()
    for shop in SHOP_WORDS:
        if shop.lower() in lower:
            return shop
    bracket = re.match(r"^\[([^\]]+)\]", title)
    return bracket.group(1) if bracket else ""


def guess_category(title: str) -> str:
    lower = title.lower()
    for category, words in CATEGORY_WORDS.items():
        if any(word.lower() in lower for word in words):
            return category
    return "생활"


def guess_flags(title: str) -> list[str]:
    flags = []
    if any(word in title for word in FREE_SHIPPING_WORDS):
        flags.append("무료배송")
    if any(word.lower() in title.lower() for word in END_WORDS):
        flags.append("품절" if "품절" in title else "종료")
    if any(word in title for word in HOT_WORDS):
        flags.append("인기")
    if extract_price(title) and extract_price(title) <= 10000:
        flags.append("만원 이하")
    return flags or ["신규"]


def guess_datetime(context: str) -> str:
    # 게시판마다 시간 표기가 달라 정확도가 낮기 때문에 모르면 현재 시각을 사용
    now = datetime.now(timezone.utc)

    hhmm = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", context)
    if hhmm:
        return now.replace(hour=int(hhmm.group(1)), minute=int(hhmm.group(2)), second=0, microsecond=0).isoformat()

    ymd = re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", context)
    if ymd:
        return datetime(int(ymd.group(1)), int(ymd.group(2)), int(ymd.group(3)), tzinfo=timezone.utc).isoformat()

    return now.isoformat()


def calculate_score(deal: Deal) -> int:
    score = 35
    score += min(28, deal.likes * 1.2)
    score += min(18, deal.comments * 0.6)
    score += min(12, deal.views / 2500)
    if deal.flags and "무료배송" in deal.flags:
        score += 5
    if any(word in deal.title for word in HOT_WORDS):
        score += 8
    if 0 < deal.price_value <= 10000:
        score += 4
    if deal.flags and any(flag in ["품절", "종료"] for flag in deal.flags):
        score -= 28
    return max(1, min(100, round(score)))


if __name__ == "__main__":
    main()
