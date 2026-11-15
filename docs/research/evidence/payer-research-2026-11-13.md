> 2026-11-13 조사 원문. 웹·SNS 검색은 AI 도구(Grok)로 했고, 아래 핵심 근거는 하정운 쪽에서 원문을 다시 열어 확인했다: G4·G5·G6(Accuris 약관·가격 페이지), G10(Siemens 연 US$180), K6(국방기술품질원 기고, 본문 일부는 요약으로 확인), K2(방사청 공고 PDF 본문 추출). 그 밖의 항목은 이 표의 신뢰도 표기를 따른다. 정리와 판단은 [market-user-journey.md](../market-user-journey.md) 2-3절.

# 전자부품 대체(단종·수급·원가) 업무/도구 — "누가, 얼마를 내는가" 근거 조사

- 작성: 2026-11-13 (KST) · 조사 범위: 2023-01 ~ 2026-11-13 (범위 밖 자료는 **[범위 밖]**으로 표시하고 참고용으로만 씀)
- 사용한 경로: 웹 검색/열람, X(전체 아카이브 검색), Hacker News(Algolia API), Reddit(검색 결과와 개별 스레드 열람. Reddit 검색 API는 봇 차단으로 실패), EEVblog, 국내 커뮤니티(클리앙·디시·블라인드·OKKY·네이버 블로그)
- 표기
  - **종류**: 웹 = 독립 매체·블로그, SNS = 커뮤니티·소셜, 정부 = 정부·공공기관, 벤더 = 도구 판매사·유통사·서비스 업체 자체 자료(벤더 후원 자료 포함)
  - **SNS 항목은 모두 일화(anecdotal)**입니다. 통계가 아니라 개인 경험담입니다.
  - 따옴표 인용은 출처당 한 문장 이하만 썼고, 나머지는 의역입니다.
  - "not opened" = 페이지를 직접 열지 못한 경우입니다. 이때는 검색 결과 요약에만 기댄 것이라 신뢰도를 낮췄습니다.

---

## 1. 근거 표

### 1-A. 글로벌 근거

| 번호 | 출처(제목·발행처·날짜·URL) | 종류 | 알 수 있는 사실(한 줄) | 지불 주체 질문에 주는 근거(누가·얼마) | 신뢰도 |
|---|---|---|---|---|---|
| G1 | BOM Manager · SiliconExpert · 2026-11 열람 · https://www.siliconexpert.com/products/bom-manager/ / FAQs · https://www.siliconexpert.com/faqs/ | 벤더 | Professional(공유 라이선스 1개, BOM 5,000부품 이하)과 Enterprise(복수 사용자, 5,000부품 초과)는 모두 연간 구독이고 가격은 공개하지 않음. 라이선스는 플로팅 방식이고, API는 1년 단위로 '고유 부품 수' 쿼터를 삼. | 누가: 회사 단위 연간 계약. 얼마: 견적제. FAQ는 Vishay BAV99와 Toshiba BAV99를 서로 다른 고유 부품으로 센다고 예시함. 다이오드 수준에서도 제조사별로 과금된다는 뜻. | 상(공식 문서). 단, 가격 수치는 없음 |
| G2 | SiliconExpert 스페인어 미러 https://sebeta.wpengine.com/es/products/bom-manager/ · KI-Syndikat(독일 제3자 리뷰, 2026-05 변경 기록) https://www.ki-syndikat.de/tools/siliconexpert/ | 벤더 미러 + 웹 | 'Essentials' 플랜은 사용자 1명, BOM 1개(500부품), **월 $250**, 언제든 해지 가능하다고 적혀 있음. | 소규모 팀 진입가가 월 $250, 연 환산 약 $3,000. 다만 2026-11-13에 연 공식 영문 페이지에는 Essentials가 보이지 않음. | 중~하(공식 페이지에서 현재 확인 안 됨) |
| G3 | Altium Store(Altium 365 연동 애드온) · Altium · 2026-11-13 열람(KRW로 표시됨) · https://store.altium.com/ | 벤더 | SiliconExpert 연동은 연 **3,333,500원**(회사당 1,000 쿼리)부터 80,001,000원(60,000 쿼리)까지. Z2Data Basic은 연 6,678,000원(2,500)부터 80,131,000원, Premium은 13,356,000원부터 160,262,000원까지. | 누가: PCB 설계툴(ECAD) 안에서 '회사 단위'로 사는 구조라 **설계팀 예산 경로**가 실제로 있음. 얼마: 연 333만~1.6억 원. | 상(공식 가격표) |
| G4 | Parts Intelligence Trial Legal Terms · Accuris · 2026-11 열람 · https://accuristech.com/trial-terms-conditions/ | 벤더 | 9일 트라이얼에 송장을 결제하면 1년 유료 구독으로 자동 전환되고, 연 **$4,950**(세금 별도). | 진입가 연 약 $5k. 계약서가 '권한 부여된 부서(Division/Department)' 단위로 사용자를 정함. 결재가 부서 단위로 이뤄진다는 단서. | 상(공식 약관) |
| G5 | Price Match Offer Terms · Accuris · 2026-11 열람(2026-12-31까지 유효) · https://accuristech.com/accuris-price-match-offer-terms/ | 벤더 | 현재 SiliconExpert·Z2Data를 구독 중인 회사에 1년차 계약가를 맞춰 줌. **최소 ACV $6,000**이고, 매칭은 '사용자·부서가 아닌 회사당 1회'. AI BOM Decision Support 등 부가 모듈은 별도 견적. | 경쟁사 고객 계약 중 연 $6k 이상이 흔하다는 간접 근거. 계약 주체는 회사 단위. | 상(공식 약관). 시장 평균가는 아님 |
| G6 | Supply Chain Intelligence Pricing · Accuris · 2026-11 열람 · https://accuristech.com/pricing-sci/ | 벤더 | 등급별 대상 고객: Parts Intelligence는 "설계 엔지니어·소싱 담당", BOM Pro는 엔지니어링 팀, BOM Elite는 "엔터프라이즈 공급망·구매 조직". | **등급이 높을수록 구매·SCM 조직이 대상.** "단종 1건 회피로 $250K 절감"이라는 문구는 벤더 주장. | 구조는 상, 절감 수치는 하(벤더 주장) |
| G7 | Pricing · Z2Data · https://www.z2data.com/pricing / 일본 대리점 FAQ · https://z2data.kumu-works.com/faq · 2026-11 열람 | 벤더 | 부품(MPN) 수, 라이선스 수, 모듈에 따라 견적을 냄. 연간 구독이고 초기비용은 없음. 트라이얼은 300 MPN. 플로팅 라이선스. | 누가: 회사 단위. 얼마: 비공개. | 상(공식). 가격 없음 |
| G8 | API Supply Scope Comparison · Nexar(Octopart) · 2026-11 열람 · https://nexar.com/compare-plans | 벤더 | 무료 Evaluation은 100부품, Standard는 2,000부품, Pro는 15,000부품. Standard에는 수명주기·데이터시트·스펙이 포함되지 않음. 가격은 페이지에 없음. | API는 '매칭 부품 수'로 과금. 대체품('Similar Parts')은 Enterprise 전용. | 상(공식). 가격 없음 |
| G9 | The Nexar API: What Engineers Need to Know in 2026 · Zenode(경쟁 벤더) · 2026-07-17 · https://zenode.ai/posts/the-nexar-api-what-engineers-need-to-know-in-2026 | 벤더(경쟁사) | 고객 보고를 근거로 Nexar Standard 월 약 $500, Pro 월 약 $2,000이라고 적음. 고객들이 "sticker shock"을 말했다고 함. | API 경로 비용이 월 $500~2,000(연 $6k~24k). | 하~중(경쟁사 글이고 '고객 보고'를 재인용) |
| G10 | PartQuest Portal – Supply Chain(Supplyframe 기반) · Siemens · 2026-11 열람 · https://www.siemens.com/en-us/products/pcb/pads/professional/cloud-apps/supply-chain/ | 벤더 | 설계자용 소싱·수명주기 앱이 연 **US$180**. 3개 앱 번들은 월 $59(연 결제). | 설계자 개인 단위 도구는 연 수백 달러 수준(저가대). | 상(공식 가격) |
| G11 | SupplyFrame NPI · AWS Marketplace(판매자 Siemens) · 2026-11 열람 · https://aws.amazon.com/marketplace/pp/prodview-eqyxen2xu7dnc | 벤더 | 엔지니어링과 소싱이 함께 쓰는 BOM 리스크·대체품 플랫폼. 12개월 계약이 **$250,000부터**. | 엔터프라이즈급은 연 $250k 이상(대기업 조직 예산). | 상(공식 등록가) |
| G12 | Best Electronic Components Analytics Platforms (2026) · ElectricalFlux · 2026-07-07 · https://electricalflux.com/learn-guides/electronic-components-analytics-procurement-guide | 웹(제3자, 출처 표기 없음) | SiliconExpert는 좌석당 연 $5k~9k, Z2Data는 연 $12k 이상, Supplyframe은 조직당 $7.5k~15k로 '추정'. 엔지니어 전원 말고 공급망 엔지니어 1~2명에게 좌석을 사라고 권함. | 좌석을 **공급망 엔지니어 쪽**에 두라는 업계 조언. 금액은 근거 없는 추정. | 하(출처 없는 추정) |
| G13 | SiliconExpert vs Z2Data vs Octopart · The Obsolescence Brief(Hermann Njike, 본인 소개는 '시스템 단종관리 매니저') · 2026-07-06 · https://theobsolescencebrief.com/siliconexpert-vs-z2data-obsolescence-tools/ | 웹(독립 블로그) | 유료 3사(SE·Z2·Accuris)는 모두 견적제이고 Octopart 조회는 무료. 유료 플랫폼은 '구매·프로그램 규모'에서 값을 하고, 엔지니어 한 명이 가끔 쓸 거면 무료로 시작하라고 함. | 유료 도구의 실제 구매자는 **프로그램 규모의 구매·단종관리 조직**. 개별 설계자는 무료 도구로 버팀. | 중(실무자 관점의 독립 글. 단, 저자 검증 불가) |
| G14 | BorgWarner Selects Lytica · Lytica 보도자료 · 2025-12-16 · https://www.lytica.com/resources/news/borgwarner-selects-lytica-to-power-data-driven-electronic-component-sourcing-strategy/ | 벤더 | BorgWarner PDS가 구매 운영용으로 Lytica를 도입. 가격·리스크 데이터에 FFF 대안 식별 기능 포함. 인용자는 PDS Director of Supply Chain. | 누가: **구매·SCM 조직(공급망 디렉터)**. 얼마: 비공개. | 중(벤더 PR이지만 고객사와 직함이 실명) |
| G15 | Obsolescence Business Case · SiliconExpert · 2026-11 열람 · https://www.siliconexpert.com/proof/obsolescence-business-case/ | 벤더 | 투자 결정을 엔지니어링, SCM·구매, 품질, 재무가 함께 내리는 구조로 제시. 고객 인용은 AMETEK Global Commodity Manager. 2019년 사례에서 소싱 매니저가 "That saved us $50,000 almost immediately."라고 말함. | 벤더가 내세우는 증언자가 **구매·소싱 직함**. 결재에 재무가 관여한다고 명시. | 중(벤더 자료. $5만 사례는 2019년 **[범위 밖]**) |
| G16 | Who Should Take the Lead in Managing Obsolescence? · Converge(Arrow 계열 유통사) · 2024-03-13 · https://www.converge.com/resources/news/who-should-take-the-lead-in-managing-obsolescence/ | 벤더(유통사) | 커뮤니티 투표에서 61%가 '공동 책임', 9%가 '공급망 파트너(유통·EMS)가 주도'라고 답함. | 예산 책임자가 한 명으로 정해져 있지 않음. 유통사가 주도해야 한다는 응답은 소수. | 중~하(유통사 주최 투표. 표본 수 비공개) |
| G17 | Four Takeaways From Z2Data's Obsolescence Trends in 2024 · Z2Data · 2024-03-27 · https://www.z2data.com/insights/four-takeaways-from-z2datas-obsolescence-trends-in-2024 | 벤더(설문 약 9,000명) | 가장 큰 고충은 '대체품의 호환·성능 확보' 31%, '대체품 식별' 18%, '단종관리 예산 확보' 8%. 2023년 단종 473,910건 중 약 30%는 PCN 없이 단종됨. | 고충 1위가 **대체품 검증**(제품 가치 제안과 일치). 예산 확보를 어려움으로 꼽은 사람은 소수. | 중(벤더 설문) |
| G18 | Discontinued Audio Chips Push Small Brands… · Headphonesty · 2026-08-15 · https://www.headphonesty.com/2026/08/chips-inside-dacs-amps-production-overnight-parts/ | 웹(독립 매체, Z2Data 수치 인용) | 2025년 단종 621,909건 중 52%가 PCN 없이 단종됨. 업계 추정으로 단종 재설계 1건이 $20k~약 $2M, 회로·레이아웃 $15k~80k, 재검증 $20k~100k. | 페인 비용(재설계·재검증)이 도구 가격(연 $3k~6k)보다 한두 자릿수 큼. | 중~하(비용은 2차 인용 '업계 추정') |
| G19 | Avoid PCB Respin: FFF Component Substitution · ESP32s.com(EMS 업체) · 날짜 미확인 · https://esp32s.com/blog/avoid-costly-pcb-respins-the-ultimate-guide-to-form-fit-function-fff-component-substitution/ | 벤더(EMS) | PCB 리스핀 한 번에 $2,000~5,000이 들고 한 달 이상 지연된다고 함. | 소형 보드는 재설계 직접비가 작아, 고가 도구를 정당화하기 어려울 수 있음. | 하(업체 마케팅. 날짜 미상) |
| G20 | Mouser unveils new BOM tool(FORTE) · EP&T · 2017-04-06 · https://www.ept.ca/mouser-unveils-new-bom-tool/ | 웹(업계지) | My Mouser 계정만 있으면 무료로 BOM 검증과 대체품 추천을 받을 수 있음. | **유통사는 대체품 도구를 고객에게 무료로 주고 주문으로 회수.** 고객에게 도구값을 받지 않음. | 중(출시 기사는 2017년 **[범위 밖]**, 현재도 제공 중인지는 미확인) |
| G21 | The Avnet Add-in for Autodesk Fusion… · Avnet · 2025-02-27 · https://news.avnet.com/news-blog/news-blog-details/2025/The-Avnet-Add-in-for-Autodesk-Fusion-Delivers-Free-Reference-Schematics-and-Live-Supply-Chain-Insights/default.aspx | 벤더(유통사) | 설계툴 무료 애드인에 대체품 검색·교체, BOM 최적화(가격·리드타임·수명주기), Avnet 담당자 연결 기능을 넣음. | 유통사가 **설계 단계 대체품 도구를 무상 번들**로 줌. 비용은 유통사가 부담하고 수주로 회수. | 상(유통사 공식 발표) |
| G22 | Arrow의 SiliconExpert 인수 · MarketScreener 등 · https://www.marketscreener.com/quote/stock/ARROW-ELECTRONICS-INC-11687/news/Arrow-Electronics-Inc-acquired-SiliconExpert-Technologies-Inc-39418470/ | 웹 | Arrow가 SiliconExpert를 인수함(검색 요약상 2012년). G13·G2도 'Arrow 소유'로 적음. | 대형 유통사는 도구를 '사서 쓰는' 쪽이 아니라 **소유하고 고객에게 파는** 쪽. | 중. **not opened**(MarketScreener 원문 미열람, 2차 기재만 확인) |
| G23 | Octopart Sponsored Results · Octopart · https://octopart.com/pulse/p/octopart-sponsored-results | 벤더 | 검색 요약상 유통사·제조사가 Octopart의 노출(스폰서 결과)에 돈을 냄. | 유통사의 지불 형태는 '도구 라이선스'가 아니라 **트래픽·노출 광고비**. | 하. **not opened**(403) |
| G24 | Show HN: Zenode – AI-powered component search · Hacker News · 2025-09-22~23 · https://news.ycombinator.com/item?id=45349822 · https://news.ycombinator.com/item?id=45334763 | SNS(HN, 일화) | 창업자(bbourn)는 가격·재고 데이터를 유통사 쪽으로 트래픽을 보내 주는 대가로 받기를 바란다고 씀. 다른 사용자(caromexia2)는 구매팀이 기술적 트레이드오프를 모른 채 대체 부품을 소싱한다고 지적. | 유통사와는 현금보다 **데이터·트래픽 교환**이 현실적이라는 창업자 인식. | 하(일화. 창업자 이해관계 있음) |
| G25 | What's your favorite BOM management software? · Reddit r/AskElectronics · u/Clear-Apple-9625 2024-07-31, u/davus_maximus 2022-03-05 · https://www.reddit.com/r/AskElectronics/comments/t71gy1/ | SNS(일화) | 2024년 사용자: 부품난 때 SiliconExpert가 프로젝트를 살렸다고 함. 2022년 사용자: 부품 1,000개 단위 블록으로 사야 하고 "£thousands"가 든다고 함. | 비용은 수천 파운드/년 수준이라는 1인칭 증언(2022년 **[범위 밖]**). 결재자는 언급 없음. | 하(익명 일화) |
| G26 | BOM management and component sourcing – what's your workflow? · Reddit r/ElectricalEngineering · u/audaciousmonk, u/catdude142 · 2025-11-17~18 · https://www.reddit.com/r/ElectricalEngineering/comments/1ozrj8m/ | SNS(일화) | 한 사람: 전담 공급망 담당자가 대체 공급처와 EOL 통보를 맡아 엔지니어링에 넘긴다고 함. 다른 사람: "Purchasing and Materials Engineering Department"가 처리한다고 함. | 운영 주체가 **구매·자재엔지니어링**이라는 1인칭 증언. 금액은 없음. | 하~중(익명 일화 2건, 내용은 서로 일치) |
| G27 | What do you guys use for component obsolescence information? · Reddit r/AskElectronics · 2019-04 · https://www.reddit.com/r/AskElectronics/comments/bcdlkb/ | SNS(일화) | 항공우주 회사(부품 1만 개 이상)가 SiliconExpert 영업을 받음. 다른 사용자는 SE가 ERP에 연동돼 있고 "다른 부서"가 이슈를 잡아 엔지니어링에 넘긴다고 씀. | 비엔지니어링 부서(구매·ERP 운영)가 도구를 보유하는 패턴. | 하(**[범위 밖]** 2019, 참고만) |
| G28 | Any good tool for alternative part search? · Reddit r/AskElectronics · 약 2024("2y ago" 표기) · https://www.reddit.com/r/AskElectronics/comments/1dq29wn/ | SNS(일화) | DigiKey 크로스레퍼런스는 "doesn't work well"이라고 함. TI 크로스 검색은 후보가 1~2개거나 아예 안 나온다고 함. | 무료 유통사 도구에 대한 불만, 즉 미충족 수요. 지불 의사는 언급 없음. | 하(익명 1건) |
| G29 | X 게시물 · @SuccessBoots · 2026-11-01 · https://x.com/SuccessBoots/status/2117018446403641388 | SNS(X, 일화) | UAV 프로그램에서 개발 중에 메인 프로세서가 단종돼 "The redesign cost more than the original BOM."이었다고 함. | 페인 비용 일화. 금액 없음. | 하(익명 일화) |
| G30 | X 게시물 · @geek4liberty · 2026-01-26 · https://x.com/i/status/2015597466809250193 | SNS(X, 일화) | 방산은 생산량이 적어서 새 부품으로 재설계하고 재인증하는 NRE가 구 부품을 사재기하는 비용보다 보통 크다고 함. | 저물량 산업에서는 대체보다 LTB 쪽으로 예산이 간다는 견해. | 하(일화) |
| G31 | X 게시물 · @GrishinRobotics(투자사) · 2026-01-31 · https://x.com/i/status/2017549841920909530 | SNS(X) | 1Buy.AI가 구매용 'AI 운영체제'로 시드 $3.9M을 유치. 엔지니어는 이미 SE·Supplyframe·Octopart를 쓰고 있고, 남은 가치는 구매 워크플로(승인·대체품·절감 추적) 연결이라고 봄. | 투자자는 **구매 조직**을 지불 주체로 보고 있음. | 하(투자자 SNS) |
| G32 | X 게시물 · @BaoDou3772 · 2026-10-25 · https://x.com/BaoDou3772/status/2114375178822066657 | SNS(X, 일화) | 단종 공지가 오면 구매는 남은 재고를 찾고, 엔지니어링은 대안을 찾고, 생산은 전환 시점을, 서비스는 예비품 기간을 묻는 흐름을 묘사. | 여러 부서가 얽힌 업무라는 묘사. 결재자는 특정하지 않음. | 하(일화) |
| G33 | LinkedIn 게시물 · Lentec · 2026-09-07(활동 ID로 추정) · https://www.linkedin.com/feed/update/urn:li:activity:7502655396906647552 | SNS(LinkedIn, 일화) | SAP ERP와 연동한 부품 수명주기 관리 시스템에 SiliconExpert를 통합해, 고위험 부품이 생기면 엔지니어링과 구매에 동시에 알림을 보낸다고 함. | 도구가 ERP(구매 측 시스템)에 붙어 있음. 금액 없음. | 하(일화. 날짜는 추정) |
| G34 | LinkedIn 게시물 · Yazharasan M · 2025-04-04(활동 ID로 추정) · https://www.linkedin.com/posts/yazharasan-10-m_componentengineering-ecm-plm-activity-7313821698431074305-wnbt | SNS(LinkedIn, 일화) | 부품 엔지니어가 IHS, SiliconExpert, Z2Data를 매일 쓴다고 함. | 실제 사용자는 **부품 엔지니어(component engineer)**. 지불자 정보는 없음. | 하(일화) |
| G35 | 구매자가 엔지니어에게 대체 부품을 추천해야 할까요? · Altium/Octopart(한국어판) · 2023-12-03 · https://resources.altium.com/kr/p/should-buyers-recommend-alternative-parts-engineers | 벤더 | 단종 부품은 종종 구매 관리자가 발견하지만, 대체품은 엔지니어링이 자격 검증을 해야 하고 구매자가 자동으로 선택해서는 안 된다고 함. | **승인권은 엔지니어링, 발견·추천은 구매.** 비용 부담 주체는 언급 없음. | 중(벤더 칼럼) |

### 1-B. 한국 근거 (Korea-specific)

| 번호 | 출처(제목·발행처·날짜·URL) | 종류 | 알 수 있는 사실(한 줄) | 지불 주체 질문에 주는 근거(누가·얼마) | 신뢰도 |
|---|---|---|---|---|---|
| K1 | 26-6차 무기체계 부품국산화개발 지원사업 과제 예비공고 · 방위사업청 · 2026-11-04 · https://krit.re.kr/common/download.do?atchFileId=F20261104132806821&fileSn=0 | 정부 | 핵심부품국산화는 정부가 최대 100억 원까지 지원(중소 75%, 중견 70%, 대기업 50%). 예비 과제 예시: '비호복합 회로카드조립체 2종' 정부지원 최대 44.47억 원. | 누가: **정부(방사청)가 개발비를 대고, 중소기업이 신청**. 얼마: 과제당 수억~수백억 원. 단, 대상은 '부품 개발'이지 대체품 선정 도구가 아님. | 상(공고 원문) |
| K2 | 25-2차 부품국산화개발 지원사업(상생협력형) 공고 · 방위사업청(대전국방벤처센터 게재) · 2025-09-04 · https://djdi.or.kr/_files/board/20250904/d8dfc240da5ab838fcd97596aa066731.pdf | 정부 | 개발 대상에 "단종이 되었거나 단종이 예상되는 품목"이 명시됨. 정부와 투자기업(방산 중견·대기업 39개사)이 1:1로 매칭 출연하고, 중소기업은 25% 이상 부담. 2025년 신규예산은 10억 원. | 단종 대응 개발비를 **정부 + 체계기업(대기업)**이 공동으로 냄. 신청자는 중소기업. | 상(공고 원문) |
| K3 | 26-3차 상생협력부품국산화 모집 공고 · 방위사업청 · 2026-04-29 · https://www.dapa.go.kr/dapa/doc/selectDoc.do?bbsSeq=443&docSeq=58528&menuSeq=3031 / 정부24 안내 · https://www.gov.kr/portal/service/serviceInfo/169000000009 | 정부 | 2026년 접수는 4/29~6/9였음. 정부24 안내상 과제별 최장 5년, 최대 100억 원, 전략부품은 500억 원 한도. | 국방 분야는 단종·국산화에 **상시 공공예산**이 있음. | 상 |
| K4 | 2025년도 소부장 공급망안정 종합지원 사업 3차공고 · 산업통상자원부 · 2025-09-01 · https://www.motir.go.kr/kor/article/ATCL2826a2625/70524/view + 요약 RnDcircle · https://app.rndcircle.io/gov-grant/995914fd-2e85-429c-b864-c05bb005805d | 정부(요약은 제3자) | '수입처 다변화'는 대체 수입처 발굴, 샘플 구매(4천만 원 한도), 공인 시험인증, 시운전을 지원하며 기업당 최대 5천만 원, 총비용의 80%. 선정 규모는 '2개사 내외'. 별도로 '공급망 컨설팅'은 2천만 원 한도 80%. | 누가: 중소·중견 소부장 기업이 신청하고 KOTRA가 사후정산. 얼마: 기업당 최대 5천만 원. 시험·인증, 컨설팅 비용이 대상이라 **대체 검증 용역비를 공공이 일부 부담할 가능성**이 있음(도구비 포함 여부는 미확인). | 중~상(공고문 PDF는 **not opened**(TLS 오류), 세부 내용은 RnDcircle 요약에 의존) |
| K5 | 소부장 대체처 발굴 헬프데스크 · KOTRA · 2026-11 열람 · https://www.kotra.or.kr/subList/41000032001 | 정부 | 수급 위험 원부자재를 수입하는 기업에 해외무역관이 대체 공급선 발굴을 지원. 온라인 상담으로 신청. | **공급처 탐색은 공공이 무상 제공**하므로 같은 기능에 기업이 돈을 낼 동기는 약함. 회로 수준 대체 판단은 범위 밖. | 상(공식 안내) |
| K6 | 부품단종 대응을 위한 부품정보 예측 기술의 발전 방향 · 국방기술품질원 DQS 매거진 · 2024-04-25 · https://dtaq-media.kr/dqs-magazine?id=219 | 정부(공공연구기관) | 각 군, 해병대, 기업체가 IHS BOM/Parts Intelligence, SMART, Q-STAR, **A-Brain(국산, 애니파이브)**을 쓰고 있음. 상용 도구의 정보 획득률은 최대 50% 수준. ○○체계는 단종 대응을 안 하면 20년간 16억 원이 추가된다는 보고가 있음. | 누가: **군과 방산업체가 상용 단종 도구를 구매해 사용**(한국에서 확인된 유일한 '유료 도구 구매자' 근거). 얼마: 도구 가격은 미공개. 미대응 비용은 체계당 16억 원 사례. | 상(공공기관 기고) |
| K7 | 부품단종에 대한 조사·분석 및 관리방안 · 한국산학기술학회논문지 21(5) · 2020 · https://www.kais99.org/jkais/journal/Vol21No05/vol21no05p29.pdf | 웹(학술) | 군 장비 4종 시범사업: 재개발(4품목)은 장비별 25억~52억 원, 1:1 대체는 11품목 260만 원 / 26품목 5,400만 원. KDS-1은 단종으로 약 2년간 수리부속을 확보하지 못함. | **대체품을 찾으면 재설계 대비 비용이 수십~수천 분의 1** → 대체 판정에 지불할 경제적 근거. | 상(논문 원문 표 확인). 단 **[범위 밖]** 2020, 방산 한정 |
| K8 | AD7280A BMS 개발기 번외 #1 – 단종 통보 받던 날 · mcu2cloud.kr(개인 블로그) · 2024-12-15 · https://mcu2cloud.kr/posts/bms/ad7280a-bms-dev-b1/ | SNS(블로그, 일화) | '부품팀 김 대리'가 NRND를 통보함. 양산 1,000대에 IC 4,000개가 필요했는데 국내 유통 재고는 거의 0개였음. 브로커 가격은 $15(정가 $8). Arrow·Avnet에서 350개를 확보했고, 후속품은 핀 비호환이라 재설계에 6개월~1년이 걸릴 것으로 봄. | **감지는 부품(구매)팀, 비용은 설계팀 공수(수개월)와 부품 프리미엄(약 2배)으로 발생.** 도구 지불 언급은 없음. | 중(구체적인 1인칭이지만 단일 사례이고 작성자 검증 불가) |
| K9 | 반도체·전자부품 단종(EOL)으로 인한 대치품 찾는 방법 · 마이크로웍스코리아(국내 반도체 유통·구매대행) · 2023-07-24 · https://microworkskorea.tistory.com/2038 | 벤더(유통사) | 제조사 문의, 데이터시트 비교, DigiKey 필터로 대치품을 찾는 법을 소개하고, 대치품 추천과 긴급자재 공급을 자사 서비스로 홍보. | **국내 중소 유통사는 대체품 추천을 무료 영업 수단으로 씀**(돈은 부품 판매로 회수). | 중~하(업체 홍보글) |
| K10 | 소자적합성 검증 · 큐랩스 회로증진센터 · 날짜 미상(2026 열람) · https://cic.qraps.co.kr/components | 벤더(시험·분석 용역) | 대체 소자 발굴과 적합성 시험, Cross-Ref 데이터, 전기·열·신뢰성 가속시험을 유료 용역으로 제공(가격 비공개). | 한국에 **'대체품 검증' 유료 용역 시장**이 존재. 고객은 제조사(부서 미상). | 중~하(업체 페이지, 가격 없음) |
| K11 | 온다N – 전자부품 구매·재고관리 SaaS · 파츠고(주) · 2026 열람 · https://www.ondaparts.com/ | 벤더(국내 SaaS) | 견적, 발주, 재고에 더해 단종·비권장 부품 식별과 대체품 검토, LTB 준비 기능을 제공. 가격 비공개. | 국내 SaaS가 단종 기능을 **구매 담당자용**으로 묶어 팖. 구매 예산 경로를 시사. | 중~하(업체 페이지) |
| K12 | 3DEXPERIENCE OnePart · 케이이노텍(다쏘 리셀러) · 2026 열람 · https://www.kinnotech.co.kr/onepart/ | 벤더 | AI 유사부품 식별, 공용화, 대체품 기반 절감 추적. 설계·구매·제조 관점의 과제를 각각 제시. | 국내 대기업·중견 대상 PLM 경로(설계·구매 공동). 금액 없음. | 하(업체 페이지. 주로 기구 부품) |
| K13 | [새로운SW] 애니파이브 '에이브레인(A-Brain)' · PRESS9/전자신문 · 2018-06-20 · https://www.press9.kr/news/articleView.html?idxno=36796 | 웹(언론) | 국내 최초 단종 부품 검색·예측 클라우드. 연구·개발·구매 부서가 쓰는 것을 상정. 국방부와 대기업은 그전까지 자체 시스템이나 수작업으로 관리했다고 함. | 한국판 SiliconExpert가 있음(K6에서 군·방산 사용 확인). 가격은 미공개. | 중(**[범위 밖]** 2018). 관련 전자신문 2018 SE 협력 기사는 **not opened** |
| K14 | 메모리 재고는 쌓이는데…아날로그반도체는 여전히 공급부족 · 디일렉 · 2023-04-06 · https://www.thelec.kr/news/articleView.html?idxno=20520 | 웹(언론, 맥킨지 인용) | 2023년 초 MCU·센서 리드타임이 20~40주. 맥킨지는 수요 기업의 80% 이상이 칩 부족에 대비가 안 돼 있다고 봄. | 2023년에도 레거시 IC 수급 페인이 지속됐다는 근거. 지불 주체 정보는 없음. | 중 |
| K15 | 경기도 반도체 산업 실태조사(2023년, 1,000개사) · 아주경제 · 2024-03-06 · https://www.ajunews.com/view/20240306150217032 | 웹(언론, 공공 조사 인용) | 도내 반도체 관련 기업이 꼽은 가장 큰 경영 애로는 '원자재 수급 및 가격 상승'(38.7%). | 수급 고충의 규모 근거. 대체부품 비용·결재자는 다루지 않음. | 중 |
| K16 | 단종 부품 대체, 핀 호환 부품으로 충분할까? · NETECH(국내 PCB 역설계 업체) · 2026-09-15 · https://e-netech.com/blog/52 | 벤더(용역 업체) | K7 논문을 인용해 재설계는 최후 수단이라고 설명하고, 역설계·대체품 검증 용역을 홍보. | 국내 '대체 검증·재설계' 용역 수요의 존재. (논문 수치를 '1:1 대체 1건 5,400만 원'으로 옮겼는데, 원문은 26품목 합계임) | 하~중 |
| K17 | 단종 부품 대체품 선정 10단계 체크리스트 · OK COMPONENTS 매거진 · 날짜 미상 · https://okcomponents.com/article/magazine/8/17/ | 벤더 | 사내 승인부품, 제조사 크로스레퍼런스, Octopart·DigiKey·Mouser 순으로 후보를 찾고, 마지막에 고객사 승인과 기록을 남기라고 안내. | 실무 흐름 근거. 비용 주체는 없음. | 하 |
| K18 | 국내 유통몰(디바이스마트·엘레파츠·아이씨뱅큐) 대체부품 기능 · 아이씨뱅큐 스펙서치 https://www.icbanq.com/productSpec.do | 벤더 | 검색 요약상 아이씨뱅큐는 스펙 검색만 있고, 세 곳 모두 공식 '대체부품 크로스레퍼런스' 서비스는 확인되지 않음. | 국내 소매 유통사가 **대체 도구에 돈을 쓰거나 번들한다는 근거를 찾지 못함.** | 하(**not opened**. 검색 요약에만 의존) |
| K19 | 국내 커뮤니티 1인칭 글 검색 결과(디시 통합검색 '단종 대체품', 클리앙, 블라인드, OKKY) | SNS | 디시 결과는 소비재 위주이고 전자회로 관련 글이 없음. 클리앙 '부품 수급' 글은 2022-09-20(리드타임 60주 언급, **[범위 밖]**, https://www.clien.net/service/board/park/17572878). 블라인드·OKKY에서는 '누가 단종 도구 비용을 내는가'를 다룬 1인칭 글을 찾지 못함. | **한국 1인칭 지불·결재 증언 없음.** | — (검색 결과 없음) |

### 1-C. 열지 못한 자료(not opened)

- Octopart Sponsored Results(403). 위 표 G23 참조.
- 한경 마켓인사이트 "인증만 6개월에 신제품 접었다"(2023-01, 403). 가전 중소기업 재인증 기간 관련 기사. 검색 요약만 봤고 표에는 넣지 않음.
- DigiKey Cross-Reference 안내(403), Avnet MyAvnet BOM tool(400).
- 2025 소부장 공급망안정 종합지원 공고문 PDF(bizinfo, TLS 오류). K4는 산업부 게시글과 RnDcircle 요약으로 대체함.
- KEA 공지(gokea.org, 본문 비어 있음), smart.kipa.org A-Brain 안내(504), 국방기술품질원 2024 예산 PDF(검색 요약상 '부품단종관리계획서 기술검토 35건'), 전자신문 2018 애니파이브·SiliconExpert 협력 기사.
- Reddit 검색 API(봇 차단). 개별 스레드만 열람함.

---

## 2. 결론

1. **가장 유력한 지불 주체는 구매·SCM(소싱/부품관리) 조직**입니다. 상위 등급 도구가 구매 조직을 대상으로 하고(G6), 실명 도입 사례와 증언자도 공급망 디렉터·커머디티 매니저입니다(G14·G15). 1인칭 일화에서도 구매·자재엔지니어링이 운영 주체로 나옵니다(G26). 다만 **대체품 승인권은 설계(엔지니어링)**에 있고(G35·K8), 설계툴 애드온 경로(연 333만 원부터, G3)도 있어서 '설계가 쓰고 구매·SCM이 결재하는' 공동 구조로 보입니다. 유통사는 대체 도구를 무료로 번들하거나(G20·G21) 데이터 업체를 소유합니다(G22). 지불자라기보다 '무료 제공자/경쟁자'입니다.
2. **가격대**는 다음과 같습니다(대부분 공식 자료로 확인).
   - 소규모: 연 약 $3k~5k (SE Essentials 월 $250은 공식 페이지에서 현재 미확인, Accuris 연 $4,950, G2·G4)
   - 중간: 연 $6k 이상 (Accuris가 밝힌 최소 계약 규모, G5) ~ 수천만 원 (G3)
   - 엔터프라이즈: 연 $250k부터 (G11)
   - 비교하면 재설계 비용은 건당 수만 달러에서 수십억 원 수준입니다(G18·K7).
3. **증거 강도**는 항목별로 다릅니다.
   - 도구 시장과 가격대가 실재한다는 점: **강**
   - "누가 결재하나": **약~중**. 벤더 자료와 익명 일화가 대부분이고, 1인칭 결재 증언은 없습니다.
   - 한국: **약**. 공공자금은 국방 부품국산화와 소부장 수입처 다변화로 명확합니다(K1~K4). 하지만 한국 민간 중소 제조사가 이런 도구를 사는 근거는 군·방산 사용 사례(K6)뿐입니다.
4. **아직 증명되지 않은 것**은 다음과 같습니다.
   - 한국 중소 제조사의 실제 지불 의사와 금액
   - 회로설계와 구매 중 누구 예산 계정으로 잡히는지
   - 다이오드 수준의 "회로 기능 판정 + 데이터시트 페이지 인용" 기능에 기존 도구보다 더 낼 의향이 있는지
   - 정부 지원사업 비용 항목에 대체 판정 도구·용역비가 인정되는지

---

## 3. 한국 근거 중 가장 좋은 3개

1. **K6 – 국방기술품질원 DQS 매거진(2024-04-25)** https://dtaq-media.kr/dqs-magazine?id=219
   - 한국에서 실제로 상용 단종 도구(IHS, A-Brain 등)를 **누가 사서 쓰는지**(각 군·방산업체) 공공기관이 직접 밝힌 자료입니다.
   - 상용 도구의 정보 획득률이 최대 50%라는 한계와, 미대응 시 체계당 16억 원 추가라는 비용 수치도 있습니다.
2. **K1·K2 – 방위사업청 부품국산화개발 지원사업 공고(2025-09-04, 2026-11-04)**
   - https://krit.re.kr/common/download.do?atchFileId=F20261104132806821&fileSn=0
   - https://djdi.or.kr/_files/board/20250904/d8dfc240da5ab838fcd97596aa066731.pdf
   - '단종 품목'을 지원 대상으로 명시했고, 중소기업 신청, 정부·체계기업 매칭, 과제당 최대 100억 원이라는 **공공 예산 주체와 규모**가 원문에 있습니다.
3. **K8 – mcu2cloud.kr "단종 통보 받던 날"(2024-12-15)** https://mcu2cloud.kr/posts/bms/ad7280a-bms-dev-b1/
   - 국내 양산 현장의 1인칭 기록입니다(일화).
   - 부품팀이 감지하고, 국내 유통 재고가 거의 0이고, 브로커가 정가의 약 2배를 부르고, 핀 비호환으로 재설계에 6개월~1년이 걸리는 흐름을 보여줍니다.
   - **페인 비용과 부서 간 역할 분담**을 볼 수 있습니다. 단, 지불 주체는 직접 나오지 않습니다.

- 차순위: K4 산업부·KOTRA 소부장 수입처 다변화(기업당 최대 5천만 원, 80%), K7 KAIS 논문(재설계 25억~52억 원 vs 대체 260만~5,400만 원, 2020년 **[범위 밖]**).

---

## 4. 남은 공백을 메우기 위한 인터뷰 질문 (한국 하드웨어·구매 담당자 대상)

1. "최근 12개월 동안 단종·품절·원가 때문에 부품을 바꾼 건이 몇 건이었나요? 건당 회로설계 공수(시간), 시험·인증 비용, 양산 지연은 대략 얼마였나요? 그 비용은 개발팀 공수로 잡히나요, 구매·프로젝트 비용으로 잡히나요?"
2. "지금 대체품을 찾을 때 쓰는 도구는 무엇인가요(유통사 무료 툴, Octopart, SiliconExpert/Z2Data, A-Brain, 엑셀)? 유료라면 어느 부서 예산 계정이고, 연 얼마이며, 갱신은 누가 결재하나요?"
3. "대체 부품의 최종 승인 서명은 누가 하나요(회로설계, 품질, 구매 중 누구)? 승인할 때 데이터시트의 페이지·표 근거를 문서로 남기라는 요구가 있나요? 그 문서를 만드는 데 건당 몇 시간이 드나요?"
4. "다이오드·TVS 같은 개별 소자를 바꿀 때, '회로에서 맡은 역할 판정 + 대체 조건 + 후보별 데이터시트 근거'를 자동으로 만들어 주면 얼마까지 낼 수 있나요?" 기준선을 제시해 주세요: 건당 ○만 원, 연 300만 원(Altium SiliconExpert 연동 수준), 연 1,000만 원.
5. "거래하는 유통사(FAE)가 대체품을 무료로 추천해 주나요? 그 추천을 그대로 승인하나요, 다시 검증하나요? 소부장 수입처 다변화나 부품국산화 같은 정부 지원을 신청해 본 적이 있다면, 대체 검증 용역비나 도구비가 비용으로 인정됐나요?"

---

## 5. 국내 유료 단종 도구 가격 추가 조사 (2026-11-16)

강사 11/13 코멘트 ①("국내 유료 단종 도구 가격을 남기세요")에 답하려고 국내 제품과 공공 지출을 다시 찾았다. 웹 검색(Claude 웹 검색 · Firecrawl)으로 했고, 온다N 첫 화면만 원문을 직접 열었다. K22 · K23은 검색 요약만 봤다(원문 미열람).

| 번호 | 출처(제목·발행처·날짜·URL) | 종류 | 알 수 있는 사실 | 가격 |
|---|---|---|---|---|
| K20 | 온다N 첫 화면 · 파츠고(주) · 2026-11-16 열람 · https://www.ondaparts.com/ | 벤더(국내 SaaS) | 전자부품 구매·재고관리 SaaS에 "단종 · 비권장 부품을 한눈에 식별하고, 적기에 대체품 검토나 라스트타임바이를 준비" 기능을 묶어 판다. 도입 경로는 "데모 신청하기" · "문의하기"뿐 | 공개 가격 없음 |
| K21 | A-BRAIN 제품 소개 · 애니파이브 · 2026-11-16 검색 · http://anyfive.com/web/pr_ebrain.asp?menu_num=5 / 기업정보 https://thevc.kr/anyfive | 벤더 | AI 기반 부품 단종 예측 플랫폼, 대체부품 정보 제공. 기업정보 사이트는 회사 수익원을 구독료 · 기술 서비스 수수료로 적는다 | 공개 가격 없음. 조달청 혁신장터 · 디지털서비스몰 등록도 검색으로 확인하지 못함 |
| K22 | 2024년도 성과관리 시행계획 · 국방부 · https://www.evaluation.go.kr/upload2/atch/eval/20240603134413776.pdf | 정부(검색 요약) | "'23년 단종정보 획득 용역사업을 통해 3,506종의 단종정보 획득". 2025년도 시행계획 검색 요약은 "'24년 … 3,932종" | 사업 금액은 확인하지 못함 |
| K23 | 무기체계부품단종/위조부품관리발전연구 제안요청서 · 국방기술품질원 · https://www.dtaq.re.kr/_custom/dtaq/_common/board/download.jsp?attach_no=197808 | 정부(검색 요약) | 단종 관리 발전 연구용역 | 발주예산 320,000,000원(수수료 · VAT 포함). 연구용역 값이며 도구 구독료가 아님 |

판단:
- 국내 단종 도구 두 곳(K20 온다N, K21 A-BRAIN)은 가격을 공개하지 않고 데모 · 견적으로 판다. 원화로 공개된 값은 해외 도구의 국내 판매가(G3 Altium Store, SiliconExpert 연동 연 3,333,500원)뿐이다.
- 국내에서 단종 정보에 돈을 내는 것이 공개 자료로 확인되는 곳은 국방(K6 · K22 · K23)이다. 민간 중소 제조사가 단종 도구에 내는 국내 가격은 공개 자료로 확인되지 않는다.
- 이 공백은 견적 요청(파츠고 · 애니파이브)이나 4절 인터뷰로만 메울 수 있다.
