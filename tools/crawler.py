#!/usr/bin/env python3
"""
Hotdeal Radar crawler v1.4

핵심 변경:
- 목록에서 핫딜 원문 URL을 찾은 뒤, 원문 상세 페이지를 한 번 더 열어 실제 쇼핑몰/구매처 링크를 추출합니다.
- 화면에서는 purchase_url을 우선으로 '구매처 바로가기'를 표시하고, 원문은 보조 버튼으로 남깁니다.

주의:
- 공개 게시글만 수집합니다.
- 로그인, CAPTCHA, 차단 우회, 과도한 요청은 하지 않습니다.
- 원문 전체를 복제하지 않고 제목/가격/링크/반응 정도만 저장합니다.
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
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "deals.json"
SOURCES_OUTPUT = DATA_DIR / "sources.json"

USER_AGENT = os.environ.get(
    "HOTDEAL_RADAR_UA",
    "Mozilla/5.0 (compatible; HotdealRadar/1.4; personal-use)"
)
REQUEST_DELAY_SECONDS = float(os.environ.get("HOTDEAL_RADAR_DELAY", "1.6"))
MAX_PER_SOURCE = int(os.environ.get("HOTDEAL_RADAR_MAX_PER_SOURCE", "35"))
DETAIL_LINK_LIMIT = int(os.environ.get("HOTDEAL_RADAR_DETAIL_LIMIT", "80"))
ENABLE_DETAIL_LINKS = os.environ.get("HOTDEAL_RADAR_DETAIL_LINKS", "true").lower() == "true"

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
    # 네이버 카페는 로그인/권한/게시판 정책 때문에 기본값을 False로 둡니다.
    {
        "name": "맘스홀릭",
        "url": "https://cafe.naver.com/imsanbu",
        "base": "https://cafe.naver.com",
        "enabled": False,
    },
]

SHOP_WORDS = [
    "쿠팡", "네이버", "네이버페이", "지마켓", "G마켓", "옥션", "11번가", "롯데온", "홈플러스", "이마트",
    "알리", "AliExpress", "SSG", "티몬", "위메프", "무신사", "컬리", "하이마트", "스팀", "PSN",
    "올리브영", "다이소", "테무", "아마존", "코스트코", "트레이더스"
]

SHOPPING_DOMAINS = [
    "coupang.com", "naver.com", "smartstore.naver.com", "shopping.naver.com", "gmarket.co.kr", "auction.co.kr",
    "11st.co.kr", "lotteon.com", "ssg.com", "emart.com", "homeplus.co.kr", "aliexpress.com", "temu.com",
    "amazon.com", "musinsa.com", "oliveyoung.co.kr", "kurly.com", "hmall.com", "interpark.com", "tmon.co.kr",
    "wemakeprice.com", "lotteimall.com", "costco.co.kr", "danawa.com", "store.steampowered.com", "playstation.com"
]

CATEGORY_WORDS = {
    "식품·간식": ["식품", "음식", "커피", "간식", "음료", "라면", "쌀", "고기", "닭가슴살", "아몬드브리즈", "컵라면", "과자", "우유", "밀키트", "냉동"],
    "생필품": ["생활", "세제", "휴지", "물티슈", "청소", "욕실", "샴푸", "치약", "세정제", "건전지"],
    "주방·수납": ["주방", "수납", "정리함", "냄비", "프라이팬", "식기", "텀블러", "보관용기"],
    "육아": ["육아", "기저귀", "분유", "이유식", "아기", "유아", "장난감", "젖병", "카시트", "유모차", "아기띠"],
    "출산·임산부": ["출산", "임산부", "산모", "수유", "젖병", "유축기", "태교", "신생아"],
    "반려동물": ["반려", "강아지", "고양이", "사료", "간식", "배변패드", "모래", "펫"],
    "뷰티·건강": ["뷰티", "화장품", "선크림", "마스크팩", "영양제", "건강", "렌즈", "향수", "바디"],
    "패션": ["패션", "의류", "신발", "패딩", "티셔츠", "가방", "무신사", "운동화"],
    "캠핑·여행": ["캠핑", "레저", "텐트", "의자", "랜턴", "여행", "캐리어", "숙박"],
    "IT": ["IT", "PC", "노트북", "태블릿", "SSD", "충전기", "케이블", "마우스", "키보드", "게임", "플스", "스팀"],
    "가전": ["가전", "에어컨", "냉장고", "청소기", "로봇청소기", "TV", "세탁기", "건조기", "식기세척기"],
    "상품권·포인트": ["상품권", "네이버페이", "페이", "쿠폰", "적립", "해피머니", "컬쳐랜드"],
    "해외직구": ["알리", "AliExpress", "테무", "아마존", "직구", "해외"],
}

END_WORDS = ["품절", "종료", "마감", "sold out"]
FREE_SHIPPING_WORDS = ["무료배송", "무배", "배송비무료", "무료 배송"]
HOT_WORDS = ["역대가", "핫딜", "특가", "체감가", "빅세일", "대란", "무료", "쿠폰"]

BAD_LINK_KEYWORDS = [
    "login", "logout", "signup", "member", "comment", "javascript:", "mailto:", "tel:", "#",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "kakao.com",
    "policy", "privacy", "notice", "help", "customer", "cs"
]

@dataclass
class Deal:
    title: str
    url: str
    source: str
    shop: str = ""
    category: str = "생필품"
    price_text: str = "가격 확인"
    price_value: int = 0
    comments: int = 0
    likes: int = 0
    views: int = 0
    flags: list[str] | None = None
    created_at: str = ""
    purchase_url: str = ""
    purchase_domain: str = ""

    def to_dict(self) -> dict:
        stable = hashlib.sha1(f"{self.source}|{self.title}|{self.url}".encode("utf-8")).hexdigest()[:16]
        return {
            "id": stable,
            "title": self.title,
            "url": self.url,
            "purchase_url": self.purchase_url or self.url,
            "purchase_domain": self.purchase_domain or domain_of(self.purchase_url or self.url),
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
    source_status: list[dict] = []
    detail_count = 0

    for source in SOURCES:
        if not source.get("enabled"):
            source_status.append(status(source, "disabled", 0, "기본 비활성화"))
            continue

        try:
            print(f"Collecting: {source['name']} {source['url']}", flush=True)
            html = fetch(source["url"])
            deals = parse_listing(html, source)[:MAX_PER_SOURCE]

            if ENABLE_DETAIL_LINKS:
                for deal in deals:
                    if detail_count >= DETAIL_LINK_LIMIT:
                        break
                    try:
                        purchase_url = extract_purchase_url_from_post(deal.url, source)
                        if purchase_url:
                            deal.purchase_url = purchase_url
                            deal.purchase_domain = domain_of(purchase_url)
                            if not deal.shop:
                                deal.shop = guess_shop_from_url(purchase_url)
                        else:
                            deal.purchase_url = deal.url
                            deal.purchase_domain = domain_of(deal.url)
                    except Exception as exc:
                        print(f"  detail link failed: {deal.url} / {type(exc).__name__}: {exc}", flush=True)
                        deal.purchase_url = deal.url
                        deal.purchase_domain = domain_of(deal.url)
                    detail_count += 1
                    time.sleep(0.35 + random.random() * 0.35)
            else:
                for deal in deals:
                    deal.purchase_url = deal.url
                    deal.purchase_domain = domain_of(deal.url)

            all_deals.extend(deals)
            source_status.append(status(source, "ok" if deals else "empty", len(deals), "수집 완료" if deals else "후보 없음"))
            print(f"  found {len(deals)} deals", flush=True)
        except Exception as exc:
            source_status.append(status(source, "failed", 0, f"{type(exc).__name__}: {str(exc)[:160]}"))
            print(f"  failed: {source['name']}: {type(exc).__name__}: {exc}", flush=True)

        time.sleep(REQUEST_DELAY_SECONDS + random.random())

    deduped = dedupe(all_deals)
    generated_at = datetime.now(timezone.utc).isoformat()
    deals_payload = {"generated_at": generated_at, "count": len(deduped), "deals": [d.to_dict() for d in deduped]}
    sources_payload = {"generated_at": generated_at, "sources": source_status}

    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(deals_payload, f, ensure_ascii=False, indent=2)
    with SOURCES_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(sources_payload, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(deduped)} deals to {OUTPUT}", flush=True)


def status(source: dict, status_value: str, count: int, message: str) -> dict:
    return {
        "name": source["name"],
        "url": source["url"],
        "status": status_value,
        "count": count,
        "message": message,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()
    if not res.encoding or res.encoding.lower() == "iso-8859-1":
        res.encoding = res.apparent_encoding
    return res.text


def parse_listing(html: str, source: dict) -> list[Deal]:
    soup = BeautifulSoup(html, "html.parser")
    base = source.get("base") or source["url"]
    source_name = source["name"]
    deals: list[Deal] = []
    seen = set()

    for a in soup.select("a[href]"):
        title = clean(a.get_text(" ", strip=True))
        url = urljoin(base, a.get("href", ""))
        if not is_valid_candidate(title, url):
            continue
        key = normalize_key(title, url)
        if key in seen:
            continue
        seen.add(key)

        context = clean(parent_text(a))
        price_value = extract_price(title)
        deals.append(Deal(
            title=title,
            url=url,
            source=source_name,
            shop=guess_shop(title),
            category=guess_category(title),
            price_text=f"{price_value:,}원" if price_value else "가격 확인",
            price_value=price_value,
            comments=extract_comments(title + " " + context),
            likes=extract_likes(context),
            views=extract_views(context),
            flags=guess_flags(title, source_name),
            created_at=guess_datetime(context),
        ))
    return deals


def extract_purchase_url_from_post(post_url: str, source: dict) -> str:
    html = fetch(post_url)
    soup = BeautifulSoup(html, "html.parser")
    base = source.get("base") or post_url
    source_domain = urlparse(base).netloc.replace("www.", "")
    candidates: list[tuple[int, str]] = []

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        text = clean(a.get_text(" ", strip=True))
        resolved = unwrap_url(urljoin(post_url, href))
        if not is_good_purchase_link(resolved, source_domain):
            continue

        score = 0
        domain = domain_of(resolved)
        lower = (resolved + " " + text).lower()
        if any(d in domain for d in SHOPPING_DOMAINS):
            score += 70
        if any(word.lower() in lower for word in ["구매", "구입", "바로가기", "링크", "상품", "딜", "coupon", "item", "product", "goods"]):
            score += 18
        if any(shop.lower() in lower for shop in SHOP_WORDS):
            score += 12
        if "redirect" in lower or "link" in lower:
            score += 3
        candidates.append((score, resolved))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def unwrap_url(url: str) -> str:
    # 게시판이 외부 링크를 redirect 파라미터로 감싸는 경우를 풀어냅니다.
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ["url", "u", "target", "redirect", "redirect_url", "link", "to", "r"]:
        if key in qs and qs[key]:
            candidate = unquote(qs[key][0])
            if candidate.startswith("http"):
                return candidate
    return url


def is_good_purchase_link(url: str, source_domain: str) -> bool:
    if not url.startswith("http"):
        return False
    lower = url.lower()
    if any(bad in lower for bad in BAD_LINK_KEYWORDS):
        return False
    domain = domain_of(url).replace("www.", "")
    if not domain or source_domain in domain or domain in source_domain:
        return False
    # 쇼핑몰 도메인은 우선 통과, 아니면 너무 일반적인 소셜/광고/첨부 링크는 제외
    if any(shop_domain in domain for shop_domain in SHOPPING_DOMAINS):
        return True
    if any(word in lower for word in ["product", "goods", "item", "deal", "coupon", "shop", "mall", "smartstore"]):
        return True
    return False


def is_valid_candidate(title: str, url: str) -> bool:
    if len(title) < 7 or len(title) > 180:
        return False
    if title in {"이전", "다음", "목록", "댓글", "추천", "비추천", "스크랩"}:
        return False
    if "공지" in title and len(title) < 35:
        return False
    if not url.startswith("http"):
        return False
    lower_url = url.lower()
    if any(x in lower_url for x in ["login", "signup", "member", "comment", "javascript:"]):
        return False
    return any(word.lower() in title.lower() for word in SHOP_WORDS) or extract_price(title) > 0 or any(word in title for word in HOT_WORDS + FREE_SHIPPING_WORDS)


def parent_text(anchor) -> str:
    parent = anchor
    for _ in range(3):
        if parent.parent:
            parent = parent.parent
    return parent.get_text(" ", strip=True)


def dedupe(deals: Iterable[Deal]) -> list[Deal]:
    out: list[Deal] = []
    seen = set()
    for deal in deals:
        key = normalize_key(deal.title, deal.purchase_url or deal.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(deal)
    out.sort(key=lambda d: calculate_score(d), reverse=True)
    return out[:220]


def normalize_key(title: str, url: str) -> str:
    t = re.sub(r"\(\d+\)", "", title)
    t = re.sub(r"\[[^\]]{1,12}\]", "", t)
    t = re.sub(r"\s+", "", t).lower()
    return f"{domain_of(url)}:{t[:90]}"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def extract_price(text: str) -> int:
    normalized = text.replace(",", "")
    man = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원?", normalized)
    if man:
        return int(float(man.group(1)) * 10000)
    dot_price = re.search(r"(\d{1,3}(?:\.\d{3})+)\s*원", text)
    if dot_price:
        return int(dot_price.group(1).replace(".", ""))
    won = re.search(r"(\d{3,9})\s*원", normalized)
    if won:
        value = int(won.group(1))
        if value >= 100:
            return value
    return 0


def extract_comments(text: str) -> int:
    for pattern in [r"\((\d{1,4})\)", r"댓글\s*(\d{1,4})", r"\[(\d{1,4})\]"]:
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
    lower = title.lower()
    for shop in SHOP_WORDS:
        if shop.lower() in lower:
            return shop
    bracket = re.match(r"^\[([^\]]+)\]", title)
    return bracket.group(1) if bracket else ""


def guess_shop_from_url(url: str) -> str:
    domain = domain_of(url)
    mapping = {
        "coupang": "쿠팡", "smartstore": "네이버", "shopping.naver": "네이버", "gmarket": "G마켓",
        "auction": "옥션", "11st": "11번가", "lotteon": "롯데온", "ssg": "SSG", "aliexpress": "알리",
        "temu": "테무", "amazon": "아마존", "musinsa": "무신사", "oliveyoung": "올리브영", "kurly": "컬리"
    }
    for key, value in mapping.items():
        if key in domain:
            return value
    return domain


def guess_category(title: str) -> str:
    lower = title.lower()
    for category, words in CATEGORY_WORDS.items():
        if any(word.lower() in lower for word in words):
            return category
    return "생필품"


def guess_flags(title: str, source_name: str = "") -> list[str]:
    flags: list[str] = []
    if any(word in title for word in FREE_SHIPPING_WORDS):
        flags.append("무료배송")
    if any(word.lower() in title.lower() for word in END_WORDS):
        flags.append("품절" if "품절" in title else "종료")
    if any(word in title for word in HOT_WORDS):
        flags.append("인기")
    if "맘" in source_name or re.search(r"맘스홀릭|맘카페|공구|공동구매", title):
        flags.append("맘카페픽")
    if extract_price(title) and extract_price(title) <= 10000:
        flags.append("만원 이하")
    return flags or ["신규"]


def guess_datetime(context: str) -> str:
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
    if deal.flags and "맘카페픽" in deal.flags:
        score += 5
    if any(word in deal.title for word in HOT_WORDS):
        score += 8
    if 0 < deal.price_value <= 10000:
        score += 4
    if deal.purchase_url and deal.purchase_url != deal.url:
        score += 3
    if deal.flags and any(flag in ["품절", "종료"] for flag in deal.flags):
        score -= 28
    return max(1, min(100, round(score)))


if __name__ == "__main__":
    main()
