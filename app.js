const state = {
  deals: [],
  filtered: [],
  mode: "all",
  category: "전체",
  source: "전체",
  query: "",
  sort: "score",
  price: "all",
  hideEnded: true,
  favorites: new Set(JSON.parse(localStorage.getItem("hotdealRadarFavorites") || "[]")),
  blocks: JSON.parse(localStorage.getItem("hotdealRadarBlocks") || '["중고","리퍼"]')
};

const categoryMap = {
  "전체": [],
  "식품·간식": ["식품","음식","커피","간식","음료","라면","쌀","고기","닭가슴살","과자","우유","냉동","밀키트"],
  "생필품": ["생활","세제","휴지","물티슈","청소","욕실","샴푸","치약","세정제","건전지"],
  "주방·수납": ["주방","수납","정리함","냄비","프라이팬","식기","텀블러","보관용기"],
  "육아": ["육아","기저귀","분유","이유식","아기","유아","장난감","젖병","카시트","유모차","아기띠"],
  "출산·임산부": ["출산","임산부","산모","수유","젖병","유축기","태교","신생아"],
  "반려동물": ["반려","강아지","고양이","사료","간식","배변패드","모래","펫"],
  "뷰티·건강": ["뷰티","화장품","선크림","마스크팩","영양제","건강","렌즈","향수","바디"],
  "패션": ["패션","의류","신발","패딩","옷","가방","무신사","운동화"],
  "캠핑·여행": ["캠핑","레저","텐트","의자","랜턴","여행","캐리어","숙박"],
  "IT": ["IT","PC","노트북","태블릿","SSD","충전기","케이블","마우스","키보드","게임","플스"],
  "가전": ["가전","에어컨","냉장고","청소기","로봇청소기","TV","세탁기","건조기","식기세척기"],
  "상품권·포인트": ["상품권","네이버페이","페이","쿠폰","적립","해피머니","컬쳐랜드"],
  "해외직구": ["알리","AliExpress","테무","아마존","직구","해외"]
};

const modeRules = {
  all: () => true,
  discover: () => true,
  under10000: d => d.price_value > 0 && d.price_value <= 10000,
  daily: d => hasAny(d, [...categoryMap["생필품"], ...categoryMap["식품·간식"], ...categoryMap["주방·수납"]]),
  baby: d => hasAny(d, [...categoryMap["육아"], ...categoryMap["출산·임산부"]]),
  mom: d => hasAny(d, ["맘스홀릭","맘카페","공구","공동구매","쇼핑할인","육아","출산","임산부","기저귀","분유","아기","젖병","카시트","유모차"]),
  pet: d => hasAny(d, categoryMap["반려동물"]),
  beauty: d => hasAny(d, categoryMap["뷰티·건강"]),
  tech: d => hasAny(d, [...categoryMap["IT"], ...categoryMap["가전"]]),
  ali: d => hasAny(d, ["알리","aliexpress","ali","직구","해외"])
};

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

document.addEventListener("DOMContentLoaded", async () => {
  renderCategoryChips();
  bindEvents();
  renderBlocks();
  await loadDeals();
});

async function loadDeals() {
  try {
    const response = await fetch(`./data/deals.json?ts=${Date.now()}`);
    const payload = await response.json();
    state.deals = Array.isArray(payload.deals) ? payload.deals.map(normalizeDeal) : [];
    $("#updatedAt").textContent = formatUpdatedAt(payload.generated_at);
  } catch (error) {
    console.error(error);
    state.deals = [];
    $("#updatedAt").textContent = "오류";
  }
  renderSourceChips();
  applyFilters();
}

function normalizeDeal(deal, index) {
  const id = deal.id || `${deal.source || "src"}-${deal.url || deal.title || index}`;
  const title = cleanText(deal.title || "제목 없음");
  const category = deal.category || guessCategory(title);
  const priceValue = Number(deal.price_value || extractPrice(title) || 0);
  const flags = Array.isArray(deal.flags) ? deal.flags : guessFlags(title);
  const comments = Number(deal.comments || 0);
  const likes = Number(deal.likes || 0);
  const views = Number(deal.views || 0);
  const score = Number(deal.score || calculateScore({ title, priceValue, flags, comments, likes, views, source: deal.source }));
  return {
    ...deal,
    id,
    title,
    category,
    price_value: priceValue,
    price_text: deal.price_text || (priceValue ? priceValue.toLocaleString("ko-KR") + "원" : "가격 확인"),
    shop: deal.shop || guessShop(title),
    flags,
    comments,
    likes,
    views,
    score,
    url: deal.url || "#",
    purchase_url: deal.purchase_url || deal.url || "#",
    purchase_domain: deal.purchase_domain || "",
    source: deal.source || "샘플",
    created_at: deal.created_at || new Date().toISOString()
  };
}

function bindEvents() {
  $("#searchInput").addEventListener("input", e => {
    state.query = e.target.value.trim();
    applyFilters();
  });

  $$(".mode-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      $$(".mode-tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      applyFilters();
    });
  });

  $("#sortSelect").addEventListener("change", e => {
    state.sort = e.target.value;
    applyFilters();
  });

  $("#priceSelect").addEventListener("change", e => {
    state.price = e.target.value;
    applyFilters();
  });

  $("#hideEnded").addEventListener("change", e => {
    state.hideEnded = e.target.checked;
    applyFilters();
  });

  $("#clearFilters").addEventListener("click", resetFilters);
  $("#refreshBtn").addEventListener("click", loadDeals);

  $("#blockForm").addEventListener("submit", e => {
    e.preventDefault();
    const value = $("#blockInput").value.trim();
    if (!value) return;
    if (!state.blocks.includes(value)) state.blocks.push(value);
    $("#blockInput").value = "";
    saveBlocks();
    renderBlocks();
    applyFilters();
  });
}

function resetFilters() {
  state.mode = "all";
  state.category = "전체";
  state.source = "전체";
  state.query = "";
  state.sort = "score";
  state.price = "all";
  state.hideEnded = true;

  $("#searchInput").value = "";
  $("#sortSelect").value = "score";
  $("#priceSelect").value = "all";
  $("#hideEnded").checked = true;

  $$(".mode-tab").forEach(b => b.classList.toggle("active", b.dataset.mode === "all"));
  $$(".category-chip").forEach(b => b.classList.toggle("active", b.dataset.category === "전체"));
  $$(".source-chip").forEach(b => b.classList.toggle("active", b.dataset.source === "전체"));
  applyFilters();
}

function renderCategoryChips() {
  const wrap = $("#categoryChips");
  wrap.innerHTML = "";
  Object.keys(categoryMap).forEach(category => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip category-chip" + (category === state.category ? " active" : "");
    btn.dataset.category = category;
    btn.textContent = category;
    btn.addEventListener("click", () => {
      $$(".category-chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.category = category;
      applyFilters();
    });
    wrap.appendChild(btn);
  });
}

function renderSourceChips() {
  const wrap = $("#sourceChips");
  if (!wrap) return;
  wrap.innerHTML = "";
  const sources = ["전체", ...new Set(state.deals.map(d => d.source).filter(Boolean))];
  sources.forEach(source => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip source-chip" + (source === state.source ? " active" : "");
    btn.dataset.source = source;
    btn.textContent = source;
    btn.addEventListener("click", () => {
      $$(".source-chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.source = source;
      applyFilters();
    });
    wrap.appendChild(btn);
  });
}

function applyFilters() {
  const query = state.query.toLowerCase();
  let deals = state.deals.filter(deal => {
    const text = `${deal.title} ${deal.category} ${deal.shop} ${deal.source}`.toLowerCase();

    if (query && !text.includes(query)) return false;
    if (state.hideEnded && deal.flags.some(f => ["종료","품절"].includes(f))) return false;
    if (state.blocks.some(word => text.includes(String(word).toLowerCase()))) return false;
    if (!modeRules[state.mode](deal)) return false;
    if (state.category !== "전체" && !hasAny(deal, categoryMap[state.category])) return false;
    if (state.source !== "전체" && deal.source !== state.source) return false;

    if (state.price === "under10000" && !(deal.price_value > 0 && deal.price_value <= 10000)) return false;
    if (state.price === "under30000" && !(deal.price_value > 0 && deal.price_value <= 30000)) return false;
    if (state.price === "under100000" && !(deal.price_value > 0 && deal.price_value <= 100000)) return false;
    if (state.price === "over100000" && !(deal.price_value >= 100000)) return false;

    return true;
  });

  deals = sortDeals(deals);
  state.filtered = deals;

  renderSummary();
  renderDeals();
}

function sortDeals(deals) {
  const copy = [...deals];
  if (state.sort === "new") {
    copy.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
  } else if (state.sort === "priceLow") {
    copy.sort((a,b) => (a.price_value || 999999999) - (b.price_value || 999999999));
  } else if (state.sort === "random" || state.mode === "discover") {
    copy.sort((a,b) => seededRandom(a.id) - seededRandom(b.id));
  } else {
    copy.sort((a,b) => b.score - a.score);
  }
  return copy;
}

function renderSummary() {
  $("#totalCount").textContent = state.deals.length.toLocaleString("ko-KR");
  $("#hotCount").textContent = state.deals.filter(d => d.score >= 70).length.toLocaleString("ko-KR");
  $("#underTenCount").textContent = state.deals.filter(d => d.price_value > 0 && d.price_value <= 10000).length.toLocaleString("ko-KR");
  $("#resultCount").textContent = `${state.filtered.length.toLocaleString("ko-KR")}개 딜`;
  const hints = {
    all: "전체 핫딜을 레이더 점수 기준으로 보여드려요.",
    discover: "인기순만 보지 않고 카테고리를 섞어 보여드려요.",
    under10000: "가볍게 줍기 좋은 만원 이하 딜만 모았어요.",
    daily: "생필품·식품처럼 생활비 절약에 가까운 딜을 모았어요.",
    baby: "육아용품과 출산 관련 딜을 모았어요.",
    mom: "맘카페에서 자주 찾는 육아·생활형 딜 위주로 보여드려요.",
    pet: "반려동물 사료·간식·소모품 딜을 모았어요.",
    beauty: "뷰티·건강 카테고리 딜을 모았어요.",
    tech: "IT·가전·주변기기 쪽 딜을 모았어요.",
    ali: "알리·해외 소품 탐험용 딜을 모았어요."
  };
  $("#resultHint").textContent = hints[state.mode] || hints.all;
}

function renderDeals() {
  const list = $("#dealList");
  const empty = $("#emptyState");
  list.innerHTML = "";

  if (!state.filtered.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  const tpl = $("#dealCardTemplate");
  state.filtered.slice(0, 120).forEach(deal => {
    const node = tpl.content.firstElementChild.cloneNode(true);

    node.querySelector(".deal-source").textContent = deal.source;
    node.querySelector(".deal-category").textContent = deal.category;
    node.querySelector(".deal-title").textContent = deal.title;
    node.querySelector(".deal-price").textContent = deal.price_text;
    node.querySelector(".deal-shop").textContent = deal.shop ? `· ${deal.shop}` : "";
    node.querySelector(".deal-time").textContent = `· ${relativeTime(deal.created_at)}`;
    node.querySelector(".deal-score").textContent = Math.round(deal.score);
    node.querySelector(".score-bar i").style.width = `${Math.min(100, Math.max(0, deal.score))}%`;

    const favoriteBtn = node.querySelector(".favorite-btn");
    favoriteBtn.classList.toggle("active", state.favorites.has(deal.id));
    favoriteBtn.textContent = state.favorites.has(deal.id) ? "♥" : "♡";
    favoriteBtn.addEventListener("click", () => toggleFavorite(deal.id));

    const flagsWrap = node.querySelector(".deal-flags");
    deal.flags.forEach(flag => {
      const span = document.createElement("span");
      span.className = "flag";
      if (["인기","급상승","맘카페픽"].includes(flag)) span.classList.add("hot");
      if (["종료","품절"].includes(flag)) span.classList.add("end");
      if (["무료배송","무료"].includes(flag)) span.classList.add("free");
      span.textContent = flag;
      flagsWrap.appendChild(span);
    });

    const purchaseLink = node.querySelector(".primary-link");
    purchaseLink.href = deal.purchase_url || deal.url;
    purchaseLink.textContent = deal.purchase_url && deal.purchase_url !== deal.url ? "구매처 바로가기" : "원문 보기";

    const sourceLink = node.querySelector(".source-link");
    sourceLink.href = deal.url;
    sourceLink.textContent = "원문";

    node.querySelector(".copy-btn").addEventListener("click", async () => {
      await navigator.clipboard.writeText(deal.purchase_url || deal.url);
      const btn = node.querySelector(".copy-btn");
      btn.textContent = "복사됨";
      setTimeout(() => btn.textContent = "복사", 1200);
    });

    list.appendChild(node);
  });
}

function toggleFavorite(id) {
  if (state.favorites.has(id)) state.favorites.delete(id);
  else state.favorites.add(id);
  localStorage.setItem("hotdealRadarFavorites", JSON.stringify([...state.favorites]));
  renderDeals();
}

function renderBlocks() {
  const list = $("#blockList");
  list.innerHTML = "";
  state.blocks.forEach((word, index) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "block-tag";
    btn.textContent = `${word} ×`;
    btn.addEventListener("click", () => {
      state.blocks.splice(index, 1);
      saveBlocks();
      renderBlocks();
      applyFilters();
    });
    list.appendChild(btn);
  });
}

function saveBlocks() {
  localStorage.setItem("hotdealRadarBlocks", JSON.stringify(state.blocks));
}

function hasAny(deal, words) {
  const text = `${deal.title} ${deal.category} ${deal.shop} ${deal.source}`.toLowerCase();
  return words.some(w => text.includes(String(w).toLowerCase()));
}

function guessCategory(title) {
  for (const [category, words] of Object.entries(categoryMap)) {
    if (category === "전체") continue;
    if (words.some(word => title.toLowerCase().includes(word.toLowerCase()))) return category;
  }
  return "생필품";
}

function guessShop(title) {
  const shops = ["쿠팡","네이버","네이버페이","지마켓","G마켓","옥션","11번가","롯데온","홈플러스","이마트","알리","AliExpress","SSG","티몬","위메프","무신사","컬리","올리브영","다이소","테무","아마존"];
  return shops.find(shop => title.toLowerCase().includes(shop.toLowerCase())) || "";
}

function guessFlags(title) {
  const flags = [];
  if (/무료배송|무배|무료/.test(title)) flags.push("무료배송");
  if (/품절|종료|마감/.test(title)) flags.push(title.includes("품절") ? "품절" : "종료");
  if (/역대가|핫딜|특가|체감가|빅세일/.test(title)) flags.push("인기");
  if (/맘스홀릭|맘카페|공구|공동구매/.test(title)) flags.push("맘카페픽");
  return flags.length ? flags : ["신규"];
}

function calculateScore({ title, priceValue, flags, comments, likes, views, source }) {
  let score = 35;
  score += Math.min(28, likes * 1.2);
  score += Math.min(18, comments * 0.6);
  score += Math.min(12, views / 2500);
  if (flags?.includes("무료배송")) score += 5;
  if (flags?.includes("맘카페픽")) score += 5;
  if (/역대가|체감가|특가|핫딜|쿠폰|무료/.test(title)) score += 8;
  if (priceValue > 0 && priceValue <= 10000) score += 4;
  if (flags?.some(f => ["종료","품절"].includes(f))) score -= 28;
  return Math.max(1, Math.min(100, Math.round(score)));
}

function extractPrice(text) {
  const normalized = text.replace(/,/g, "");
  const man = normalized.match(/(\d+(?:\.\d+)?)\s*만\s*원?/);
  if (man) return Math.round(Number(man[1]) * 10000);
  const won = normalized.match(/(\d{1,9})\s*원/);
  if (won) return Number(won[1]);
  return 0;
}

function cleanText(text) {
  return String(text).replace(/\s+/g, " ").trim();
}

function relativeTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "시간 확인";
  const diff = Date.now() - date.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return "방금 전";
  if (min < 60) return `${min}분 전`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}시간 전`;
  const day = Math.floor(hour / 24);
  if (day < 7) return `${day}일 전`;
  return date.toLocaleDateString("ko-KR", { month:"short", day:"numeric" });
}

function formatUpdatedAt(value) {
  if (!value) return "샘플";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "샘플";
  return date.toLocaleString("ko-KR", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
}

function seededRandom(seed) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
  }
  return (h >>> 0) / 4294967295;
}
