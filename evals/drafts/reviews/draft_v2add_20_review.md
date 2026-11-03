# 평가셋 검토표 — v2 추가 20건(후보 찾기)

> **판정 기록**
> - 이 20건: v1 50건(2026-11-02 동결, 저장소 `evals/dataset_v1.jsonl`)에 더하는 v2 추가 초안(draftv2-n01~n20)이다. 이 파일의 n01~n20은 draftv2-n01~n20을 뜻하며 v1의 draft50-n01~n20과 다른 문항이다(예: 여기 n13은 ROHM 문항, v1 n13은 예비로 뺀 1N270 문항). 50건에 0건이던 "후보 찾기"(후보 품번 없이 대체 후보를 찾아 달라는 질문) 유형이다. 관련 10(회로마다 2, 이 중 되묻기 3: n02·n04·n08), 비관련 10(out_of_domain 2, unknown_entity 3, missing_attribute 3, wrong_period 2, 회로마다 2). 11-06 무렵 동결 예정.
> - 초안: Codex가 썼다(2026-11-01). 출제(`evidence/eval_v2add_codex/1_출제/`)와 정답(`2_정답/`, 출제 의도를 지운 문항으로 따로)을 나눠 돌렸다. 아래 "Codex 판단"·"Codex 정답"은 정답 쪽 초안이다.
> - 관련 문항은 열린 정답이다. 조건을 모두 만족하는 코퍼스 품번이면 어느 것이든 정답이고, 적힌 후보는 예시다.
> - 출제 의도와 정답의 차이: 관련/비관련과 비관련 종류는 20건 모두 같다. 되묻기 3건도 정답 쪽이 모두 되묻기로 답했다. 후보 예시는 7건에서 다르다(아래 표). 두 쪽에 다 나온 후보의 판정은 서로 같다.
> - 기계 대조에서 원문에 없다고 나온 숫자(14.286, 0.080, 25.714, 714.286, 6.25, 114.286)는 모두 기준값 계산 결과(전류 ÷ 0.7, 전압 × 1.25, 80 mA = 0.080 A)다.
> - 검토 때 볼 점: n05·n06은 USB 데이터선 정전용량(CJ) 조건을 피하려고 "USB 분리·저속 클램프 시험" 조건을 넣었다. 실제 사용자 질문으로 자연스러운지 본다. n10 후보 BAS316의 VR 100 V는 절대 최대 정격표(1쪽, VR 행 없음)가 아니라 1쪽 KEY PARAMETERS와 2쪽 항복 시험값(IR = 100 µA에서 최소 100 V)에서 왔다. 역전압 정격으로 인정할지 본다.
> - 1차 사람 판정(하정운, 2026-11-03, 전부 O): 비관련 표의 "정운" 칸과 판단형의 "정운 확인" 줄에 O, 또는 X와 맞는 결론을 적는다.
> - 2차 사람 판정(김재훈, 2026-11-03, 전부 O, 정운 전달): 비관련 표의 "재훈" 칸과 판단형의 "재훈 확인" 줄에 같은 방식으로 적는다.
> - 두 사람 판정이 다른 문항만 함께 다시 보고 정한 뒤 동결한다.

| 문항 | 출제 의도 후보(예상 판정) | Codex 정답 후보(판정) |
|---|---|---|
| n01 | 1N4148W, 1N4148WS (역할상 충분) | 같음 |
| n02 되묻기(입력 최대 전압) | 1N4148W, 1N4148WS-G (지금은 확인 안 됨, 12V면 역할상 충분) | 1N4148W, 1N4148WS (지금은 확인 안 됨, 60V·80V 이하면 역할상 충분) |
| n03 | 1N5818, 1N5819 (역할상 충분) | 1N5817, SS14 (역할상 충분) |
| n04 되묻기(코일 전류) | SS14LW, SS24LW (지금은 확인 안 됨, 80mA면 역할상 충분) | 1N5817, SS14 (지금은 확인 안 됨, 80mA면 역할상 충분) |
| n05 | BZT52C3V6, BZT52C3V6S (역할상 충분) | BZT52C3V6S, BZT52B3V6S (역할상 충분) |
| n06 | BZT52B3V6S, BZT52C3V6S (역할상 충분) | 같음 |
| n07 | SS14LW, SS14ALH (사양 동등) | SS14, SS14L (사양 동등) |
| n08 되묻기(RAW 최대 전압) | SS14LW, SS14ALH (지금은 확인 안 됨, 12V면 사양 동등) | SS14, SS14L (지금은 확인 안 됨, 32V 이하면 사양 동등) |
| n09 | 1N4148W, 1N4148WS (역할상 충분) | 같음 |
| n10 | 1N4148WS-G, 1N4148WSH (역할상 충분) | BAS16, BAS316 (역할상 충분) |

- 1번 표는 숫자만 묻는 문항이다. 정답의 숫자가 근거 쪽 원문에 있는지 기계로 대조했다. 대조에서 걸린 것만 보면 된다.
- 2번 표는 비관련(자료 밖이라 거절이 정답) 문항이다. 질문이 정말 우리 자료 밖인지만 훑고 확인 칸에 O/X를 적는다.
- 3번은 판단이 들어간 문항이다. Codex 결론에 동의하면 O, 아니면 X와 맞는 결론을 적는다.
- 기계 대조는 숫자가 원문에 "있는지"만 본다. 맞는 행·조건에서 왔는지는 보지 않는다.

## 1. 숫자형: 기계 대조로 끝 (0건)

| 문항 | 질문 | Codex 정답 | 기계 대조 |
|---|---|---|---|

## 2. 비관련: 훑어보기 (9건)

| 문항 | 질문 | 종류 | Codex 결론 | 기계 확인 | 정운 | 재훈 |
|---|---|---|---|---|---|---|
| n11 | S1 수급이 끊겨서 바꾸려 해. 같은 전원 켜기·끄기 기능을 하는 대체 스위치 후보를 찾아 줘. | out_of_domain | S1 대체 스위치 추천은 서비스 범위 밖이므로 거절하는 것이 정답이다. S1은 다이오드가 아닌 On/Off SPST 스위치이며, 이 서비스는 다이오드만 취급한다. | - | O | O |
| n13 | D3가 단종돼서 바꿔야 해. ROHM 제품 중에서 이 릴레이용 대체 후보를 찾아 줘. | unknown_entity | ROHM 제품만으로는 후보를 제시할 수 없다는 안내가 정답이다. 코퍼스에는 ROHM 제조사 데이터시트와 품번 목록이 없으므로 TSC 후보를 ROHM 제품처럼 제시하면 안 된다. | 품번 후보 없음 | O | O |
| n14 | D3를 저잡음 부품으로 바꾸고 싶어. 1kHz에서 순방향 전류 잡음 밀도가 1pA/√Hz 이하로 명시된 대체 후보를 찾아 줘. | missing_attribute | 1 kHz에서 순방향 전류 잡음 밀도 1 pA/√Hz 이하를 보증하는 후보는 문서로 확인할 수 없다는 자료 부재 안내가 정답이다. 누설전류나 역회복 시간으로 잡음 밀도를 대신하지 않는다. | - | O | O |
| n15 | D1 재고가 없어서 다른 제조사로 바꾸려 해. Toshiba 제품 중에서 같은 클램프 역할을 할 대체 후보를 찾아 줘. | unknown_entity | Toshiba 제품만으로는 대체 후보를 제시할 수 없다는 안내가 정답이다. 코퍼스에 Toshiba의 문서·품번 목록이 없으므로 같은 3.6 V 표기를 근거로 TSC 부품을 Toshiba 제품으로 바꿔 부를 수 없다. | 품번 후보 없음 | O | O |
| n16 | D2 대체품을 검토 중이야. 개정 코드가 G2710인 TSC 데이터시트를 기준으로 이 자리에 쓸 후보를 찾아 줘. | wrong_period | 개정 코드 G2710인 TSC 데이터시트가 코퍼스에 없으므로 그 판을 기준으로 후보를 확정할 수 없다는 안내가 정답이다. 현재 보유한 G1804 등의 개정판을 요청한 판으로 간주하지 않는다. | - | O | O |
| n17 | D2를 다른 공급처 제품으로 바꾸려 해. Central Semiconductor 제품만으로 USB 역류 방지용 대체 후보를 찾아 줘. | unknown_entity | Central Semiconductor 제품만으로는 USB 역류 방지 후보를 제시할 수 없다는 안내가 정답이다. 요청한 제조사의 문서·품번 목록이 코퍼스에 없으므로 TSC 제품으로 제조사 조건을 대신 만족시킬 수 없다. | 품번 후보 없음 | O | O |
| n18 | 장시간 켜 두는 보드라 D2의 신뢰성을 보고 바꾸려 해. 55°C에서 고장률이 10FIT 이하로 명시된 대체 후보를 찾아 줘. | missing_attribute | 55°C에서 고장률 10 FIT 이하를 보증하는 후보는 코퍼스에서 확인할 수 없다는 자료 부재 안내가 정답이다. FIT는 10억 부품·시간당 고장 건수이며, 동작 온도 정격이나 정성적인 high reliability 문구로 고장률 값을 대신할 수 없다. | - | O | O |
| n19 | D3를 바꾸려 해. Vishay 데이터시트를 근거로 같은 전원 경로에 쓸 대체 후보를 찾아 줘. | out_of_domain | Vishay 데이터시트에 근거한 후보 검색은 SPEC이 제외한 제조사 자료를 요구하므로 범위 밖으로 거절하는 것이 정답이다. 코퍼스에는 Vishay 문서가 없으며, TSC 1N4148 문서를 Vishay 근거로 제시하면 안 된다. | - | O | O |
| n20 | D3가 단종돼서 바꾸려 해. 2027년판 TSC 데이터시트를 기준으로 같은 역할을 할 대체 후보를 찾아 줘. | wrong_period | 2027년판 TSC 데이터시트가 코퍼스에 없으므로 그 판에 근거한 대체 후보를 확정할 수 없다는 안내가 정답이다. 현재 가진 과거 개정판을 2027년판이라고 제시하지 않는다. | - | O | O |

## 3. 판단형: 꼼꼼히 (11건)

### n01 — D1 자리를 삽입형 대신 표면실장으로 바꿔서 조립하려고 해. 같은 보호 역할을 할 대체 후보를 찾아 줘.

- 회로·대상: SparkFun Breadboard Supply · D1 · 조건: D1은 현재 TSC 1N5819로 교체해 쓰고 있다. / J1 잭으로만 공급하며 최대 부하 전류는 10mA이다. / 입력 최대 전압은 12V이다. / 실온 25°C에서 사용하고, 허용 전압 강하는 IF=10mA·TJ=25°C·0.3ms 펄스 시험 기준으로 1.00V 이하이다. / 새 패키지에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high
- Codex 정답: D1은 J1→S1→D1→F1→RAW 경로의 직렬 역극성 보호 다이오드이다(기준표 3.1). 필수 조건은 VRRM(없으면 VR) ≥ 12 V × 1.25 = 15 V, IF(AV)(없으면 IF) ≥ 10 mA / 0.7 = 14.286 mA, VF ≤ 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms)이며 표면실장이어야 한다. 후보 1N4148W는 VRRM 75 V·IF 150 mA(TA=25°C)·VF 최대 1.00 V(지정 시험 조건)인 SOD-123F로 역할상 충분이다. 후보 1N4148WS는 VRRM 100 V·IF 150 mA(TA=25°C)·VF 최대 1.00 V(같은 시험 조건)인 SOD-323F로 역할상 충분이다. 두 후보 모두 원래 1N5819의 IF 1 A에는 못 미치지만 회로 조건은 만족하고, 원래 삽입형 footprint와 달라 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 넷리스트로 역극성 보호 역할을 확인하고 질문이 정한 현재 부품·실제 전압·전류·VF 시험 조건을 우선 적용했다. 전원 경로가 하나이므로 OR-ing의 IR 비교를 요구하지 않는다.
- 기계 대조: 원문에 없는 숫자: 14.286
- 근거:
  - netlists/supply_breadboard.net, D1, 핀 A → Net-(S1-S), 핀 C → Net-(F1-1); S1 핀 3과 D1 A, F1 핀 P$1과 D1 C 연결; F1 핀 P$2 → RAW, U1 핀 IN → RAW; D1 원래 footprint import_input:DIODE-0.4
  - corpus_txt/1N4148W SERIES_K1804.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148W VRRM 75 V·IF 150 mA·PD 400 mW(TA=25°C); MECHANICAL DATA, SOD-123F
  - corpus_txt/1N4148W SERIES_K1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148W Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse leakage current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N4148WS SERIES_N2212.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148WS VRRM 100 V·IF 150 mA·PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/1N4148WS SERIES_N2212.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148WS Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5819 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파), TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N5819 VF 최대 0.60 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 1 mA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: 1N4148W → 1N4148W SERIES_K1804.pdf (정확 일치 1행); 1N4148WS → 1N4148WS SERIES_N2212.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)
### n02 — 소량 보드의 원가를 줄이려고 D1을 바꾸려 해. 이 조건에 맞는 대체 후보를 찾아 줘.

- 회로·대상: SparkFun Breadboard Supply · D1 · 조건: D1은 현재 TSC 1N5819로 교체해 쓰고 있다. / J1 잭으로만 공급하며 최대 부하 전류는 10mA이다. / 실온 25°C에서 사용하고, 허용 전압 강하는 IF=10mA·TJ=25°C·0.3ms 펄스 시험 기준으로 1.00V 이하이다. / 새 패키지에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high · **사람 확인 필요**
- Codex 정답: D1의 역할은 직렬 역극성 보호이며, 입력 최대 전압 Vmax(역극성 시 최대 인가 전압 포함)를 먼저 되물어야 한다. RAW라는 넷 이름과 LM317이라는 부품 값만으로 J1의 최대 입력 전압을 확정할 수 없다. 조건은 VRRM(없으면 VR) ≥ Vmax × 1.25, IF(AV)(없으면 IF) ≥ 10 mA / 0.7 = 14.286 mA, VF ≤ 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms)이다. 후보 1N4148W(SOD-123F)는 VRRM 75 V·IF 150 mA·해당 VF 최대 1.00 V이므로 Vmax ≤ 75/1.25 = 60 V이면 역할상 충분이다. 후보 1N4148WS(SOD-323F)는 VRRM 100 V·IF 150 mA·해당 VF 최대 1.00 V이므로 Vmax ≤ 100/1.25 = 80 V이면 역할상 충분이다. 두 후보 모두 정격의 기본 온도는 TA=25°C이고, 현재는 Vmax 미정으로 문서로 확인 안 됨이며 원래 1N5819의 정격을 회로 전압으로 대신하지 않는다. 두 후보 모두 원래 IF 1 A보다 작고 기판 수정 필요다. 원가 절감 여부는 가격 자료가 없어 확정하지 않는다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 값이 없는 것은 회로 운용 전압이지 코퍼스의 부품 속성이 아니다. 따라서 비관련 missing_attribute로 거절할 문항이 아니라 되물음·조건부 후보 제시가 정답인 관련 문항이다.
- 메모: J1 최대 입력·역극성 전압을 받아 VR 조건을 확정해야 한다. 후보의 허용 전압은 다이오드 판정 한계이며 보드 전체의 동작 가능 전압을 뜻하지 않는다.
- 기계 대조: 원문에 없는 숫자: 14.286
- 근거:
  - netlists/supply_breadboard.net, D1, 핀 A → Net-(S1-S), 핀 C → Net-(F1-1); S1 핀 3과 D1 A, F1 핀 P$1과 D1 C 연결; F1 핀 P$2 → RAW, U1 핀 IN → RAW; D1 원래 footprint import_input:DIODE-0.4
  - corpus_txt/1N4148W SERIES_K1804.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148W VRRM 75 V·IF 150 mA·PD 400 mW(TA=25°C); MECHANICAL DATA, SOD-123F
  - corpus_txt/1N4148W SERIES_K1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148W Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse leakage current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N4148WS SERIES_N2212.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148WS VRRM 100 V·IF 150 mA·PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/1N4148WS SERIES_N2212.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148WS Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5819 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파), TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N5819 VF 최대 0.60 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 1 mA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: 1N4148W → 1N4148W SERIES_K1804.pdf (정확 일치 1행); 1N4148WS → 1N4148WS SERIES_N2212.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n03 — D3에 쓰던 부품이 단종됐어. 릴레이를 끌 때 같은 역할을 할 대체 후보를 찾아 줘.

- 회로·대상: Adafruit MOSFET Driver · D3 · 조건: X1에는 최대 전원 전압 12V, 정상 코일 전류 80mA인 릴레이를 연결한다. / PWM 없이 간헐적으로 한 번씩 켜고 끈다. / 차단 시 다이오드 전류는 피크 80mA·폭 8.3ms의 단발 반정현파이고 주변 온도 TA와 접합 온도 TJ는 모두 25°C이다. / 패키지가 달라지면 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: D3는 X1에 연결한 릴레이와 병렬이고 캐소드가 VIN, 애노드가 /OUT인 플라이백 다이오드이다(기준표 3.3). 조건은 VRRM ≥ 12 V × 1.25 = 15 V, IF(AV) 또는 IFSM ≥ 코일 정상 전류 80 mA = 0.080 A이며 IFSM은 피크 80 mA·폭 8.3 ms 단발 반정현파·TA=TJ=25°C 조건으로 대조한다. PWM이 없으므로 trr은 필수 조건이 아니고, 이 역할의 전류 기준에 kI를 추가하지 않는다. 후보 1N5817은 VRRM 20 V·IFSM 30 A(8.3 ms 단발 반정현파, 정격 부하 중첩·TA=25°C 기본 조건)의 DO-41로 역할상 충분이다. 후보 SS14는 VRRM 40 V·IFSM 40 A(동일 파형·폭·기본 온도)의 SMA로 역할상 충분이다. 넷리스트의 1N400x/SM4002는 원래 품번을 하나로 확정하지 못하므로 동일품·사양 동등을 내지 않으며 두 후보 모두 SOD-123 footprint에서 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: D3의 두 넷에 X1의 부하 단자가 모두 연결되어 있고 Q1이 /OUT을 스위칭한다. 질문의 단발 파형과 데이터시트 IFSM의 파형·폭을 직접 대조했으며 µs 서지 정격으로 대체하지 않았다.
- 메모: 원래 부품 표기 1N400x/SM4002가 불완전하여 원품 대비 주요 정격 비교는 확정할 수 없다. 제시 판정은 회로 역할 조건 충족에 대한 1차 판정이다.
- 기계 대조: 원문에 없는 숫자: 0.080
- 근거:
  - netlists/driver_mosfet.net, D3, 핀 A → /OUT, 핀 C → VIN; X1 핀 L1.1·L1.2 → /OUT, 핀 L2.1·L2.2 → VIN; Q1 핀 3 → /OUT; D3 값 1N400x/SM4002, footprint SOD-123
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5817 열: VRRM 20 V·IFSM 30 A(8.3 ms 단발 반정현파, 정격 부하에 중첩)·TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/SS12 SERIES_R2305.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14 열: VRRM 40 V·IF 1 A·IFSM 40 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, SMA
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: 1N5817 → 1N5817 SERIES_H2104.pdf (정확 일치 1행); SS14 → SS12 SERIES_R2305.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n04 — D3 재고가 없어. 이 릴레이의 플라이백용으로 쓸 대체 후보를 찾아 줘.

- 회로·대상: Adafruit MOSFET Driver · D3 · 조건: X1에는 최대 전원 전압 12V인 릴레이를 연결한다. / PWM 없이 간헐적으로 한 번씩 켜고 끈다. / 차단 전류의 파형은 폭 8.3ms의 단발 반정현파이고 주변 온도 TA와 접합 온도 TJ는 모두 25°C이다. / 패키지가 달라지면 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high · **사람 확인 필요**
- Codex 정답: D3는 VIN과 /OUT 사이의 릴레이 플라이백 다이오드이며 VRRM ≥ 12 V × 1.25 = 15 V가 필요하다. 코일 정상 전류와 차단 피크 전류를 되물어 IF(AV) 또는 IFSM ≥ 코일 정상 전류 기준을 확정해야 하며, 8.3 ms 단발 반정현파라는 폭만으로 전류 크기를 알 수 없다. 후보 1N5817(DO-41)은 VRRM 20 V·IFSM 30 A, 후보 SS14(SMA)는 VRRM 40 V·IFSM 40 A로 전압 조건은 충족한다(둘 다 TA=25°C 기본 조건·8.3 ms 단발 반정현파, 정격 부하 중첩 서지 정격). 현재 판정은 두 후보 모두 전류 기준 미정으로 문서로 확인 안 됨이며, 예를 들어 코일 정상·피크 전류가 80 mA로 확인되면 둘 다 역할상 충분이다. 일반적으로 나머지 질문 조건이 유지되고 단발 차단 전류가 해당 IFSM 이내이면 역할 조건을 만족하며 PWM이 없어 trr은 필수가 아니고 kI를 추가하지 않는다. 원래 품번 1N400x/SM4002는 확정할 수 없어 동일품·사양 동등은 내지 않으며 두 후보 모두 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 넷리스트 X1 값은 커넥터 품번이며 코일 전류가 아니다. 다른 문항에 주어진 80 mA를 이 문항의 확정 조건으로 가져오지 않는다.
- 메모: 코일 정상 전류와 차단 피크 전류 확인이 필수다. 원래 품번도 하나로 확정되지 않았다.
- 기계 대조: 원문에 없는 숫자 없음
- 근거:
  - netlists/driver_mosfet.net, D3, 핀 A → /OUT, 핀 C → VIN; X1 핀 L1.1·L1.2 → /OUT, 핀 L2.1·L2.2 → VIN; Q1 핀 3 → /OUT; D3 값 1N400x/SM4002, footprint SOD-123
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5817 열: VRRM 20 V·IFSM 30 A(8.3 ms 단발 반정현파, 정격 부하에 중첩)·TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/SS12 SERIES_R2305.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14 열: VRRM 40 V·IF 1 A·IFSM 40 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, SMA
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: 1N5817 → 1N5817 SERIES_H2104.pdf (정확 일치 1행); SS14 → SS12 SERIES_R2305.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n05 — D1을 표면실장으로 바꿔 조립하려고 해. 이 시험 조건에서 같은 클램프 역할을 할 후보를 찾아 줘.

- 회로·대상: ATtiny85 dev board · D1 · 조건: USB 케이블은 분리하고 통신은 사용하지 않는다. / J1의 D- 핀을 저속 클램프 시험 입력으로 쓰며 PB3는 고임피던스로 둔다. / 25°C에서 D1에 흐르는 총 제너 전류를 R1 쪽 전류까지 포함해 5mA·30ms 펄스로 맞춘다. / 클램프 전압 허용 범위는 3.42~3.78V이고 표면실장 부품에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high · **사람 확인 필요**
- Codex 정답: D1은 GND로 연결된 3.6 V 제너 클램프이며 이 문항에서는 USB 통신을 끈 저속 시험용이다(기준표 3.4). 후보의 VZ 보증 범위 전체가 3.42~3.78 V 안이어야 하며 조건은 TA=25°C·IZ=IZT=5 mA·PW=30 ms이다. 전력 조건은 공칭값 기준 PD ≥ (5 mA × 3.6 V)/0.7 = 25.714 mW이고, 허용 범위 상단을 쓰면 PD ≥ (5 mA × 3.78 V)/0.7 = 27 mW로 보수적으로 판정한다. 후보 BZT52C3V6S는 VZ 3.42~3.78 V, 후보 BZT52B3V6S는 VZ 3.53~3.67 V이며 둘 다 지정 시험 조건의 SOD-323F·PD 200 mW(TA=25°C)라 역할상 충분이다. 실제 IZ/IZT=1로 시험 전류 불일치가 없으며, 전압 기준 용도가 아닌 클램프이고 USB가 분리되어 데이터선 CJ 조건을 발동하지 않는다. 원래 표기는 3.6 Zener뿐이라 동일품·사양 동등을 내지 않고, 둘 다 삽입형 footprint에서 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 질문에서 R1 전류까지 포함한 총 제너 전류와 펄스 폭을 지정했으므로 저항으로 전류를 다시 추정하지 않는다. 물리적으로 USB 넷에 연결되었어도 이 문항의 실제 사용은 비통신 저속 클램프다.
- 메모: 넷 이름만으로 CJ 조건을 항상 발동시키지 않고, 명시된 USB 분리·비통신 시험 조건을 반영했다. 기준표 3.4의 데이터선 조건을 운용 조건으로 해석한 부분은 사람이 확정해야 한다.
- 기계 대조: 원문에 없는 숫자: 25.714
- 근거:
  - netlists/tiny_attiny85_dev.net, D1, 핀 1(K) → Net-(D1-K), 핀 2(A) → /GND; J1 핀 2(D-)·R1 핀 1·R3 핀 2 → Net-(D1-K); D1 값 3.6 Zener, footprint Diode_THT:D_DO-34_SOD68_P7.62mm_Horizontal
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 2쪽, ELECTRICAL SPECIFICATIONS, BZT52C3V6S 행: VZ 3.42/3.60/3.78 V(최소/공칭/최대), IZT 5 mA·TA=25°C
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 3쪽, Notes, 1행: VZ 시험 펄스 30 ms
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 2쪽, ELECTRICAL SPECIFICATIONS, BZT52B3V6S 행: VZ 3.53/3.60/3.67 V(최소/공칭/최대), IZT 5 mA·TA=25°C
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 3쪽, Notes, 1행: VZ 시험 펄스 30 ms
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: BZT52C3V6S → BZT52C2V4S SERIES_K2411.pdf (정확 일치 1행); BZT52B3V6S → BZT52B2V4S SERIES_I2411.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n06 — 현재 쓰는 D2의 재고가 없어. 전력 정격이 지금보다 낮아도 이 클램프 시험에 충분한 대체 후보를 찾아 줘.

- 회로·대상: ATtiny85 dev board · D2 · 조건: D2는 현재 TSC BZT52C3V6으로 교체해 쓰고 있다. / USB 케이블은 분리하고 통신은 사용하지 않으며 J1의 D+ 핀을 저속 클램프 시험 입력으로 쓰고 PB4는 고임피던스로 둔다. / 25°C에서 D2의 제너 전류는 5mA·30ms 펄스이며 클램프 전압 허용 범위는 3.42~3.78V이다. / 표면실장 부품에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high · **사람 확인 필요**
- Codex 정답: D2는 현재 BZT52C3V6의 3.6 V 제너 클램프이며 USB 비통신 저속 시험용이다(기준표 3.4). VZ 보증 범위 전체가 3.42~3.78 V 안이어야 하고 TA=25°C·IZ=IZT=5 mA·PW=30 ms여야 하며, PD ≥ (5 mA × 3.6 V)/0.7 = 25.714 mW, 상단 전압을 쓴 보수적 기준은 (5 mA × 3.78 V)/0.7 = 27 mW이다. 후보 BZT52C3V6S는 VZ 3.42~3.78 V·PD 200 mW, 후보 BZT52B3V6S는 VZ 3.53~3.67 V·PD 200 mW로 모두 지정 시험 조건을 만족한다. 두 후보는 원래 BZT52C3V6의 PD 500 mW에는 못 미쳐 사양 동등이 아닌 역할상 충분이다. 후보는 모두 SOD-323F이며 현재 부품의 SOD-123F 및 넷리스트의 삽입형 footprint와 달라 기판 수정 필요다. IZ/IZT=1이고 전압 기준 용도가 아니며 USB를 분리했으므로 CJ와 전압 기준용 별도 오차 조건은 발동하지 않는다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 현재 부품은 질문이 명시한 TSC BZT52C3V6을 사용했다. 전력 정격 200 mW가 원래보다 작아도 실제 소비전력의 여유 기준을 넘으면 역할상 충분이 성립한다.
- 메모: USB 분리·비통신 시험이므로 CJ 조건을 적용하지 않은 해석은 사람이 확정해야 한다.
- 기계 대조: 원문에 없는 숫자: 25.714
- 근거:
  - netlists/tiny_attiny85_dev.net, D2, 핀 1(K) → Net-(D2-K), 핀 2(A) → /GND; J1 핀 3(D+)·R2 핀 2 → Net-(D2-K); D2 원래 footprint Diode_THT:D_DO-34_SOD68_P7.62mm_Horizontal
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 2쪽, ELECTRICAL SPECIFICATIONS, BZT52C3V6S 행: VZ 3.42/3.60/3.78 V(최소/공칭/최대), IZT 5 mA·TA=25°C
  - corpus_txt/BZT52C2V4S SERIES_K2411.txt, 3쪽, Notes, 1행: VZ 시험 펄스 30 ms
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 2쪽, ELECTRICAL SPECIFICATIONS, BZT52B3V6S 행: VZ 3.53/3.60/3.67 V(최소/공칭/최대), IZT 5 mA·TA=25°C
  - corpus_txt/BZT52B2V4S SERIES_I2411.txt, 3쪽, Notes, 1행: VZ 시험 펄스 30 ms
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, PD 500 mW(TA=25°C); MECHANICAL DATA, SOD-123F
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS, BZT52C3V6 행: VZ 3.42/3.60/3.78 V·IZT 5 mA·TA=25°C
  - corpus_txt/BZT52C2V4 SERIES_G1804.txt, 3쪽, Notes, 1행: VZ 시험 펄스 30 ms
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: BZT52C3V6S → BZT52C2V4S SERIES_K2411.pdf (정확 일치 1행); BZT52B3V6S → BZT52B2V4S SERIES_I2411.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n07 — 현재 쓰는 D2를 더 이상 구하기 어려워. USB 쪽 역류를 막는 역할을 유지할 대체 후보를 찾아 줘.

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: D2는 현재 TSC 1N5819로 교체해 쓰고 있고 SJ1은 열어 둔다. / USB와 RAW는 외부 스위치로 번갈아 공급하며 D2의 최대 부하 전류는 500mA이다. / RAW 외부 전원의 최대 전압은 12V이다. / 전원 공급 우선순위는 다이오드의 전압 강하로 정하지 않고 U2의 입력 전압 여유는 별도로 확보한다. / 역누설은 정격 역전압에서 TJ=25°C·30ms 펄스 시험값으로 현재 부품과 비교한다. / 실온 25°C에서 쓰며 새 패키지에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: D2는 USB의 UVCC→F1→D2→/RAW 경로에서 RAW 쪽 전원이 USB로 역류하는 것을 막는다(기준표 3.2). 조건은 VRRM(없으면 VR) ≥ RAW 최대 12 V × 1.25 = 15 V, IF(AV)(없으면 IF) ≥ 500 mA/0.7 = 714.286 mA, IR ≤ 원래 1N5819의 1 mA(VR=40 V·TJ=25°C·PW=30 ms)이다. 전원 선택 우선순위와 U2 입력 여유를 별도로 확보하므로 VF는 역할 필수 조건에서 제외한다. 후보 SS14는 VRRM 40 V·IF 1 A·IR 최대 200 µA(VR=40 V·TJ=25°C·PW=30 ms)이며 VF 최대 0.50 V(IF=1 A·TJ=25°C·PW=0.3 ms)·IFSM 40 A(8.3 ms 단발 반정현파)라 사양 동등이다. 후보 SS14L은 VRRM 40 V·IF 1 A·동일 누설 시험에서 IR 최대 400 µA이며 VF 최대 0.55 V(동일 VF 시험)·IFSM 30 A(같은 파형·폭)라 사양 동등이다. 두 후보는 TA=25°C 기본 정격이며 원래의 VRRM 40 V·IF 1 A·IR 1 mA·VF 0.60 V·IFSM 30 A를 같거나 개선하고, 패키지는 각각 SMA·Sub SMA라 원래 넷리스트 SOD-323 또는 현재 1N5819 DO-41에서 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: IR을 서로 다른 정격 역전압에서 비교하는 오류를 피하려고 두 후보 모두 원래와 같은 40 V 정격을 골랐다. SJ1 개방 조건에서 D2가 우회되지 않는다.
- 메모: 주요 정격 목록은 아직 정하지 않았다(SPEC 5절 규칙 파일 "(정할 것)"). 사양 동등은 확인 가능한 VRRM·IF·VF·IR·IFSM·사용 온도를 기준으로 한 1차 판정이므로 주요 정격 범위를 사람이 확정해야 한다.
- 기계 대조: 원문에 없는 숫자: 714.286
- 근거:
  - netlists/pro_micro_v13.net, D2, 핀 2(A) → Net-(D2-A), 핀 1(C) → /RAW; F1 핀 2·SJ1 핀 1 → Net-(D2-A); U2 핀 1(IN)·JP6 핀 1 → /RAW; F1 핀 1·X1 핀 VBUS1 → UVCC; D2 원래 footprint import_input:SOD-323
  - corpus_txt/SS12 SERIES_R2305.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14 열: VRRM 40 V·IF 1 A·IFSM 40 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, SMA
  - corpus_txt/SS12 SERIES_R2305.txt, 2쪽, ELECTRICAL SPECIFICATIONS, SS14 VF 최대 0.50 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 200 µA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/SS12L SERIES_Q2103.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14L 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, Sub SMA
  - corpus_txt/SS12L SERIES_Q2103.txt, 2쪽, ELECTRICAL SPECIFICATIONS, SS14L VF 최대 0.55 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 400 µA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5819 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파), TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N5819 VF 최대 0.60 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 1 mA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: SS14 → SS12 SERIES_R2305.pdf (정확 일치 1행); SS14L → SS12L SERIES_Q2103.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n08 — D2 조달이 불안정해서 다른 부품으로 바꾸려 해. USB와 RAW를 번갈아 쓸 때 맞는 대체 후보를 찾아 줘.

- 회로·대상: SparkFun Pro Micro v13 · D2 · 조건: D2는 현재 TSC 1N5819로 교체해 쓰고 있고 SJ1은 열어 둔다. / USB와 RAW는 외부 스위치로 번갈아 공급하며 D2의 최대 부하 전류는 500mA이다. / 전원 공급 우선순위는 다이오드의 전압 강하로 정하지 않고 U2의 입력 전압 여유는 별도로 확보한다. / 역누설은 정격 역전압에서 TJ=25°C·30ms 펄스 시험값으로 현재 부품과 비교한다. / 실온 25°C에서 쓰며 새 패키지에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 high · **사람 확인 필요**
- Codex 정답: D2의 역할은 USB→RAW 전원 경로의 역류 방지이다(기준표 3.2). RAW 외부 전원의 최대 전압 VRAW,max를 되물어야 하며, /RAW라는 이름이나 U2 MIC5219만으로 최대 운용 전압을 확정할 수 없다. 조건은 VRRM(없으면 VR) ≥ VRAW,max × 1.25, IF(AV)(없으면 IF) ≥ 500 mA/0.7 = 714.286 mA, IR ≤ 1 mA(VR=40 V·TJ=25°C·PW=30 ms)이며 질문 조건상 VF는 역할 필수가 아니다. 후보 SS14(SMA)는 VRRM 40 V·IF 1 A·IR 최대 200 µA, 후보 SS14L(Sub SMA)은 VRRM 40 V·IF 1 A·IR 최대 400 µA이고 누설의 전압·온도·펄스 폭은 모두 원래와 같다. 현재 두 후보의 판정은 VRAW,max 미정으로 문서로 확인 안 됨이다. VRAW,max ≤ 40/1.25 = 32 V로 확인되면 전압 여유도 충족하고, VF 최대 0.50/0.55 V(IF=1 A·TJ=25°C·PW=0.3 ms)·IFSM 40/30 A(8.3 ms 단발 반정현파)도 원래 0.60 V·30 A보다 같거나 좋아 두 후보를 사양 동등으로 판정할 수 있다. 정격 기본 조건은 TA=25°C이며 둘 다 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 없는 값은 사용자의 RAW 전압 조건이므로 관련 문항이다. 다른 문항의 12 V나 코퍼스 밖 핀 배치 그림의 16 V를 가져오지 않았다.
- 메모: RAW 외부 전원의 최대 운용 전압 확인이 필요하다. 32 V는 다이오드 전압 여유 한계이며 U2나 보드 전체의 허용 전압을 뜻하지 않는다. 사양 동등에 쓸 주요 정격 목록도 사람이 확정해야 한다.
- 기계 대조: 원문에 없는 숫자: 714.286
- 근거:
  - netlists/pro_micro_v13.net, D2, 핀 2(A) → Net-(D2-A), 핀 1(C) → /RAW; F1 핀 2·SJ1 핀 1 → Net-(D2-A); U2 핀 1(IN)·JP6 핀 1 → /RAW; F1 핀 1·X1 핀 VBUS1 → UVCC; D2 원래 footprint import_input:SOD-323
  - corpus_txt/SS12 SERIES_R2305.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14 열: VRRM 40 V·IF 1 A·IFSM 40 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, SMA
  - corpus_txt/SS12 SERIES_R2305.txt, 2쪽, ELECTRICAL SPECIFICATIONS, SS14 VF 최대 0.50 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 200 µA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/SS12L SERIES_Q2103.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, SS14L 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파, 정격 부하에 중첩), TA=25°C 기본 조건; MECHANICAL DATA, Sub SMA
  - corpus_txt/SS12L SERIES_Q2103.txt, 2쪽, ELECTRICAL SPECIFICATIONS, SS14L VF 최대 0.55 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 400 µA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N5817 SERIES_H2104.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N5819 열: VRRM 40 V·IF 1 A·IFSM 30 A(8.3 ms 단발 반정현파), TA=25°C 기본 조건; MECHANICAL DATA, DO-41
  - corpus_txt/1N5817 SERIES_H2104.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N5819 VF 최대 0.60 V(IF=1 A·TJ=25°C·PW=0.3 ms); Reverse current @ rated VR 최대 1 mA(VR=40 V·TJ=25°C·PW=30 ms), Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: SS14 → SS12 SERIES_R2305.pdf (정확 일치 1행); SS14L → SS12L SERIES_Q2103.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n09 — D3를 삽입형 대신 표면실장으로 바꾸려 해. 같은 전원 경로에 쓸 대체 후보를 찾아 줘.

- 회로·대상: Franzininho DIY · D3 · 조건: D3에는 현재 TSC 1N4148을 사용한다. / USB와 U1 쪽 전원은 외부 스위치로 번갈아 공급하고 반대편 5V 레일의 최대 전압은 5V이다. / D3의 최대 부하 전류는 10mA이고 VF 허용값은 IF=10mA·TJ=25°C·0.3ms 펄스에서 1V 이하이다. / 역누설은 VR=20V·TJ=25°C·30ms 펄스 시험값으로 현재 부품과 비교한다. / 실온 25°C에서 사용하며 표면실장 부품에 맞춰 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: D3는 X1 USB VBUS에서 5V 레일로 직렬 연결된 역류 방지 다이오드이다(기준표 3.2). 조건은 VRRM(없으면 VR) ≥ 반대편 5 V × 1.25 = 6.25 V, IF(AV)(없으면 IF) ≥ 10 mA/0.7 = 14.286 mA, IR ≤ 원래 25 nA(VR=20 V·TJ=25°C·PW=30 ms), 사용자 지정 VF ≤ 1 V(IF=10 mA·TJ=25°C·PW=0.3 ms), 표면실장이다. 후보 1N4148W는 VRRM 75 V·IF 150 mA·해당 IR 최대 25 nA·VF 최대 1.00 V이고 SOD-123F라 역할상 충분이다. 후보 1N4148WS는 VRRM 100 V·IF 150 mA·동일 IR·VF 시험에서 각각 최대 25 nA·1.00 V이고 SOD-323F라 역할상 충분이다. 정격 기본 온도는 TA=25°C이며 1N4148W는 원래 VRRM 100 V보다 작고, 1N4148WS는 원래 PD 500 mW보다 작은 200 mW여서 주요 정격에 PD를 포함한 비교에서 사양 동등이 아니다. 둘 다 원래 DO-35 삽입형 footprint에서 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 원래 1N4148과 후보의 IR을 모두 VR=20 V·TJ=25°C·PW=30 ms로 대조했다. 전류가 낮아 원래 정격을 그대로 요구할 이유는 없다.
- 메모: 1N4148WS의 역할상 충분 판정은 원래 대비 주요 정격에 PD를 포함한 것이다. 주요 정격 목록이 아직 정해지지 않아(SPEC 5절), 사람이 PD 포함 여부와 최종 대체 판정 명칭을 확정해야 한다.
- 기계 대조: 원문에 없는 숫자: 6.25, 14.286
- 근거:
  - netlists/franz_c09.net, D3, 핀 A → Net-(D3-PadA), 핀 C → 5V; X1 핀 VBUS → Net-(D3-PadA), U1 핀 1 → 5V; D3 값 1N4148, footprint Franzininho:DIODE-1N4148
  - corpus_txt/1N4148W SERIES_K1804.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148W VRRM 75 V·IF 150 mA·PD 400 mW(TA=25°C); MECHANICAL DATA, SOD-123F
  - corpus_txt/1N4148W SERIES_K1804.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148W Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse leakage current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N4148WS SERIES_N2212.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148WS VRRM 100 V·IF 150 mA·PD 200 mW(TA=25°C); MECHANICAL DATA, SOD-323F
  - corpus_txt/1N4148WS SERIES_N2212.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148WS Forward voltage 최대 1.00 V(IF=10 mA·TJ=25°C·PW=0.3 ms); Reverse current 최대 25 nA(VR=20 V·TJ=25°C·PW=30 ms), Notes 1·2
  - corpus_txt/1N4148 SERIES_K2301.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148 VRRM 100 V·IF 150 mA·PD 500 mW(TA=25°C); MECHANICAL DATA, DO-35
  - corpus_txt/1N4148 SERIES_K2301.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148 VF 최대 1 V(IF=10 mA·TJ=25°C·PW=0.3 ms); IR 최대 25 nA(VR=20 V)·5 µA(VR=75 V), TJ=25°C·PW=30 ms, Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: 1N4148W → 1N4148W SERIES_K1804.pdf (정확 일치 1행); 1N4148WS → 1N4148WS SERIES_N2212.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n10 — D3 재고가 없어. 지금보다 역누설이 작은 부품 중에서 같은 역할을 할 대체 후보를 찾아 줘.

- 회로·대상: Franzininho DIY · D3 · 조건: D3에는 현재 TSC 1N4148을 사용한다. / USB와 U1 쪽 전원은 외부 스위치로 번갈아 공급하고 반대편 5V 레일의 최대 전압은 5V이며 D3의 최대 부하 전류는 80mA이다. / 전원 선택 우선순위를 다이오드 전압 강하로 정하지 않고 뒤 회로의 입력 여유도 별도로 확보한다. / 역누설은 VR=75V·25°C·30ms 펄스 시험에서 1µA 이하인 부품을 원한다. / 실온 25°C에서 사용하고 패키지가 달라지면 기판을 수정할 수 있다.
- Codex 판단: 관련, 확신 medium · **사람 확인 필요**
- Codex 정답: D3는 USB→5V의 역류 방지 다이오드이다(기준표 3.2). 조건은 VRRM(없으면 VR) ≥ 5 V × 1.25 = 6.25 V, IF(AV)(없으면 IF) ≥ 80 mA/0.7 = 114.286 mA, IR ≤ 1 µA(VR=75 V·TJ=25°C·PW=30 ms)이며 이는 원래 1N4148의 같은 시험값 최대 5 µA보다 작아야 한다. 전원 우선순위와 뒤 회로의 입력 여유를 별도로 확보하므로 VF는 필수 조건이 아니다. 후보 BAS16(SOT-23)은 VRRM 75 V·IF 150 mA(TA=25°C)·지정 조건의 IR 최대 1 µA라 역할상 충분이며 원래 VRRM 100 V보다 작다. 후보 BAS316(SOD-323)은 VR 100 V(문서가 VRRM 대신 VR을 명시)·IF 250 mA·PD 200 mW(TA=25°C)·지정 조건의 IR 최대 1.00 µA라 역할상 충분이며 원래 PD 500 mW에는 못 미친다. 둘 다 원래보다 보증 누설 상한을 5 µA→1 µA로 낮추고 전류 여유 기준을 충족하며, 원래 DO-35 footprint와 달라 기판 수정 필요다. 위 후보는 예시이며, 명시한 조건을 모두 만족하는 TSC 코퍼스에 있는 품번은 어느 것이든 정답으로 인정한다. 동일 동작은 보장하지 않는다.
- 이유: 낮은 누설을 요구해도 시험 전압·온도·펄스 폭이 다르면 비교하지 않는다. BAS116의 5 nA 수치는 30 ms 시험 조건이 명시되지 않아 이 문항의 확정 후보로 쓰지 않았다.
- 메모: BAS316의 역할상 충분 판정은 주요 정격에 PD를 포함한 것이다. 주요 정격 목록이 미확정이므로 사람이 판정 명칭을 확정해야 한다. BAS316 원문의 VR은 기준표가 허용한 대체 지표로 사용했다.
- 기계 대조: 원문에 없는 숫자: 6.25, 114.286
- 근거:
  - netlists/franz_c09.net, D3, 핀 A → Net-(D3-PadA), 핀 C → 5V; X1 핀 VBUS → Net-(D3-PadA), U1 핀 1 → 5V; D3 값 1N4148, footprint Franzininho:DIODE-1N4148
  - corpus_txt/BAS16_F2001.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, VRRM 75 V·IF 150 mA(TA=25°C); MECHANICAL DATA, SOT-23
  - corpus_txt/BAS16_F2001.txt, 2쪽, ELECTRICAL SPECIFICATIONS, Reverse current 최대 1 µA(VR=75 V·TJ=25°C); Notes 2, PW=30 ms
  - corpus_txt/BAS316_E1907.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, IF 250 mA·PD 200 mW(TA=25°C); KEY PARAMETERS, VR 100 V; MECHANICAL DATA, SOD-323
  - corpus_txt/BAS316_E1907.txt, 2쪽, ELECTRICAL SPECIFICATIONS, Reverse voltage 최소 100 V(IR=100 µA·TJ=25°C); Reverse current 최대 1.00 µA(VR=75 V·TJ=25°C); Notes 2, PW=30 ms
  - corpus_txt/1N4148 SERIES_K2301.txt, 1쪽, ABSOLUTE MAXIMUM RATINGS, 1N4148 VRRM 100 V·IF 150 mA·PD 500 mW(TA=25°C); MECHANICAL DATA, DO-35
  - corpus_txt/1N4148 SERIES_K2301.txt, 2쪽, ELECTRICAL SPECIFICATIONS, 1N4148 VF 최대 1 V(IF=10 mA·TJ=25°C·PW=0.3 ms); IR 최대 25 nA(VR=20 V)·5 µA(VR=75 V), TJ=25°C·PW=30 ms, Notes 1·2
  - 정답판정-기준표.md, 2절 기준값 출처·3절 kV=1.25·kI=1/0.7; SPEC.md, 3절 대체 판정 5종
  - tsc_datasheet_list.csv, parts 정확 일치: BAS16 → BAS16_F2001.pdf (정확 일치 1행); BAS316 → BAS316_E1907.pdf (정확 일치 1행)
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)

### n12 — D1을 방사선 시험용 보드에 쓸 부품으로 바꾸려 해. 총 이온화 선량 내성이 10krad(Si) 이상으로 명시된 대체 후보를 찾아 줘.

- 회로·대상: SparkFun Breadboard Supply · D1
- Codex 판단: 비관련(missing_attribute), 확신 medium · **사람 확인 필요**
- Codex 정답: 총 이온화 선량 내성 10 krad(Si) 이상이 명시된 후보는 코퍼스에서 확인할 수 없다는 자료 부재 안내가 정답이다. 방사선 내성 보증값을 일반 전압·전류 정격으로 추정하거나 조건을 무시한 후보를 제시하면 안 된다.
- 이유: [실측] tsc_datasheet_list.csv 전체 1,360행과 corpus_txt/*.txt 전체 1,360개를 대소문자 구분 없이 검색했다. 검색식 TID(단어 경계)|total\s+ioniz|krad|radiation은 CSV 0회, 원문 일치 줄 0건(0문서)이었고, 방사선|이온화|ionis|ioniz|rad\s*\(Si\)도 원문 0건이었다. 추천 후보에 요구한 속성 자체가 없어 missing_attribute를 우선 적용했다. 별도로 원래 넷리스트 값 1N4001은 CSV parts 정확 일치 0건이며 1N4001G와 혼동하지 않았다.
- 메모: 원래 1N4001의 CSV 정확 일치도 없지만 질문은 특정 품번 조회보다 특수 속성 조건의 후보 검색이다. missing_attribute를 우선한 분류가 평가 의도와 맞는지 확인해야 한다.
- 기계 대조: -
- 근거:
  - tsc_datasheet_list.csv, 전체 파일·parts 검색: TID|total ioniz|krad|radiation 0회; parts 정확 일치 1N4001 0건
  - corpus_txt/*.txt, 1,360개 전체 검색: TID(단어)|total\s+ioniz|krad|radiation 0줄·0문서
  - netlists/supply_breadboard.net, D1, 핀 A → Net-(S1-S), 핀 C → Net-(F1-1); S1 핀 3과 D1 A, F1 핀 P$1과 D1 C 연결; F1 핀 P$2 → RAW, U1 핀 IN → RAW; D1 원래 footprint import_input:DIODE-0.4
- 정운 확인(O / X와 맞는 결론): O (11-03)
- 재훈 확인(O / X와 맞는 결론): O (11-03)
