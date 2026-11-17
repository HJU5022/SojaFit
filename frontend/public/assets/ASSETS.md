# assets

## 역할
- 넣는 것: `/assets`에서 제공하는 승인된 브랜드 이미지와 공개 라이선스 샘플 넷리스트(`samples/`, 화면 입구는 #58에서 뺐고 파일만 둠). Vite는 빌드 때 `dist/assets`로 복사하고 FastAPI는 기존 StaticFiles 경로로 제공한다.
- 넣지 않는 것: React 소스, 사용자 업로드, API 데이터, 서버 설정, 비밀값.

## 파일
- `ASSETS.md` — 이 폴더 설명.
- `product/` — 랜딩 "판정 근거" 4단계가 쓰는 운영 화면 캡처 4장(`question.png` 질문 · `missing-condition.png` 빠진 조건 · `condition-evidence.png` 조건별 판정 · `evidence-source.png` 근거 원문). 11-17 운영 리비전 `sojafit-api-pre-ef0138b2-rs`에서 v3-01 질문으로 찍고 사이드바를 뺀 같은 범위(1215×683)로 잘랐다. [왜] FastAPI는 `/assets`와 `/circuit-schematics`만 정적으로 열어서, 루트의 다른 경로는 `index.html`로 대체된다.
- `samples/` — 공개 라이선스 샘플 넷리스트(화면 입구 없음, #58). [SAMPLES.md](samples/SAMPLES.md)
- `sojafit-icon.svg` — 화면 머리 로고(`src/ui.tsx` `Brand`의 인라인 SVG)와 같은 청록색 자리·후보 기호의 투명 SVG. 마주 보는 두 모서리와 가운데 사각형으로 구성하며 특정 전자부품의 기호를 쓰지 않는다. `index.html`의 파비콘으로만 쓴다. [주의] 로고 기호를 바꾸면 이 파일도 같이 바꾼다(#17: 탭 아이콘이 앱 로고와 달랐음).
