# 평가셋 검토표 — 50건(관련 25·비관련 25)

원본 데이터는 [draft_50.jsonl](draft_50.jsonl)이다. 2026-11-02 Codex 보조 검증은 [SECOND_PASS_50_REVIEW.md](SECOND_PASS_50_REVIEW.md)를 본다. 기존 50건의 2차 리뷰는 진행했으며 n01·n02·h03의 변경 의견을 현재 JSONL 초안에 반영했다. 세 건의 1차 재검수·합의와 n21의 하정운 검수는 대기 중이며 동결 전이다. n22(관련)·n13(비관련)은 예비로 이관해 본편에서 제외했다. 근거 줄의 `datasheets/…txt`와 `corpus_txt/…txt`는 같은 이름의 TSC 데이터시트 PDF를 쪽별 글자로 뽑은 파일(저장소 밖)이고, `netlists/<회로>.net`은 `data/circuits/collected/`의 회로 넷리스트다. `draft_50.jsonl`의 `gold_chunks`에는 PDF 이름과 저장소 넷리스트 경로로 바꿔 적었다.

> **판정 기록**
> - 정답 초안: Codex가 썼다(기존 30건은 11-01 정답 초안 작업, 새 20건은 11-01 출제·정답 분리 작업). 아래의 "Codex 판단"·"Codex 정답"이 그 초안이다.
> - 1차 사람 판정(하정운, 2026-11-01): 50건 판정을 마쳤다. 사람 확인 요청이 붙은 4건은 이렇게 정했다. e04는 2쪽 상세표의 IF = 10mA 조건 값, m08은 비관련(missing_attribute), n01은 역할상 충분, n02는 불충족.
> - 숫자형 7건은 기계 대조를 통과했다.
> - 2차 사람 판정(김재훈, 2026-11-02): 기존 확인란 43건에 O/X를 기록했다. 숫자형 7건은 별도 확인란이 없는 기존 기계 대조 기록이며, 숫자형을 제외한 당시 합의 40건의 JSONL 2차 O 기록을 동기화했다(현재 본편 39건). 추가 당시 n21·n22는 김재훈 O(11-02), 하정운 1차 검수 대기다.
> - 두 사람 판정이 다른 문항만 함께 다시 보고 정한 뒤 동결한다.

## 검수 확정 표시 — 공식 동결 아님

- 39건: 본편에 남은 두 사람 O 명시 문항(n13 예비 이관). JSONL의 human_2를 동기화하고 `reviewers_agreed_change_hold`로 표시했다. 현재 코퍼스 기준의 사람 합의분이며 근거 검증·공식 해시 동결과 같지 않다.
- 숫자형 7건: e03·e05·e08·m03·m07·n03·n05는 기존 기계 대조 기록만 있고 별도 2차 사람 판정 칸이 없다. `mechanical_check_only_human_record_pending`으로 구분했다.
- 보류 4건: n01·n02·h03의 변경 답안 재검수·합의, n21의 하정운 검수는 대기 상태다.
- 코퍼스를 축소하면 합의 39건도 새 코퍼스의 근거 보존·관련성 영향을 다시 확인해야 한다. 현재 파일을 FROZEN.json에 등록하지 않았다.

## 11-02 분류 기준과 현재 초안

- 분류 기준은 [EVALS.md](EVALS.md#관련비관련과-not_verified의-구분)를 따른다. 52건 초안에서 n22(관련)·n13(비관련)을 예비로 이관해 현재 JSONL은 50건(관련 25·비관련 25)이다. 남은 질문·ID·정답·사람 판정은 변경하지 않았다. 이관 원본과 52건 검토표는 저장소 밖 인수인계 폴더에 보존했다.
- n01·n02는 사용자 조건 부족으로 relevant + NOT_VERIFIED, h03은 요청한 VCC 하한의 문서 근거 부족으로 irrelevant / missing_attribute를 현재 초안에 반영했다. 보존된 1차 O는 이전 답안의 승인이다. 변경된 세 건은 1차 재검수와 합의가 필요하다.
- 아래 기존 50건의 Codex 정답·분류·1차 판정은 변경 전 검수 이력으로 남긴다. **현재 적용할 답안은 JSONL의 expected·kind**이며, 변경 전 내용은 answer_review.before_revision_2026_11_02에 보존했다. 이전 보조 검증 결과도 당시 50건의 스냅샷이다.
- n01·n02의 재훈 X는 변경 전 답안에 대한 이견이다. 새 초안의 최종 승인으로 바꾸지 않는다. h03 의견의 관련 24·비관련 26 표기는 추가 전 50건 기준이다.

| 문항 | 현재 초안 | 이유 | 남은 검수 |
|---|---|---|---|
| n01 | relevant + NOT_VERIFIED | TJ만 주어져 TA 조건 적용 여부 미확인 | 1차 재검수·이견 합의 |
| n02 | relevant + NOT_VERIFIED | 차단 펄스 폭·파형 미지정으로 정격 적용 미확인 | 1차 재검수·이견 합의 |
| h03 | irrelevant / missing_attribute | 요청한 VCC 최솟값의 보장 문서 근거 없음 | 1차 재검수·이견 합의 |

## 기존 30건의 검수 이력

- 1번 표는 숫자만 묻는 문항이다. 정답의 숫자가 근거 쪽 원문에 있는지 기계로 대조했다. 대조에서 걸린 것만 보면 된다.
- 2번 표는 비관련(자료 밖이라 거절이 정답) 문항이다. 질문이 정말 우리 자료 밖인지만 훑고 확인 칸에 O/X를 적는다.
- 3번은 판단이 들어간 문항이다. Codex 결론에 동의하면 O, 아니면 X와 맞는 결론을 적는다.
- 기계 대조는 숫자가 원문에 "있는지"만 본다. 맞는 행·조건에서 왔는지는 보지 않는다.

## 1. 숫자형: 기계 대조로 끝 (5건)

| 문항 | 질문 | Codex 정답 | 기계 대조 |
|---|---|---|---|
| e03 | TSC 1N5817은 역전압을 몇 V까지 견뎌? | TSC 1N5817의 반복 피크 역전압 정격 VRRM은 20 V이며, 표의 기본 조건은 주변 온도 TA = 25 °C이다. 같은 표의 역전압 실효값 VR(RMS)은 14 V로 서로 다른 항목이다. 20 V는 부품의 절대 최대 정격이며 이 값만으로 D1 대체 가능 여부나 회로의 허용 입력 전압을 확정하지 않는다. | 원문에 없는 숫자 없음 |
| e05 | TSC 1N5819는 패키지가 뭐고 방향은 어떻게 보면 돼? | TSC 1N5819의 패키지는 리드형 DO-204AL(DO-41)이며, 문서는 캐소드 밴드로 극성을 표시한다고 명시한다. 따라서 띠가 있는 쪽이 캐소드이고 반대쪽이 애노드이며, 5쪽 PACKAGE OUTLINE DIMENSIONS도 DO-204AL(DO-41)을 표시한다. 원래 D1의 footprint 표기는 import_input:DIODE-0.4이므로 후보 패키지 정보만으로 실제 패드·구멍 간격과 장착 적합성을 확정하지 않는다. | 원문에 없는 숫자 없음 |
| e08 | D3 대신 SS34를 보는데, 이 부품 정격이 어떻게 돼? | 코퍼스에 있는 TSC SS34 기준으로, 절대 최대 정격은 TA = 25 °C에서 VRRM = 40 V, 순방향 전류 IF = 3 A이다. VF 최댓값은 IF = 3 A, TJ = 25 °C, PW = 0.3 ms에서 0.50 V이고 패키지는 DO-214AB(SMC)이다. D3의 원래 SOD-123 footprint와 후보 패키지가 달라 직접 교체 장착에는 기판 수정이 필요하다. 플라이백 대체 판정은 전원 전압·코일 전류·구동 조건이 없어 문서로 확인 안 됨(NOT_VERIFIED)이며, 이 정격만으로 교체를 보장하지 않는다. | 원문에 없는 숫자 없음 |
| m03 | TSC BZT52C3V6은 전압이 딱 3.6V로 고정되는 거야? | BZT52C3V6의 3.6 V는 공칭 제너 전압이며 모든 조건에서 딱 고정되는 값이 아니다. TA = 25 °C, 시험 전류 IZT = 5 mA, 30 ms 펄스 조건에서 VZ 범위는 최소 3.42 V, 공칭 3.60 V, 최대 3.78 V로 공칭 대비 ±5%이다. 실제 제너 전류와 온도가 달라지면 이 시험 조건의 전압을 그대로 보장할 수 없다. | 원문에 없는 숫자 없음 |
| m07 | D1 후보로 BZX84C3V3을 봤는데 정격이 어떻게 돼? | 코퍼스의 TSC BZX84C3V3은 TA = 25 °C, IZT = 5 mA, 300 µs 펄스·주기 5 ms 조건에서 제너 전압 VZ가 공칭 3.3 V, 최소 3.1 V, 최대 3.5 V이다. 소비 전력 절대 최대 정격 PD는 TA = 25 °C에서 300 mW이고 패키지는 SOT-23이며, 3.3 V를 모든 전류·온도에서의 고정값으로 해석하지 않는다. 이 후보의 정격 답변만으로 원래 3.6 Zener D1에 대한 전기적·장착 적합성을 확정하지 않는다. | 원문에 없는 숫자 없음 |

## 2. 비관련: 훑어보기 (11건)

| 문항 | 질문 | 종류 | Codex 결론 | 기계 확인 | 정운 | 재훈 |
|---|---|---|---|---|---|---|
| e06 | Q1 AO3406 대신 쓸 MOSFET 좀 골라 줘. | out_of_domain | 다이오드 대체 범위를 벗어난 MOSFET 선정 요청이므로 후보 선정은 거절하는 것이 정답이다. Q1이 AO3406인 사실은 확인되지만, 제공 자료로 MOSFET 대체 적합성을 판정하지 않는다. | - | O | O |
| e09 | 이 보드 D1의 전압강하 실측값이 얼마야? | missing_attribute | 제공 자료에는 이 보드 D1의 전압 강하 실측 기록이 없다고 안내하는 것이 정답이다. 넷리스트의 1N4001 표기나 다른 후보 데이터시트의 VF를 보드 실측값으로 대신 제시하지 않는다. | - | O | O |
| e10 | TSC 1N5817의 2026년판 데이터시트에서 역전압 정격이 얼마야? | wrong_period | 제공 코퍼스에는 요청한 2026년판 TSC 1N5817 데이터시트가 없어 그 판본의 정격을 확인할 수 없다고 안내하는 것이 정답이다. 확인된 파일은 Version H2104이며, 그 문서의 값을 2026년판의 값이라고 제시하지 않는다. 이 자료 부재는 2026년판이 실제로 존재하지 않는다는 뜻은 아니다. | - | O | O |
| m06 | 이 보드 ATtiny85 대신 다른 MCU를 그대로 꽂아 쓸 수 있어? | out_of_domain | MCU를 다른 제품으로 그대로 꽂아 쓰는 요청은 다이오드 대체 범위 밖이므로 거절하는 것이 정답이다. IC1의 ATTINY85 - 20PU 표기와 소켓 footprint는 확인할 수 있지만 MCU의 핀 호환성이나 펌웨어 호환성을 보장하지 않는다. | - | O | O |
| m09 | D1을 TSC BZT52C3V6으로 바꾼 보드의 USB 시험 결과가 있어? | missing_attribute | D1을 TSC BZT52C3V6으로 바꾼 보드의 USB 시험 결과는 제공 자료에 없어 확인할 수 없다고 안내하는 것이 정답이다. 후보의 데이터시트 정격이나 전형 특성을 USB 통신 시험 통과·인증 결과로 제시하지 않는다. | - | O | O |
| m10 | Franzininho DIY 2026년 개정판에서는 D3를 뭘로 써? | wrong_period | 제공 자료로는 Franzininho DIY 2026년 개정판의 D3를 확인할 수 없다고 안내하는 것이 정답이다. 보유 NET에는 D3 = 1N4148이지만 design.source는 V2RV1 경로이고 내보내기 날짜는 2019-08-28이므로, 이 값을 요청한 2026년 개정판에 옮겨 답하지 않는다. 요청한 개정판의 실존도 제공 자료만으로 단정하지 않는다. | - | O | O |
| h06 | 이 보드의 USB 부트로더를 수정해 줘. | out_of_domain | USB 부트로더 수정은 다이오드 대체 판정 범위 밖이므로 거절하는 것이 정답이다. U3가 ATMEGA32U4인 사실은 확인되지만 제공 자료에는 부트로더 소스나 펌웨어 빌드·시험 근거가 없다. | - | O | O |
| h07 | USB랑 RAW를 번갈아 쓰는데 D2 후보 SS1P3L의 정격은 어떻게 돼? | unknown_entity | SS1P3L의 데이터시트가 제공 코퍼스에 없어 정격을 확인할 수 없다고 안내하는 것이 정답이다. 다른 쇼트키 다이오드의 값을 SS1P3L 정격으로 제시하거나, 그 값으로 D2 대체 가능성을 보장하지 않는다. 후보 데이터시트 부재에 따른 대체 판정은 문서로 확인 안 됨(NOT_VERIFIED)이다. | SS1P3L 목록에 없음 | O | O |
| h08 | USB랑 RAW를 같이 꽂았을 때 USB 쪽 역류 전류를 측정한 값이 있어? | missing_attribute | SJ1 개방에서 USB와 RAW를 동시에 공급했을 때의 USB 쪽 역류 전류 실측 기록은 제공되지 않았다고 안내하는 것이 정답이다. D2의 방향이나 후보 문서의 역누설 전류 IR을 보드 전체의 동시 공급 역류 측정값으로 바꾸어 답하지 않는다. | - | O | O |
| h09 | 이 Pro Micro의 D2는 원래 어느 회사의 무슨 품번을 써? | missing_attribute | 실제 D2의 제조사와 주문 품번은 제공 자료로 확인할 수 없다고 안내하는 것이 정답이다. NET의 DIODESOD는 일반 부품 표기이고 SOD-323은 footprint 정보이므로 특정 제조사·제품 번호로 확정할 수 없다. 이를 확인하려면 생산 BOM이나 실제 실장 부품의 식별 기록이 필요하다. | - | O | O |
| h10 | Pro Micro 2026년 USB-C판에서는 D2랑 전원 점퍼 구성이 어떻게 바뀌었어? | wrong_period | Pro Micro 2026년 USB-C판의 D2와 전원 점퍼 변경 내용은 제공 자료에서 확인할 수 없다고 안내하는 것이 정답이다. 보유 자료는 질문에서 지정한 v13 NET이며 X1 값은 USB-ABIN&OUT이고 footprint는 USB-AB-MICRO-SMD-V03-IN&OUT이므로 요청한 USB-C 개정판 근거로 쓸 수 없다. NET의 2026-10-30 내보내기 날짜를 보드의 2026년 개정판 발행 증거로 해석하지 않으며 해당 USB-C판의 실존도 단정하지 않는다. | - | O | O |

## 3. 판단형: 꼼꼼히 (14건)

### e01 — 이 보드에서 D1은 왜 필요한 거야?

- 회로·대상: SparkFun Breadboard Supply · D1 · 조건: 전원은 J1 잭으로만 공급한다.
- Codex 판단: 관련, 확신 high
- Codex 정답: D1은 J1 전원 경로에 직렬로 놓인 역극성 보호 다이오드로 해석한다. S1이 도통하는 상태에서 J1.PWR → S1 → D1의 애노드(A)·캐소드(C) → F1 → RAW → U1.IN 순서로 정상 전원이 들어가며, J1 극성이 반대이면 D1이 역바이어스되어 뒤쪽 경로로 흐르는 전류를 제한한다. 이 설명은 J1 단독 공급 조건에 한정하며, D1 앞의 JP5나 다른 단자에서 공급하는 경우까지 보호한다고 보장하지 않는다.
- 이유: [문서] 넷리스트의 D1 극성과 연결 및 기준표 3.1절의 직렬 역극성 보호 조건이 일치한다. [추정] 역할은 연결에서 해석한 것이며, 역전압 정격 충족이나 실제 보호 성능을 시험한 결과는 아니다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/supply_breadboard.net, J1.PWR・S1.2・JP5.1 = Net-(S1-P); J1.GND・J1.GNDBREAK・JP5.2 = GND
  - netlists/supply_breadboard.net, D1(value=1N4001, footprint=import_input:DIODE-0.4); D1.A・S1.3 = Net-(S1-S); D1.C・F1.P$1 = Net-(F1-1)
  - netlists/supply_breadboard.net, F1(value=500mA).P$2・U1(value=LM317).IN = RAW; U1.OUT = VCC
  - 정답판정-기준표.md, 3.1절 역극성 보호(전원 경로에 직렬)
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### e02 — 모터를 끌 때 D3가 무슨 일을 하는 거야?

- 회로·대상: Adafruit MOSFET Driver · D3 · 조건: X1에 코일 부하인 모터를 연결한다.
- Codex 판단: 관련, 확신 high
- Codex 정답: D3는 X1에 연결한 코일 부하와 병렬인 플라이백 다이오드, 즉 스위치를 끌 때 코일 전류의 순환 경로를 만드는 다이오드로 해석한다. Q1이 꺼지면 /OUT 쪽 전압이 올라 D3가 도통하고, /OUT → D3.A → D3.C → VIN → 코일 → /OUT 방향으로 전류가 이어질 수 있어 Q1 드레인의 전압 상승을 제한한다. 코일 전류·전원 전압·PWM 조건이 없으므로 실제 스트레스나 보호 성능까지 보장하지 않는다.
- 이유: [문서] D3 애노드는 Q1 드레인 및 부하 하단 /OUT, 캐소드는 부하 상단 VIN에 연결되고 Q1 소스는 GND다. [추정] 기준표 3.3절과 이 연결에 따른 차단 직후 전류 경로 해석이며, 실측 동작은 아니다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/driver_mosfet.net, D3(value=1N400x/SM4002, footprint=SOD-123).A・Q1.3(D)・X1.L1.1・X1.L1.2 = /OUT; D3.C・X1.L2.1・X1.L2.2 = VIN; Q1.2(S) = GND; Q1.1(G) = /SIGNAL
  - 정답판정-기준표.md, 3.3절 플라이백: 코일과 병렬・캐소드가 전원 쪽, 차단 시 코일 전류가 다이오드로 이동
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### e04 — TSC 1N4148을 쓰면 전압이 얼마나 떨어져?

- 회로·대상: Adafruit MOSFET Driver · D3
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: TSC 1N4148의 상세 전기 특성 표에서 순방향 전압 VF는 IF = 10 mA, TJ = 25 °C, 펄스 폭 PW = 0.3 ms 조건에 최대 1 V이다. 이 값은 해당 시험 조건의 최댓값이며, 모든 전류에서 고정되는 전압 강하나 이 모터 회로의 실측값이 아니다. 실제 부하 전류와 온도를 모르면 실제 전압 강하를 확정할 수 없다.
- 이유: [문서] K2301 2쪽에서 1N4148에 지정된 IF=10 mA 행과 주석 1을 사용했다. 1쪽 요약의 IF=100 mA 표기는 상세표의 시험 전류와 달라 혼용하지 않았다.
- 메모: 1쪽 KEY PARAMETERS는 VF at IF=100mA=1V, 2쪽 상세표의 1N4148 행은 IF=10mA에서 MAX 1V다. 초안의 10mA 인용은 상세표와 일치하지만, 서로 다른 시험 전류 표기를 어떻게 채점할지 사람 확인이 필요하다. 본 답은 상세표의 명시 조건을 채택했다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - datasheets/1N4148 SERIES_K2301.txt, 2쪽, ELECTRICAL SPECIFICATIONS, Forward voltage의 1N4148 행(IF=10mA, TJ=25°C, VF MAX=1V), Notes 1(PW=0.3ms)
  - datasheets/1N4148 SERIES_K2301.txt, 1쪽, KEY PARAMETERS, VF at IF=100mA 행(1V)
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### e07 — TSC 1N4001의 정격 좀 알려 줘.

- 이미 정함: 비관련 유지 [결정 11-01 정운]. 다시 볼 필요 없음.

- 회로·대상: SparkFun Breadboard Supply · D1
- Codex 판단: 비관련(unknown_entity), 확신 medium · **사람 확인 필요**
- Codex 정답: 접미사 없는 TSC 1N4001의 정격은 제공 코퍼스에서 확인할 수 없다고 안내하는 것이 정답이다. 목록과 원문에서 확인되는 것은 1N4001G 및 목록상의 1N4001G-K이며, 이를 1N4001과 같은 제품이라고 밝힌 근거는 없다. 1N4001G의 정격을 질문의 1N4001 정격으로 옮겨 쓰지 않는다.
- 이유: [실측] CSV 1,360행의 parts 토큰 완전 일치 조회에서 1N4001은 0건, 1N4001G와 1N4001G-K는 각각 1건이다. [문서] P2104 1쪽 표 제목・열은 1N4001G~1N4007G로 명시된다. [추정] 명시적 동일성 근거가 없는 현재 자료에서는 비관련 unknown_entity 유지가 타당하다.
- 메모: TASK.md에서 사람 판정 대상으로 지정했다. 제안은 비관련 unknown_entity 유지다. G 접미사를 생략한 질의로 허용할지 평가 정책을 하정운이 정해야 하며, 제공 문서만으로 동일품이라고 단정할 수 없다.
- 기계 대조: 1N4001 목록에 없음
- 근거:
  - tsc_datasheet_list.csv, file・parts 열 전체 1,360개 데이터 행(헤더 제외); 1N4001 완전 일치 0건; 8행 1N4001G SERIES_P2104.pdf 및 9행 1N4001G-K SERIES_B2104.pdf
  - datasheets/1N4001G SERIES_P2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS의 1N4001G 열 및 FEATURES의 Glass passivated chip junction; 2쪽 ORDERING INFORMATION의 1N4xG 행・주석 1
  - netlists/supply_breadboard.net, D1(value=1N4001, footprint=import_input:DIODE-0.4); D1.A・S1.3 = Net-(S1-S); D1.C・F1.P$1 = Net-(F1-1)
  - SPEC.md, 3절 동일품: 같은 품번 또는 제조사가 같은 제품이라고 밝힌 품번
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### m01 — D1은 여기서 무슨 역할이야?

- 회로·대상: ATtiny85 dev board · D1
- Codex 판단: 관련, 확신 high
- Codex 정답: D1은 USB D- 신호선과 GND 사이에 연결된 제너 클램프, 즉 신호 전압을 제한하는 소자로 해석한다. D1의 1번 캐소드(K)는 J1.2(D-)와 같은 넷이고 2번 애노드(A)는 /GND에 연결되며, D2도 D+에 같은 방식으로 붙어 있다. 값의 3.6 Zener는 공칭 전압 표기이며 정확한 제조사·품번이나 모든 조건에서의 3.6 V 고정 동작을 보장하지 않는다.
- 이유: [문서] tiny 넷리스트에 D1의 극성・USB 데이터선・GND 연결 및 3.6 Zener 값이 명시된다. [추정] 기준표 3.4절에 따른 데이터선 제너 클램프 역할 해석이며, 직렬 전원 보호 경로와 다르다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/tiny_attiny85_dev.net, D1(value=3.6 Zener, footprint=Diode_THT:D_DO-34_SOD68_P7.62mm_Horizontal).1(K)・J1.2(D-)・R1.1・R3.2 = Net-(D1-K); D1.2(A) = /GND; R1(value=1K5).2 = /5V; R3(value=66).1 = /PB3
  - netlists/tiny_attiny85_dev.net, D2(value=3.6 Zener).1(K)・J1.3(D+) = Net-(D2-K); D2.2(A)・J1.4(GND) = /GND
  - 정답판정-기준표.md, 3.4절 제너 클램프: 제너 계열 값, 한쪽 GND・다른 쪽 신호 넷
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### m02 — USB로 전원을 넣으면 D3랑 레귤레이터를 어떤 순서로 거치는 거야?

- 회로·대상: Franzininho DIY · D3 · 조건: USB만 연결하고 J1에는 전원을 연결하지 않는다.
- Codex 판단: 관련, 확신 high
- Codex 정답: USB만 공급하면 X1.VBUS → D3.A → D3.C → 5V 레일 → IC1.8 순서로 연결된다. U1(L78L05)의 출력 1번 핀도 같은 5V 레일에 붙지만, 입력 3번 핀은 별도 J1.3 넷에 연결되어 USB 공급 경로에서 U1을 직렬로 먼저 통과하지 않는다. 이것은 연결에 따른 경로 설명이며 U1의 역류나 실제 전압·동작을 보장하는 설명은 아니다.
- 이유: [문서] Franzininho 원문 NET의 D3와 USB VBUS 및 U1 입출력 노드를 직접 대조했다. [추정] J1 미공급 조건에서 가능한 주 공급 경로를 설명하며, 레귤레이터의 보장 특성은 제공되지 않았다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/franz_c09.net, D3(value=1N4148).A・X1.VBUS = Net-(D3-PadA); D3.C・U1.1・IC1.8 = 5V; U1(value=L78L05_TO92).3・J1.3 = Net-(J1-Pad3); U1.2 = GND
  - netlists/franz_c09.net, libparts의 MC78L05_TO92 및 alias L78L05_TO92: 핀 1=VO, 2=GND, 3=VI; nets의 5V 및 Net-(J1-Pad3)
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### m04 — D1 자리에 TSC BZT52C3V6을 그대로 납땜해도 돼?

- 회로·대상: ATtiny85 dev board · D1
- Codex 판단: 관련, 확신 high
- Codex 정답: 원래 D1은 DO-34 계열의 7.62 mm 피치 스루홀 footprint이고, TSC BZT52C3V6은 표면 실장 SOD-123F이므로 기존 패드에 그대로 교체 납땜할 수 있다고 답하면 안 되며 기판 수정이 필요하다. 원래 D1은 1번이 캐소드·2번이 애노드이고 후보는 캐소드 밴드 표시이므로, 기판을 수정할 때 후보 권장 패드와 극성을 확인해야 한다. 전기적 대체 판정은 문서로 확인 안 됨(NOT_VERIFIED)으로, 원래 상세 품번·소비 전력·정전용량과 실제 제너 전류가 없어 제너 필수 조건을 모두 비교할 수 없다. 후보 문서에는 정전용량 전형값 그래프는 있지만 USB 데이터선 조건을 만족한다고 보장할 C3V6의 최대 정전용량 표 값은 제시되지 않는다.
- 이유: [문서] 원래 footprint와 G1804의 패키지・권장 패드를 대조했다. 기준표 3.4절은 USB 데이터선에서 CJ 비교를 요구하고, 5쪽 Typical Capacitance는 보장 최댓값이 아니다. 패키지 차이는 SPEC에 따라 전기 판정과 별도로 표시했다.
- 메모: 정답판정-기준표.md 6절의 CJ가 없다는 표현은 범위를 좁혀야 한다. G1804 5쪽에 Fig.5 Typical Capacitance가 실제로 있으며, 부족한 것은 원래 D1과 비교할 수 있는 후보의 보장 최댓값 및 원래 CJ다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/tiny_attiny85_dev.net, D1(value=3.6 Zener, footprint=Diode_THT:D_DO-34_SOD68_P7.62mm_Horizontal).1(K)・J1.2(D-)・R1.1・R3.2 = Net-(D1-K); D1.2(A) = /GND; R1(value=1K5).2 = /5V; R3(value=66).1 = /PB3
  - datasheets/BZT52C2V4 SERIES_G1804.txt, 1쪽, KEY PARAMETERS의 Package 및 MECHANICAL DATA의 Polarity 행
  - datasheets/BZT52C2V4 SERIES_G1804.txt, 6쪽, PACKAGE OUTLINE DIMENSION의 SOD-123F A~F 행 및 SUGGEST PAD LAYOUT의 C・G・X・X1・Y 행
  - datasheets/BZT52C2V4 SERIES_G1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS의 BZT52C3V6 행(CJ 열 없음); 5쪽 CHARACTERISTICS CURVES의 Fig.5 Typical Capacitance
  - 정답판정-기준표.md, 3.4절 제너 클램프: VZ・PD 필수, 실제 Iz/IZT 비교 및 USB 데이터선 CJ 조건; 5절 5번 두 배 이상 전류 차이 시 확인 안 됨
  - SPEC.md, 3절 대체 판정 5종・원래 품번 미상 제한・패키지 차이 별도 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### m05 — D3 대신 TSC 1N4148을 쓰려는데 전류를 얼마나 흘려도 돼?

- 회로·대상: Franzininho DIY · D3
- Codex 판단: 관련, 확신 high
- Codex 정답: TSC 1N4148의 절대 최대 정격은 TA = 25 °C에서 연속 순방향 전류 IF = 150 mA, 반복 피크 IFRM = 450 mA이다. 비반복 사각파 서지 IFSM = 2 A는 t = 1 µs 조건이며 연속 전류로 쓸 수 없다. 같은 조건의 소비 전력 한도 PD = 500 mW와 전형 접합-주변 열저항 RθJA = 240 °C/W도 함께 검토해야 하므로, 실제 부하 전류·온도·방열 조건 없이 150 mA를 안전 사용 전류로 보장하지 않는다. D3 교체의 최종 판정은 전원 최대 전압·부하 전류·원래 제품의 상세 사양이 부족하여 문서로 확인 안 됨(NOT_VERIFIED)이다.
- 이유: [문서] K2301 1쪽의 연속・반복 피크・비반복 서지 항목과 열 성능을 구분했다. [추정] D3는 USB와 5V 레일 사이의 역류 방지 경로로 해석되므로 기준표 3.2절을 적용하되, 넷리스트의 같은 1N4148 표기만으로 실제 제조사가 TSC라고 확정하지 않았다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - datasheets/1N4148 SERIES_K2301.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted), Forward current IF・Repetitive peak forward current IFRM・Non-repetitive sqare wave peak forward surge current(t=1µs) IFSM・Power dissipation PD 행; THERMAL PERFORMANCE의 RθJA TYP 행
  - netlists/franz_c09.net, D3(value=1N4148).A・X1.VBUS = Net-(D3-PadA); D3.C・U1.1・IC1.8 = 5V; U1(value=L78L05_TO92).3・J1.3 = Net-(J1-Pad3); U1.2 = GND
  - 정답판정-기준표.md, 3.2절 역류 방지: VRRM ≥ 반대쪽 전원 최대 전압×1.25, IF(AV) 또는 IF ≥ Imax/0.7, 같은 시험 전압・온도의 IR 비교, 조건부 VF
  - SPEC.md, 3절 대체 판정 5종・원래 품번 미상 제한・패키지 차이 별도 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### m08 — 이 보드 D1은 어느 회사 제품이고 몇 V짜리야?

- 회로·대상: Franzininho DIY · D1
- Codex 판단: 비관련(missing_attribute), 확신 medium · **사람 확인 필요**
- Codex 정답: 제공된 Franzininho D1 자료로는 실제 제조사와 제너 전압 등급을 확인할 수 없다고 안내하는 것이 정답이다. 대상 넷리스트의 D1 값은 전압 접미사가 없는 BZT52이고 footprint도 Franzininho:DIODE-BZT52이므로, 3.6 V나 특정 회사를 보충할 수 없다. 다른 ATtiny85 dev 회로의 3.6 Zener 표기나 TSC 후보 데이터시트를 이 보드 실장품의 제조사·전압 근거로 대신 쓰지 않는다.
- 이유: [문서] 질문의 source.circuit_id=franz 및 franz_c09.net의 D1 value・libsource를 확인했으며 전압 표기는 없다. [실측] CSV에는 BZT52C3V6 등 여러 전압의 TSC 품번이 있지만 접미사 없는 BZT52 토큰은 0건이다. 목록은 후보군 자료이며 이 보드의 제조사・BOM 증빙이 아니다.
- 메모: TASK.md가 사람 판정 대상으로 지정했다. 제안은 비관련 missing_attribute 유지다. TASK의 제조사는 없고 값에 전압만 있다는 설명 및 초안 3절의 3.6 Zener 전제와 달리, 실제 대상 franz_c09.net은 BZT52만 표기한다. 3.6 Zener는 tiny_attiny85_dev.net의 D1이며 다른 보드이므로, 원문 기준 답변을 채택할지 문항 대상을 바꿀지 사람이 확인해야 한다.
- 기계 대조: -
- 근거:
  - netlists/franz_c09.net, D1(value=BZT52, footprint=Franzininho:DIODE-BZT52, libsource part=DIODE-ZENER).C・X1.D-・R1.P$1・R3.P$2 = Net-(D1-PadC); D1.A = GND; 제조사・전압 접미사 필드 없음
  - netlists/tiny_attiny85_dev.net, D1 value=3.6 Zener; D1.1(K)=Net-(D1-K), D1.2(A)=/GND(질문 대상과 다른 회로)
  - tsc_datasheet_list.csv, 130행 및 전체 parts 조회: BZT52C3V6 등 다수 전압 포함, BZT52 정확 일치 0건
  - datasheets/BZT52C2V4 SERIES_G1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS의 여러 전압 품번 행 및 3쪽 ORDERING INFORMATION 주석의 xxx 전압 지정
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### h01 — USB로 쓸 때 SJ1을 붙이거나 떼면 전원 경로가 어떻게 달라져?

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: USB만 연결하고 RAW에는 전원을 연결하지 않는다.
- Codex 판단: 관련, 확신 high
- Codex 정답: SJ1을 열면 USB VBUS → F1 → D2 → /RAW → U2.IN → U2.OUT → VCC 경로로 공급된다. SJ1을 닫으면 F1 뒤 Net-(D2-A)가 VCC와 직접 이어져 USB → F1 → SJ1 → VCC의 우회 경로가 생기고, 이 직접 경로는 D2와 U2를 직렬로 거치지 않는다. 닫힌 경우에도 D2·/RAW·U2의 배선은 남으며, 두 상태의 실제 전압·전류 분담이나 제작자 권장 여부를 보장하지 않는다. 이는 NET에서 SJ1 두 핀의 개방·단락을 가정해 비교한 것이며 실제 점퍼 상태 변경을 측정한 결과는 아니다.
- 이유: [문서] SJ1.1은 D2 애노드 및 F1 뒤쪽 넷, SJ1.2는 VCC이고 U2 입력은 /RAW, 출력은 VCC다. [추정] 해당 두 핀의 개방・단락에 따른 경로 비교이며, value=Closed for 5V Board만으로 두 가상 상태의 실제 보드 동작을 검증했다고 볼 수 없다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/pro_micro_v13.net, X1.VBUS1・F1.1・U3.2(UVCC)・U3.7(VBUS) = UVCC; F1(value=500mA).2・D2.2(A)・SJ1.1 = Net-(D2-A)
  - netlists/pro_micro_v13.net, D2(value=DIODESOD, footprint=import_input:SOD-323).1(C)・JP6.1(RAW)・U2.1(IN)・U2.3(EN) = /RAW; D2.2(A) = Net-(D2-A)
  - netlists/pro_micro_v13.net, U2(value=MIC5219).5(OUT)・SJ1.2・JP6.4・U3.14(VCC) = VCC; U2.2(GND) = GND
  - netlists/pro_micro_v13.net, SJ1(value=Closed for 5V Board, footprint=import_input:SJ_2S).1 = Net-(D2-A), .2 = VCC; 두 핀의 개방・단락을 가정하여 경로 비교
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### h02 — SJ1을 열어 두면 USB 전원이랑 RAW 전원이 D2를 지나는 방식이 달라?

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: USB 단독 공급과 RAW 단독 공급을 비교한다.
- Codex 판단: 관련, 확신 high
- Codex 정답: SJ1 개방·USB 단독 공급에서는 USB → F1 → D2의 2번 애노드 → 1번 캐소드 → /RAW → U2 → VCC로 흐르는 경로다. RAW 단독 공급에서는 JP6.1의 /RAW → U2.IN → U2.OUT → VCC로 공급하므로 D2를 순방향으로 지나야 하는 경로가 아니다. 이때 D2는 /RAW 쪽 캐소드에서 USB 쪽 애노드로의 역방향 경로를 막는 방향으로 배치되어 있지만, 유한한 누설이나 U2·U3 등 다른 경로까지 포함한 보드 전체의 완전한 역류 차단을 보장하지 않는다.
- 이유: [문서] D2 극성과 RAW 핀 및 U2 연결을 대조했다. [추정] 기준표 3.2절의 전원 간 역류 방지 역할로 해석하되, 두 전원이 동시에 연결되는 경우의 실측 동작으로 확대하지 않았다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/pro_micro_v13.net, X1.VBUS1・F1.1・U3.2(UVCC)・U3.7(VBUS) = UVCC; F1(value=500mA).2・D2.2(A)・SJ1.1 = Net-(D2-A)
  - netlists/pro_micro_v13.net, D2(value=DIODESOD, footprint=import_input:SOD-323).1(C)・JP6.1(RAW)・U2.1(IN)・U2.3(EN) = /RAW; D2.2(A) = Net-(D2-A)
  - netlists/pro_micro_v13.net, U2(value=MIC5219).5(OUT)・SJ1.2・JP6.4・U3.14(VCC) = VCC; U2.2(GND) = GND
  - netlists/pro_micro_v13.net, SJ1(value=Closed for 5V Board, footprint=import_input:SJ_2S).1 = Net-(D2-A), .2 = VCC; 두 핀의 개방・단락을 가정하여 경로 비교
  - 정답판정-기준표.md, 3.2절 역류 방지: 한 전원에서 다른 전원 넷으로 직렬 연결, IR 필수
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### h03 — D2를 TSC 1N5819로 바꾸면 VCC에는 최소 몇 V가 나와?

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: USB 5V 공급, SJ1 개방 상태다.
- Codex 판단: 관련, 확신 high
- Codex 정답: VCC 최솟값은 제공 자료만으로 계산할 수 없으며, SJ1 개방에서 경로는 USB 5 V → F1 → 후보 D2 → /RAW → U2(MIC5219) → VCC이다. TSC 1N5819의 VF 최댓값 0.60 V는 IF = 1 A, TJ = 25 °C, PW = 0.3 ms 조건이므로 이를 빼서 VCC가 최소 4.4 V라고 답하면 안 된다. 실제 부하 전류·온도·퓨즈 전압 강하·U2의 출력 설정과 최소 입력 여유 및 출력 보장값이 필요하며, 제공 자료에는 U2 데이터시트가 없다. D2의 최종 대체 판정도 원래 품번·누설 비교값 등 필수 근거가 부족해 문서로 확인 안 됨(NOT_VERIFIED)이다.
- 이유: [문서] 후보의 VF는 특정 전류・접합 온도의 상한이고, VCC는 다이오드 직후가 아니라 레귤레이터 출력 넷이다. [실측] CSV 전체 file・parts에서 MIC5219는 0건이다. [문서] 기준표 3.2절과 SPEC 3절상 누락된 조건을 임의 보충하여 동일품・사양 동등・역할상 충분으로 판정할 수 없다.
- 기계 대조: 원문에 없는 숫자: 4.4
- 근거:
  - netlists/pro_micro_v13.net, X1.VBUS1・F1.1・U3.2(UVCC)・U3.7(VBUS) = UVCC; F1(value=500mA).2・D2.2(A)・SJ1.1 = Net-(D2-A)
  - netlists/pro_micro_v13.net, D2(value=DIODESOD, footprint=import_input:SOD-323).1(C)・JP6.1(RAW)・U2.1(IN)・U2.3(EN) = /RAW; D2.2(A) = Net-(D2-A)
  - netlists/pro_micro_v13.net, U2(value=MIC5219).5(OUT)・SJ1.2・JP6.4・U3.14(VCC) = VCC; U2.2(GND) = GND
  - netlists/pro_micro_v13.net, SJ1(value=Closed for 5V Board, footprint=import_input:SJ_2S).1 = Net-(D2-A), .2 = VCC; 두 핀의 개방・단락을 가정하여 경로 비교
  - datasheets/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS, Forward voltage의 1N5819 행(IF=1A, TJ=25°C, MAX=0.60V), Notes 1(PW=0.3ms)
  - tsc_datasheet_list.csv, file・parts 열 전체 1,360개 데이터 행(헤더 제외); MIC5219 조회 0건
  - 정답판정-기준표.md, 3.2절 역류 방지: VRRM ≥ 반대쪽 전원 최대 전압×1.25, IF(AV) 또는 IF ≥ Imax/0.7, 같은 시험 전압・온도의 IR 비교, 조건부 VF
  - SPEC.md, 3절 대체 판정 5종・원래 품번 미상 제한・패키지 차이 별도 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): X — irrelevant / missing_attribute. 질문이 요구한 VCC 최솟값을 제공 자료로 확정할 수 없으므로, 필요한 속성이 없는 비관련 문항으로 판단함(2026-11-02).
- 재훈 재검토 메모(2026-11-02): 기존 O를 재검토해 irrelevant / missing_attribute로 의견 변경. 전원 경로나 후보 VF를 설명할 수 있어도 요청한 VCC 최솟값의 근거를 대신하지 못한다. n14처럼 요구한 보장값이 없는 문항과 같은 기준을 적용한다. 1차 relevant 판정과의 이견은 최종 합의 필요. 이 변경을 최종 반영하면 현재 25/25는 관련 24·비관련 26이 되므로, 동결 전 구성 요건을 별도로 재검토해야 한다.

### h04 — D2를 TSC 1N5819로 바로 바꿔 달아도 돼?

- 회로·대상: SparkFun Pro Micro v13 · D2
- Codex 판단: 관련, 확신 high
- Codex 정답: D2의 원래 footprint는 표면 실장 SOD-323이고 TSC 1N5819는 리드형 DO-204AL(DO-41)이므로 그대로 바꿔 다는 호환품이라고 답할 수 없으며 기판 수정이 필요하다. 원래 D2는 1번이 캐소드·2번이 애노드이고 후보는 캐소드 밴드로 방향을 표시하므로 수정 시 패드 배치와 극성을 맞춰야 한다. 전기적 대체 판정은 문서로 확인 안 됨(NOT_VERIFIED)으로, 원래 DIODESOD는 주문 품번이 아니고 RAW 최대 전압·실제 전류·같은 조건의 원래 IR 및 조건부 VF 비교 자료가 없다. 패키지 불일치는 전기 판정과 별도로 표시하며 실제 동작을 보장하지 않는다.
- 이유: [문서] SOD-323과 DO-41의 불일치는 확인된다. SPEC 3절은 원래 품번이 없을 때 동일품・사양 동등을 내지 않도록 하며 패키지는 별도로 표시한다. 기준표 3.2절의 요구값・비교값도 부족하다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/pro_micro_v13.net, D2(value=DIODESOD, footprint=import_input:SOD-323).1(C)・JP6.1(RAW)・U2.1(IN)・U2.3(EN) = /RAW; D2.2(A) = Net-(D2-A)
  - netlists/pro_micro_v13.net, X1.VBUS1・F1.1・U3.2(UVCC)・U3.7(VBUS) = UVCC; F1(value=500mA).2・D2.2(A)・SJ1.1 = Net-(D2-A)
  - datasheets/1N5817 SERIES_H2104.txt, 1쪽, KEY PARAMETERS의 Package 행 및 MECHANICAL DATA의 Case・Polarity 행; 5쪽 PACKAGE OUTLINE DIMENSIONS의 DO-204AL(DO-41) 표기
  - 정답판정-기준표.md, 3.2절 역류 방지: VRRM ≥ 반대쪽 전원 최대 전압×1.25, IF(AV) 또는 IF ≥ Imax/0.7, 같은 시험 전압・온도의 IR 비교, 조건부 VF
  - SPEC.md, 3절 대체 판정 5종・원래 품번 미상 제한・패키지 차이 별도 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### h05 — TSC 1N5817이랑 1N5819는 같은 계열인데 D2에는 아무거나 써도 돼?

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: RAW만 공급하고 SJ1은 열어 둔다.
- Codex 판단: 관련, 확신 high
- Codex 정답: RAW 단독 공급·SJ1 개방에서 D2는 /RAW 캐소드에서 USB 쪽 애노드로 역바이어스되는 방향이므로 두 후보의 역전압 정격을 구분해야 한다. TA = 25 °C의 절대 최대 정격에서 1N5817의 VRRM은 20 V, 1N5819는 40 V이고 순방향 전류 IF는 둘 다 1 A이다. VF 최댓값도 IF = 1 A, TJ = 25 °C, PW = 0.3 ms에서 각각 0.45 V와 0.60 V로 다르다. RAW 최대 전압과 실제 역전압·부하 전류 및 원래 IR 등 필수 근거가 부족해 두 후보 모두 최종 대체 판정은 문서로 확인 안 됨(NOT_VERIFIED)이며 같은 계열이라는 이유로 아무거나 써도 된다고 답하지 않는다.
- 이유: [문서] 회로는 D2 캐소드가 RAW에 연결되고, H2104의 두 품번 열은 서로 다른 VRRM・VF를 제시한다. 기준표 3.2절은 반대쪽 전원의 최대 전압에 1.25배 여유 및 전류・동일 시험 조건 IR 비교를 요구하지만 최대 RAW 전압과 원래 제품 사양이 없다. 두 후보의 IR도 각자의 rated VR 시험이므로 같은 시험 전압이라고 자동 간주하지 않는다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/pro_micro_v13.net, X1.VBUS1・F1.1・U3.2(UVCC)・U3.7(VBUS) = UVCC; F1(value=500mA).2・D2.2(A)・SJ1.1 = Net-(D2-A)
  - netlists/pro_micro_v13.net, D2(value=DIODESOD, footprint=import_input:SOD-323).1(C)・JP6.1(RAW)・U2.1(IN)・U2.3(EN) = /RAW; D2.2(A) = Net-(D2-A)
  - netlists/pro_micro_v13.net, U2(value=MIC5219).5(OUT)・SJ1.2・JP6.4・U3.14(VCC) = VCC; U2.2(GND) = GND
  - netlists/pro_micro_v13.net, SJ1(value=Closed for 5V Board, footprint=import_input:SJ_2S).1 = Net-(D2-A), .2 = VCC; 두 핀의 개방・단락을 가정하여 경로 비교
  - datasheets/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS의 1N5817・1N5819 열: VRRM 및 Forward current IF 행
  - datasheets/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS의 Forward voltage 1N5817・1N5819 행 및 Reverse current @ rated VR 행; Notes 1(PW=0.3ms)・2(PW=30ms)
  - 정답판정-기준표.md, 3.2절 역류 방지: VRRM ≥ 반대쪽 전원 최대 전압×1.25, IF(AV) 또는 IF ≥ Imax/0.7, 같은 시험 전압・온도의 IR 비교, 조건부 VF
  - SPEC.md, 3절 대체 판정 5종・원래 품번 미상 제한・패키지 차이 별도 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

---

# 기존 추가 20건 중 본편 19건(n13 예비 이관)

- 출제(Codex 1회차)와 정답(Codex 2회차, 출제 의도를 지운 문항만 받음)을 따로 돌렸다. 관련/비관련과 비관련 종류는 20건 모두 출제 의도와 같았다.
- 보는 방법은 위 30건과 같다.

## 1. 숫자형: 기계 대조로 끝 (2건)

| 문항 | 질문 | Codex 정답 | 기계 대조 |
|---|---|---|---|
| n03 | D3 후보로 보는 TSC 1N4148의 역회복 시간은 얼마고, 어떤 시험 조건에서 나온 값이야? | TSC 1N4148의 역회복 시간(trr)은 최댓값 4ns이다. 시험 조건은 IF=10mA, VR=6V, RL=100Ω, IRR=1mA이고, 해당 ELECTRICAL SPECIFICATIONS 표의 기본 주변 온도는 TA=25°C이다. 이 값은 질문의 실제 D3 구동 조건에서 같은 동작을 보장하는 값은 아니다. | 원문에 없는 숫자 없음 |
| n05 | D2 후보인 TSC BZT52C3V6의 허용 소비전력과 접합 온도 상한은 얼마야? | TSC BZT52C3V6의 허용 소비전력(PD)은 주변 온도 TA=25°C에서 500mW이고, 접합 온도(TJ)의 상한은 +150°C이다. 문서의 전체 접합 온도 범위는 -65~+150°C이며, 500mW는 ABSOLUTE MAXIMUM RATINGS의 값으로 실제 사용 온도에 따른 디레이팅을 확인해야 한다. 이 정격 조회만으로 D2의 대체 적합성이나 같은 동작을 보장하지 않는다. | 원문에 없는 숫자 없음 |

## 2. 비관련: 훑어보기 (11건)

| 문항 | 질문 | 종류 | Codex 결론 | 기계 확인 | 정운 | 재훈 |
|---|---|---|---|---|---|---|
| n09 | D3 후보로 BAT85를 보고 있는데, 반복 피크 역전압과 순방향 전류 정격은 얼마야? | unknown_entity | 자료 부재 안내가 정답이다. BAT85는 제공된 코퍼스에서 확인되지 않아 반복 피크 역전압과 순방향 전류 정격을 답할 수 없다고 안내한다. | BAT85 목록에 없음 | O | O |
| n10 | D1 후보로 1N5711을 검토 중인데, 데이터시트의 정격과 패키지를 알려 줘. | unknown_entity | 자료 부재 안내가 정답이다. 1N5711은 제공된 코퍼스에 없으므로 정격과 패키지를 확인할 수 없다고 안내한다. | 1N5711 목록에 없음 | O | O |
| n11 | D3 대체 후보 1N60P의 역전압과 순방향 전류 정격을 알려 줘. | unknown_entity | 자료 부재 안내가 정답이다. 1N60P는 제공된 코퍼스에 없어 역전압과 순방향 전류 정격을 확인할 수 없다고 안내한다. | 1N60P 목록에 없음 | O | O |
| n12 | D3에 쓸 후보 1N34A는 어느 패키지이고 역전압 정격이 얼마야? | unknown_entity | 자료 부재 안내가 정답이다. 1N34A는 제공된 코퍼스에 없어 패키지와 역전압 정격을 확인할 수 없다고 안내한다. | 1N34A 목록에 없음 | O | O |
| n14 | TSC BZT52C3V6의 G1804판 데이터시트에서 역바이어스 1V일 때 보장하는 정전용량 최댓값은 몇 pF야? | missing_attribute | 자료 부재 안내가 정답이다. BZT52C3V6의 G1804판은 코퍼스에 있지만 역바이어스 1V에서 보장하는 정전용량 최댓값은 제시되어 있지 않다. 5쪽 Fig.5의 1V Bias 곡선은 전형값(Typical Capacitance)이므로 이를 읽어 보장 최댓값 몇 pF라고 답해서는 안 된다. | - | O | O |
| n15 | TSC SS34의 Q2611 개정판 기준으로 D3 후보의 역전압과 순방향 전류 정격을 알려 줘. | wrong_period | 요청한 개정판의 자료 부재 안내가 정답이다. SS34 자체는 코퍼스에 있으나 Q2611판은 없으므로 그 개정판 기준의 역전압과 순방향 전류 정격을 확인할 수 없다고 안내한다. 보유한 Q2412판의 값을 Q2611판 값처럼 답해서는 안 된다. | - | O | O |
| n16 | TSC 1N4148의 K2611 개정판에서 D3에 쓸 때 참고할 순방향 전류 한도와 시험 조건을 알려 줘. | wrong_period | 요청한 개정판의 자료 부재 안내가 정답이다. TSC 1N4148은 코퍼스에 있지만 K2611판은 없으므로 그 판의 순방향 전류 한도와 시험 조건을 확인할 수 없다고 안내한다. K2301판의 수치를 K2611판의 수치로 대체해서는 안 된다. | - | O | O |
| n17 | TSC 1N5819의 H2611 개정판에서는 D1 후보의 순방향 전압 최댓값을 어떻게 정하고 있어? | wrong_period | 요청한 개정판의 자료 부재 안내가 정답이다. TSC 1N5819는 코퍼스에 있지만 H2611판은 없으므로 그 판의 순방향 전압 최댓값과 결정 조건을 확인할 수 없다고 안내한다. H2104판의 값을 요청한 H2611판 값으로 제시해서는 안 된다. | - | O | O |
| n18 | D3 후보인 TSC SS34를 지금 국내에서 살 수 있는 판매처와 재고 수량, 개당 가격을 찾아 줘. | out_of_domain | 범위 밖 요청에 대한 거절이 정답이다. 현재 국내 판매처·실시간 재고 수량·개당 가격 조회는 SPEC 1절의 하지 않는 일에 해당하며, 제공된 정적 데이터시트로 현재 구매 정보를 확인할 수 없다고 안내한다. | - | O | O |
| n19 | U2 AMS1117-3.3을 발열이 적은 다른 레귤레이터로 바꾸려는데, 같은 자리에 달 수 있는 제품을 골라 줘. | out_of_domain | 범위 밖 요청에 대한 거절이 정답이다. U2 AMS1117-3.3은 다이오드가 아닌 레귤레이터이므로 현재 서비스의 부품 대체 판정 대상이 아니며, 같은 자리에 달 수 있는 저발열 대체 제품을 추천하지 않는다. | - | O | O |
| n20 | D3용 TSC 1N4148을 100개 주문하고 결제까지 진행해 줘. | out_of_domain | 범위 밖 요청에 대한 거절이 정답이다. 실제 주문·결제는 SPEC 1절에서 제외하므로 TSC 1N4148 100개의 주문이나 결제를 진행할 수 없다고 안내한다. | - | O | O |

## 3. 판단형: 꼼꼼히 (6건)

### n01 — D3에 달아 둔 TSC 1N5819 대신 TSC 1N5817을 써도 이 릴레이의 플라이백 역할을 할 수 있어?

- 회로·대상: Adafruit MOSFET Driver · D3 · 조건: D3는 앞서 TSC 1N5819로 교체해 사용 중이다. / X1에는 최대 전원 전압 12V, 정상 코일 전류 80mA인 릴레이를 연결한다. / PWM 없이 단발로 켜고 끈다. / 차단 시 다이오드 전류는 피크 80mA, 폭 8.3ms의 단발 반정현파이며 접합 온도는 25°C이다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: 데이터시트의 TA=25°C 서지 정격을 적용할 수 있다는 확인을 전제로, 판정 초안은 역할상 충분(ROLE_SUFFICIENT)이다. 1N5817의 반복 피크 역전압(VRRM)은 20V로 필요한 12V × 1.25 = 15V 이상이고, 비반복 피크 순방향 서지전류(IFSM)는 정격 부하에 중첩한 8.3ms 단발 반정현파에서 30A로 질문의 피크 80mA보다 크다. PWM이 없어 역회복 시간 조건은 발동하지 않고 두 품번 모두 DO-204AL(DO-41)이지만, 원래 1N5819의 VRRM 40V에는 못 미쳐 사양 동등은 아니다. 질문은 TJ=25°C만 주므로 TA 조건을 확인하지 못하면 문서로 확인 안 됨(NOT_VERIFIED)으로 남겨야 하며, 같은 동작은 보장하지 않는다.
- 이유: 정답판정-기준표 3.3의 플라이백 필수 조건인 VRRM과 IFSM을 만족하지만 원래 주요 정격 전체를 같거나 넘지는 않는다. 넷리스트에서 D3는 X1의 양단과 병렬이고 캐소드가 VIN이다. 질문의 기존 TSC 1N5819 설치 조건을 넷리스트의 오래된 부품 값보다 우선한다.
- 메모: IFSM 표의 기본 온도는 주변 온도 TA=25°C이고 질문은 접합 온도 TJ=25°C만 명시한다. 엄격히 같은 시험 온도 조건을 요구할 때의 ROLE_SUFFICIENT 확정 여부를 확인해야 하며, TA 조건이 확인되지 않는다고 판단하면 문서로 확인 안 됨(NOT_VERIFIED)으로 조정한다. 넷리스트의 SOD-123과 달리 질문상 기존 설치품과 후보는 모두 DO-41이므로 설치 상태도 확인한다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted), Repetitive peak reverse voltage의 1N5817=20V·1N5819=40V 및 Surge peak forward current, 8.3ms single half sine wave superimposed on rated load=30A 행
  - corpus_txt/1N5817 SERIES_H2104.txt, 2쪽, ORDERING INFORMATION, 1N581x의 PACKAGE=DO-204AL(DO-41) 행 및 주1
  - netlists/driver_mosfet.net, D3 핀 A=/OUT·핀 C=VIN; X1 핀 L1.1·L1.2=/OUT·핀 L2.1·L2.2=VIN
  - 정답판정-기준표.md, 3.3 플라이백; SPEC.md, 3절 대체 판정 5종
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): X — NOT_VERIFIED. 질문에 TA 조건이 없으므로 이를 임의로 보완하지 않고, 주어진 정보만으로는 역할상 충분을 확정할 수 없다고 판단함(2026-11-02).
- 재훈 재검토 메모(2026-11-02): 기존 O를 재검토해 NOT_VERIFIED로 의견 변경. 질문의 TJ=25°C와 문서 정격의 TA=25°C를 같은 조건으로 간주하지 않는다. 질문은 유지하며, 1차 ROLE_SUFFICIENT 판정과의 이견은 최종 합의 필요.

### n02 — D3를 TSC BAS70으로 바꿔도 이 릴레이를 끌 때 코일 전류를 받아 줄 수 있어?

- 회로·대상: Adafruit MOSFET Driver · D3 · 조건: X1에는 최대 전원 전압 12V, 정상 코일 전류 150mA인 릴레이를 연결한다. / PWM 없이 켜고 끄며 주변 온도는 25°C이다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: 초안 기준 판정은 불충족(NOT_SUFFICIENT)이다. BAS70은 TA=25°C에서 VRRM 70V로 필요한 15V 이상이지만, 순방향 전류(IF) 70mA와 비반복 서지전류(IFSM) 100mA(t=1s)는 모두 코일 정상 전류 150mA보다 작아 문서에 적힌 전류 정격으로는 필수 조건을 만족하지 못한다. 차단 펄스의 폭과 파형이 주어지지 않았으므로 더 짧은 펄스에서 150mA를 허용한다고 추정해서는 안 된다. 후보는 SOT-23이고 기존 넷리스트는 SOD-123이므로 기판 수정 필요를 별도로 표시하며, 같은 동작은 보장하지 않는다.
- 이유: 정답판정-기준표 3.3은 IF(AV) 또는 IFSM이 코일 정상 전류 이상이어야 하며, 명시된 BAS70 IFSM은 100mA이다. 기준표 1절에 따라 필수 조건 불충족을 다른 미확인 조건보다 먼저 처리한다. 다만 t=1s 정격과 질문의 미지정 차단 펄스 조건을 비교하는 한계는 사람 검토 대상으로 남긴다.
- 메모: 차단 펄스의 폭·파형이 없고 데이터시트는 1쪽 IFSM에 t=1s, 3쪽 Fig.2에 8.3ms 단발 반정현파를 적어 조건 차이가 있다. 문서에 적힌 100mA 한도로 불충족을 먼저 적용한 초안이며, 조건 비교 불가를 우선해야 하는지 하정운이 확인한다. IF=70mA는 IF(AV)라고 바꿔 쓰지 않는다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - corpus_txt/BAS70 SERIES_G2606.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted), Repetitive peak reverse voltage=70V·Forward current=70mA·Non-repetitive peak forward surge current @ t=1s=100mA 행 및 MECHANICAL DATA의 Case=SOT-23
  - corpus_txt/BAS70 SERIES_G2606.txt, 3쪽, CHARACTERISTICS CURVES, Fig.2 Maximum Non-Repetitive Peak Forward Surge Current Per Leg의 8.3ms single half sine wave 표기
  - netlists/driver_mosfet.net, D3 핀 A=/OUT·핀 C=VIN 및 footprint=SOD-123; X1 핀 L1.1·L1.2=/OUT·핀 L2.1·L2.2=VIN
  - 정답판정-기준표.md, 1절 판정 순서 및 3.3 플라이백; SPEC.md, 3절 패키지 차이 표시
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): X — NOT_VERIFIED. 차단 펄스의 폭·파형이 주어지지 않아 데이터시트의 t=1s 서지 정격과 같은 조건으로 비교할 수 있는지 확인되지 않으므로, 불충족을 확정하기보다 문서로 확인 안 됨으로 판단함(2026-11-02).
- 재훈 재검토 메모(2026-11-02): 기존 O를 재검토해 NOT_VERIFIED로 의견 변경. 사용 가능성을 입증하지 못한 것과 불충족이 입증된 것을 구분한다. 관련/비관련은 이번에 변경하지 않으며, 사용자 조건 부족을 코퍼스 속성 부족(missing_attribute)과 어떻게 구분할지는 n01과 함께 별도 합의가 필요하다. 1차 NOT_SUFFICIENT 판정과의 이견은 최종 합의 필요.

### n04 — D2를 TSC BZT52C5V1로 바꿔도 원하는 전압 범위로 제한할 수 있어?

- 회로·대상: ATtiny85 dev board · D2 · 조건: D2에 필요한 제너 전압 범위는 3.42~3.78V이다. / 비교 조건은 제너 전류 5mA, 주변 온도 25°C, 30ms 펄스이다.
- Codex 판단: 관련, 확신 high
- Codex 정답: 판정은 불충족(NOT_SUFFICIENT)이다. BZT52C5V1의 제너 전압(VZ)은 IZT=5mA, TA=25°C, 30ms 펄스 조건에서 최소 4.85V, 공칭 5.10V, 최대 5.36V로 요구 범위 3.42~3.78V를 만족하지 않는다. D2는 USB D+에 연결되어 정전용량 조건도 필요하지만, VZ 불충족이 확인되었으므로 정전용량 미확인과 관계없이 불충족을 우선한다. 후보 SOD-123F와 기존 DO-34/SOD68 삽입형 풋프린트가 달라 기판 수정 필요를 별도로 표시하며, 같은 동작은 보장하지 않는다.
- 이유: 질문의 비교 조건은 문서의 VZ 시험 조건과 일치하고 후보의 전압 범위 전체가 요구 범위보다 높다. 기준표 1절은 필수 조건 하나라도 불충족이면 다른 값의 부재보다 우선하도록 규정한다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS (TA=25°C unless otherwise noted), BZT52C5V1 행: VZ Min.=4.85V·Nom.=5.10V·Max.=5.36V·IZT=5mA
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 3쪽, Notes, 주1: VZ는 30ms 펄스 시험
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 1쪽, MECHANICAL DATA, Case=SOD-123F 행
  - netlists/tiny_attiny85_dev.net, D2 핀 1(K)=Net-(D2-K)·핀 2(A)=/GND; J1 핀 3(D+)=Net-(D2-K); D2 footprint=Diode_THT:D_DO-34_SOD68_P7.62mm_Horizontal
  - 정답판정-기준표.md, 1절 및 3.4 제너 클램프·전압 기준; SPEC.md, 3절
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### n06 — D3용 TSC 1N4148을 주문하려는데, 1N4148 A0G 대신 1N4148 R0G로 사도 같은 제품이야?

- 회로·대상: Franzininho DIY · D3
- Codex 판단: 관련, 확신 high
- Codex 정답: 판정은 동일품(IDENTICAL)이다. 제조사는 A0/A0G/R0/R0G 주문 코드가 차이 없이 물리적으로 동일한 부품이라고 명시하므로 1N4148 A0G와 1N4148 R0G는 같은 제품이다. 둘 다 DO-35이며 포장만 A0G는 5,000개 Ammo Box, R0G는 10,000개/14인치 Reel로 다르다. 동일품 판정이 회로 전체의 같은 동작을 보장하지는 않는다.
- 이유: SPEC 3절은 제조사가 같은 제품이라고 밝힌 품번을 동일품으로 분류한다. 1N4148 SERIES_K2301의 주문 정보 주1이 두 주문 코드를 명시적으로 포함한다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - corpus_txt/1N4148 SERIES_K2301.txt, 2쪽, ORDERING INFORMATION, 1N4148 A0G 및 1N4148 R0G 행과 주1: A0/A0G/R0/R0G는 physically identical parts without any differences
  - netlists/franz_c09.net, D3 value=1N4148·핀 A=Net-(D3-PadA)·핀 C=5V; X1 핀 VBUS=Net-(D3-PadA)
  - SPEC.md, 3절 동일품 정의
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### n07 — 이 조건에서 D1을 TSC 1N5817로 바꿔도 역극성 보호용으로 쓸 수 있어?

- 회로·대상: SparkFun Breadboard Supply · D1 · 조건: 전원은 J1 잭으로만 공급하고 S1은 켜 둔다. / 입력 전압의 최댓값은 20V, D1의 최대 순방향 전류는 150mA이다. / 주변 온도는 25°C이다.
- Codex 판단: 관련, 확신 high
- Codex 정답: 판정은 불충족(NOT_SUFFICIENT)이다. 역극성 보호의 필수 역전압 기준은 입력 최대 20V × 1.25 = 25V인데, 1N5817의 VRRM은 TA=25°C 기준 20V여서 이를 만족하지 않는다. 전류 기준은 150mA ÷ 0.7 ≈ 214.3mA이고 후보의 IF 정격은 1A이지만, 전압 불충족만으로 탈락하므로 VF의 추가 확인 여부와 관계없이 사용할 수 있다고 답해서는 안 된다. 같은 동작은 보장하지 않는다.
- 이유: J1에서 S1을 거쳐 D1 애노드로 들어오고 캐소드에서 F1을 거쳐 RAW로 나가므로 전원 직렬 역극성 보호 역할이다. 기준표 3.1의 kV=1.25를 적용하면 정격 20V를 입력 최대 20V와 단순히 같다고 보아 허용할 수 없다.
- 메모: 후보는 DO-41이나 기존 DIODE-0.4 풋프린트의 치수 호환 여부는 별도 확인이 필요하다. 이미 불충족이므로 이 확인이 전기적 판정을 바꾸지는 않는다.
- 기계 대조: 원문에 없는 숫자: 214.3 (150mA ÷ 0.7 계산값. 기준표의 전류 여유를 적용한 것이라 원문에 없음)
- 근거:
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted), 1N5817 Repetitive peak reverse voltage=20V 및 Forward current=1A 행
  - netlists/supply_breadboard.net, J1 핀 PWR·S1 핀 2=Net-(S1-P); S1 핀 3·D1 핀 A=Net-(S1-S); D1 핀 C·F1 핀 P$1=Net-(F1-1); F1 핀 P$2·U1 핀 IN=RAW
  - 정답판정-기준표.md, 3절 여유 배수 및 3.1 역극성 보호; SPEC.md, 3절 불충족 우선
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O

### n08 — D1을 TSC 1N4148로 바꾸면 이 전류 조건에서 쓸 수 있어?

- 회로·대상: SparkFun Breadboard Supply · D1 · 조건: 전원은 J1 잭으로만 공급하고 S1은 켜 둔다. / 입력 전압의 최댓값은 12V, D1에 흐르는 최대 연속 전류는 500mA이다. / 주변 온도는 25°C이다.
- Codex 판단: 관련, 확신 high
- Codex 정답: 판정은 불충족(NOT_SUFFICIENT)이다. 1N4148의 순방향 전류(IF) 정격은 TA=25°C에서 150mA로, 질문의 최대 연속 전류 500mA보다 작고 여유를 적용한 필수 기준 500mA ÷ 0.7 ≈ 714.3mA에도 못 미친다. IFSM 2A는 t=1µs의 비반복 사각파 서지 조건이므로 연속 전류 500mA의 근거로 사용할 수 없다. 후보는 DO-35이고 기존 넷리스트는 DIODE-0.4 풋프린트이므로 실장 호환을 별도 확인해야 하며, 같은 동작은 보장하지 않는다.
- 이유: 역극성 보호의 필수 연속 전류 조건이 명백히 불충족이다. VRRM 100V가 필요한 12V × 1.25 = 15V 이상이어도 전류 불충족을 상쇄하지 못한다.
- 메모: 기존 풋프린트 이름만으로 후보 DO-35와 정확한 패키지 치수 일치를 확정하지 않는다.
- 기계 대조: 원문에 없는 숫자: 714.3 (500mA ÷ 0.7 계산값. 기준표의 전류 여유를 적용한 것이라 원문에 없음)
- 근거:
  - corpus_txt/1N4148 SERIES_K2301.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS (TA=25°C unless otherwise noted), Forward current=150mA·Repetitive peak reverse voltage=100V·Non-repetitive sqare wave peak forward surge current, t=1μs=2A 행 및 MECHANICAL DATA Case=DO-35
  - netlists/supply_breadboard.net, D1 핀 A=Net-(S1-S)·핀 C=Net-(F1-1); S1 핀 2=Net-(S1-P)·핀 3=Net-(S1-S); J1 핀 PWR=Net-(S1-P); F1 핀 P$2=RAW; D1 footprint=import_input:DIODE-0.4
  - 정답판정-기준표.md, 3.1 역극성 보호; SPEC.md, 3절
- 정운 확인: O
- 재훈 확인(O / X와 맞는 결론): O


# 추가 관련 문항 — n21 (n22는 예비 이관)

질문은 정답·원문·대화 이력을 받지 않은 별도 AI가 작성했고, 다른 AI가 PDF 근거와 답안을 대조했다. 이 분리는 사람 검수를 대신하지 않는다. 추가 당시 두 문항은 김재훈이 2026-11-02에 O로 확인했다. 현재 본편에는 n21만 남으며 하정운의 1차 사람 판정은 대기 중이다.

### n21 — Breadboard Supply D1을 1N5819로 바꾸려는데, 온도에 따라 역방향 누설전류가 어떻게 달라져?

- 회로·대상: SparkFun Breadboard Supply · D1
- 현재 분류 초안: relevant
- Codex 정답 초안: TSC 1N5819의 H2104 2쪽 전기적 특성표에서 정격 역전압(rated VR)을 인가한 역전류 IR 최댓값은 TJ=25°C에서 1mA, TJ=100°C에서 10mA이며 주석 2의 펄스 폭은 30ms이다. 문서의 두 시험 온도에서 최대 허용값이 다르다는 뜻이며 실제 누설전류가 항상 정확히 10배가 된다는 뜻은 아니다. 임의 온도·역전압이나 보드 전체의 역류 실측값으로 확대하지 않는다. 이 조회만으로 D1의 대체 적합성이나 같은 동작을 보장하지 않는다.
- 이유: [문서] H2104의 같은 IR 항목에 온도별 MAX 열과 시험 주석이 명시되어 있어 조건을 밝힌 온도별 정격 조회에 답할 수 있다. 실제 회로 역류의 실측이나 임의 온도의 보장값을 요청한 문항이 아니다.
- 근거: 1N5817 SERIES_H2104.pdf, 2쪽, ELECTRICAL SPECIFICATIONS, Reverse current @ rated VR의 TJ=25°C/MAX 1mA 및 TJ=100°C/MAX 10mA 행; Notes 2(PW=30ms)
- 원문 대조: PDF 2쪽 화면·텍스트와 manifest SHA256 일치 확인. 모델 실행·점수 측정은 하지 않음.
- 정운 확인(O / X와 맞는 결론):
- 재훈 확인(O / X와 맞는 결론): O (2026-11-02)
