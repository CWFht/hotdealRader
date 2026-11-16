# 핫딜 레이더 v1.8

## 이번 버전 핵심

- 30분 자동 갱신: `.github/workflows/update-deals.yml`에 `cron: "7,37 * * * *"` 반영
- 수동 재수집: 화면 상단 `재수집` 버튼으로 GitHub Actions 화면 이동
- 구매처 바로가기 우선: 원문 상세 페이지 안의 외부 쇼핑몰 링크를 `purchase_url`로 저장
- 다양한 수집처 시도: 루리웹, 뽐뿌, 뽐뿌_해외, 퀘이사존, 에펨코리아, 클리앙_알뜰구매, 딜바다
- 수집처 상태 표시: 각 수집처의 성공/실패/0건/구매처 링크 수를 `data/sources.json`으로 표시

## 업로드 핵심

GitHub 웹에서 `.github` 폴더가 안 보이거나 업로드가 꼬이면, 아래 파일명을 `Create new file`에 직접 입력하세요.

`.github/workflows/update-deals.yml`

내용은 `_workflow_update-deals.yml_복사용.txt`에도 똑같이 넣어두었습니다.

## 테스트 순서

1. 파일 업로드 후 Commit
2. Actions 탭에서 `Update hotdeal data` 확인
3. `Run workflow` 실행
4. 실행 완료 후 `data/deals.json`, `data/sources.json`의 시간이 바뀌었는지 확인
5. GitHub Pages 화면에서 새로고침 버튼 클릭


## v1.8 긴급 수정

- `index.html`에서 `styles.css?v=1.8.0`, `app.js?v=1.8.0`로 불러오도록 변경하여 GitHub Pages/브라우저 캐시 문제를 줄였습니다.
- 117개 수집 후 카드가 보이지 않는 상황을 대비해 카드 렌더링 예외 처리를 추가했습니다.
- 뽐뿌 상세글 링크가 `view.php` 형태일 때 `/zboard/view.php`로 정확히 연결되도록 수정했습니다.
- 구매처 링크 탐색 범위를 60개 상세글까지 확대했습니다.
- 원문 목록 링크 자체가 외부 쇼핑몰 링크인 경우 바로 `purchase_url`로 저장합니다.

## 네이버 블로그 오토파일럿 (Claude 스킬)

`.claude/skills/naver-blog-autopilot/`에 블로그 글 자동 작성 스킬이 있습니다. 핫딜 레이더와는 별개로 동작합니다.

- 주제 하나를 받으면 키워드 설계 → 원고 → 이미지 → 검수 → 스마트에디터 붙여넣기 파일까지 만듭니다.
- 블로그별 설정은 `profiles/`에, 공통 규칙(네이버 SEO, 수익 설계, 사람 글 문체, 브랜드커넥트, 이미지)은 `references/`에 있습니다.
- 결과물은 `posts/`에 생기며 `.gitignore`로 커밋에서 빠집니다.
