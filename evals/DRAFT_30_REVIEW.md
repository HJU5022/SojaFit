# 난이도별 평가 문항 30건 — 검수용

2026-10-30. **문항 작성자 검수 완료 · 팀원 검수 요청 단계. 실행·동결 금지.** 관련/비관련은 작성 의도이며 확정 kind·expected·gold_chunks가 아니다.
원본 데이터는 [draft_30.jsonl](draft_30.jsonl), 작성 범위는 [작업서](../docs/specs/evaluation-draft-30.md)다.

## 검수 전 알아둘 점

- 모델에게는 회로·대상·필요한 사용 조건과 자연스러운 질문만 제공한다. 의도 분류·예상 답변·자료 부재 조건·검수 메모는 제공하지 않는다.
- 없는 품번·문서·개정판을 묻는 문항은 그대로 포함하되, 자료 부재 여부는 검수자가 고정 코퍼스에서 확인한다. 질문에 “없으면 거절”, “다른 문서로 답하지 마” 같은 지시를 넣지 않는다. 부재를 확인하기 위해 허위 PDF를 만들거나 원본 문서를 수정하지 않는다.
- 정보가 부족한 자연스러운 교체 질문도 포함한다. 안전한 부분 답변·추가 조건 질문과 최종 교체 확답을 구분해 검수한다.
- 난이도별 10건, 처음 계획은 관련 의도 5·비관련 의도 5였다. 11-01에 e08·m07을 관련으로 바꿔 관련 17·비관련 13이 됐고, 비관련은 범위 밖 3·없는 대상 2·없는 항목 5·기간/개정판 다름 3이다.
- 회로 규모에 따른 작성자 계획 난이도이며 모델 성공률 측정값이 아니다. 쉬운 없는 품번 질문이 Pro Micro를 쓴다고 어려워지는 것은 아니다.
- TSC 데이터시트 1,360건은 파싱·청킹을 마쳤지만 아직 색인되지 않았다(저장소에는 표본 3건). 관련 의도 문항도 필요한 공개 설명·규칙·정확한 후보 자료를 채워야 한다.
- 회로 조건 부족, 문서 속 값 부재, 사양 불충족은 서로 다르다. 최종 kind를 기계적으로 배정하지 않는다.
- 최신 SPEC 3절의 판정 5종과 답/거절 매핑은 정의됐다. 이 초안의 문항별 정답·근거 및 해당 판정 매핑은 팀원 검수 전이며, 원래 품번이 없을 때 동일품·사양 동등을 내지 않는 기준도 적용해야 한다.
- 예상 답변 방향은 AI의 검토 제안이다. 질문 작성자가 근거를 보지 않은 독립 평가셋이라고 주장하지 않는다. 사람 검수·독립 문항 작성 여부를 확인해야 한다.
- 원래 제조사를 모르는 회로 부품에 TSC 문서를 연결한 것은 조사 후보 지정이며 동일품 확인이 아니다.
- wrong_period의 개정판 적용은 합의 전이다. 질문 속 2026년 개정판은 실제 존재·발행·수집을 주장하지 않는다. 코퍼스에서 답을 찾으면 해당 의도 분류를 바꿔야 한다.
- MCU 없는 보드·Pro Micro는 서비스 지원 범위를 바꾸지 않는 탐색 초안이다. 정식 평가 채택 전 SPEC 범위를 팀과 합의한다.
- 유사한 역할·조건 질문은 family 및 회로·부품을 기준으로 묶어 분석하고, 개발용/최종 평가용에 근접 문항이 갈라지는 것을 피한다.

## 검수 방법

각 문항에서 질문의 명료성, 회로·참조번호·가정의 정확성, 난이도, 실제 코퍼스에서 답할 수 있는지, 예상 답변 방향을 확인한다. 정답 근거를 찾은 검수자는 PDF 해시·개정판·쪽·표·행 또는 회로 NET 해시·핀 연결 위치를 기록한다. 관련 문항의 gold_chunks는 그 뒤에 채운다. 비관련은 고정 코퍼스에서 부재를 확인한 뒤 확정한다.
최종 v1은 비관련 4유형을 충족하도록 재배치하고, 관련/비관련 반반은 11-02에 비관련 2건을 더하거나 v2에서 비관련을 더 넣어 맞춘다. 30행을 단순 복사해 동결하지 않는다.

## 쉬움 — MCU 없는 회로

### draft30-e01 · 관련 의도

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `series-path`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 전원은 J1 잭으로만 공급한다.

**질문:** 이 보드에서 D1은 왜 필요한 거야?

**예상 답변 방향:** D1의 방향과 연결을 근거로 역할과 보호 범위를 설명한다. 보드 전체의 모든 공급 경로를 보호한다고 확대하지 않는다.

**검수할 근거:** D1 핀 연결·원본 회로도·역극성 보호 설명 문서

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e02 · 관련 의도

- 회로: Adafruit MOSFET Driver · 대상 **D3** · family: `inductive-path`
- 입력: [NET](../data/circuits/collected/samples/mosfet_driver/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/mosfet_driver/converted/connections.json)
- 사용자 제공 조건: X1에 코일 부하인 모터를 연결한다.

**질문:** 모터를 끌 때 D3가 무슨 일을 하는 거야?

**예상 답변 방향:** D3와 Q1·부하 연결로 차단 직후 경로를 설명하고, 이를 실제 동작 보장과 구분한다.

**검수할 근거:** D3·Q1·X1 연결·플라이백 동작 설명 문서

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e03 · 관련 의도

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `datasheet-vrrm`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC 1N5817은 역전압을 몇 V까지 견뎌?

**예상 답변 방향:** 해당 후보의 정확한 표·단위·보장값을 인용한다. 이것만으로 교체 가능 판정을 내리지 않는다.

**검수할 근거:** TSC 1N5817 SERIES H2104의 정격 표

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e04 · 관련 의도

- 회로: Adafruit MOSFET Driver · 대상 **D3** · family: `forward-test-condition`
- 입력: [NET](../data/circuits/collected/samples/mosfet_driver/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/mosfet_driver/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC 1N4148을 쓰면 전압이 얼마나 떨어져?

**예상 답변 방향:** 후보 문서의 시험 조건과 값의 성격을 함께 제시하고 부하 조건을 임의로 채우지 않는다.

**검수할 근거:** TSC 1N4148 SERIES K2301의 전기 특성·시험 조건

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e05 · 관련 의도

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `package-drawing`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC 1N5819는 패키지가 뭐고 방향은 어떻게 보면 돼?

**예상 답변 방향:** 후보의 패키지 도면·극성을 인용하고 원본 footprint와 실제 패드 적합성 확인을 구분한다.

**검수할 근거:** TSC 1N5817 SERIES H2104 패키지 도면·후보 주문 정보

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e06 · 비관련 의도 / out_of_domain

- 회로: Adafruit MOSFET Driver · 대상 **Q1** · family: `replace-mosfet`
- 입력: [NET](../data/circuits/collected/samples/mosfet_driver/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/mosfet_driver/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** Q1 AO3406 대신 쓸 MOSFET 좀 골라 줘.

**예상 답변 방향:** 다이오드 대체 범위를 벗어난 요청임을 알리고 MOSFET 적합성을 임의 판정하지 않는다.

**검수할 근거:** SPEC 다이오드 범위·Q1 식별

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e07 · 비관련 의도 / unknown_entity

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `unknown-1n4001`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC 1N4001의 정격 좀 알려 줘.

**예상 답변 방향:** 지정 문서가 없으면 자료 부재를 밝힌다. 다른 계열의 값을 해당 부품 값으로 대입하지 않는다.

**검수할 근거:** 고정 코퍼스에 1N4001 자료가 실제 없는지 확인

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e08 · 관련 (11-01 변경, 처음 의도는 비관련 / unknown_entity. 코퍼스에 SS34 데이터시트가 있음)

- 회로: Adafruit MOSFET Driver · 대상 **D3** · family: `unknown-ss34`
- 입력: [NET](../data/circuits/collected/samples/mosfet_driver/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/mosfet_driver/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D3 대신 SS34를 보는데, 이 부품 정격이 어떻게 돼?

**예상 답변 방향:** SS34라는 이름만으로 제조사를 보충하거나 다른 쇼트키 문서를 대신 인용하지 않는다.

**검수할 근거:** 코퍼스 SS34 문서 유무·정확한 제조사 식별

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e09 · 비관련 의도 / missing_attribute

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `board-measured-drop`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** 이 보드 D1의 전압강하 실측값이 얼마야?

**예상 답변 방향:** 실측 기록과 데이터시트 정격을 구분하고 실측값을 만들어 내지 않는다.

**검수할 근거:** 해당 완성 보드 측정 기록의 존재 여부

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-e10 · 비관련 의도 / wrong_period

- 회로: SparkFun Breadboard Supply · 대상 **D1** · family: `requested-new-edition-easy`
- 입력: [NET](../data/circuits/collected/samples/breadboard_supply/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/breadboard_supply/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC 1N5817의 2026년판 데이터시트에서 역전압 정격이 얼마야?

**예상 답변 방향:** 요청한 개정판을 확보하지 않았다면 그 한계를 밝힌다. 해당 개정판의 실존을 질문이 보장하지 않는다.

**검수할 근거:** 요청 연도 문서 유무·문서 내부 개정판·발행 정보

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

## 중간 — ATtiny85

### draft30-m01 · 관련 의도

- 회로: ATtiny85 dev board · 대상 **D1** · family: `usb-zener-role`
- 입력: [NET](../data/circuits/collected/samples/attiny85_dev/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/attiny85_dev/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D1은 여기서 무슨 역할이야?

**예상 답변 방향:** 데이터선과 GND 연결·극성을 확인해 역할을 설명하고 전원 경로 보호와 혼동하지 않는다.

**검수할 근거:** D1 연결·회로도·제너/클램프 설명 문서

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m02 · 관련 의도

- 회로: Franzininho DIY · 대상 **D3** · family: `usb-supply-path`
- 입력: [NET](../data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net), [연결 JSON](../data/circuits/collected/received-20261030/c09/connections.json)
- 사용자 제공 조건: USB만 연결하고 J1에는 전원을 연결하지 않는다.

**질문:** USB로 전원을 넣으면 D3랑 레귤레이터를 어떤 순서로 거치는 거야?

**예상 답변 방향:** 받은 NET의 D3·5V·USB 연결과 U1 관계를 추적한다. 레귤레이터를 반드시 통과한다고 단정하지 않는다.

**검수할 근거:** c09 원본 NET·회로도·D3 역할 설명 근거

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m03 · 관련 의도

- 회로: ATtiny85 dev board · 대상 **D1** · family: `zener-test-current`
- 입력: [NET](../data/circuits/collected/samples/attiny85_dev/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/attiny85_dev/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** TSC BZT52C3V6은 전압이 딱 3.6V로 고정되는 거야?

**예상 답변 방향:** 해당 계열의 C3V6 행과 시험 조건을 정확히 찾아 전압 이름만으로 판정하지 않는다.

**검수할 근거:** TSC BZT52C2V4 SERIES G1804의 C3V6 행·표 주석

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m04 · 관련 의도

- 회로: ATtiny85 dev board · 대상 **D1** · family: `zener-footprint`
- 입력: [NET](../data/circuits/collected/samples/attiny85_dev/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/attiny85_dev/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D1 자리에 TSC BZT52C3V6을 그대로 납땜해도 돼?

**예상 답변 방향:** 원본 DO-34 계열 footprint와 후보 도면을 구분하고 패드·극성·기판 수정 확인을 제시한다.

**검수할 근거:** 원본 D1 footprint·TSC BZT52 계열 패키지 도면

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m05 · 관련 의도

- 회로: Franzininho DIY · 대상 **D3** · family: `current-constraint`
- 입력: [NET](../data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net), [연결 JSON](../data/circuits/collected/received-20261030/c09/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D3 대신 TSC 1N4148을 쓰려는데 전류를 얼마나 흘려도 돼?

**예상 답변 방향:** 정격의 연속·펄스 구분과 조건을 인용하고 부하 정보가 있어야 하는 항목을 짚는다.

**검수할 근거:** TSC 1N4148 SERIES K2301의 전류 정격·주석

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m06 · 비관련 의도 / out_of_domain

- 회로: Franzininho DIY · 대상 **IC1** · family: `replace-mcu`
- 입력: [NET](../data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net), [연결 JSON](../data/circuits/collected/received-20261030/c09/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** 이 보드 ATtiny85 대신 다른 MCU를 그대로 꽂아 쓸 수 있어?

**예상 답변 방향:** 현재 다이오드 대체 범위를 벗어난 요청으로 안내하고 MCU 교체를 보장하지 않는다.

**검수할 근거:** SPEC 범위·c09 IC1 식별

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m07 · 관련 (11-01 변경, 처음 의도는 비관련 / unknown_entity. 코퍼스에 BZX84C3V3 데이터시트가 있음)

- 회로: ATtiny85 dev board · 대상 **D1** · family: `unknown-bzx84`
- 입력: [NET](../data/circuits/collected/samples/attiny85_dev/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/attiny85_dev/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D1 후보로 BZX84C3V3을 봤는데 정격이 어떻게 돼?

**예상 답변 방향:** 다른 3.3V·3.6V 제너의 값을 가져와 해당 후보의 근거로 삼지 않는다.

**검수할 근거:** 고정 코퍼스 BZX84C3V3 자료 존재 여부

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m08 · 비관련 의도 / missing_attribute

- 회로: Franzininho DIY · 대상 **D1** · family: `unknown-original-order-code`
- 입력: [NET](../data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net), [연결 JSON](../data/circuits/collected/received-20261030/c09/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** 이 보드 D1은 어느 회사 제품이고 몇 V짜리야?

**예상 답변 방향:** 일반 계열명과 실제 제조사·전압 등급을 구분하고 관행으로 빈 BOM을 채우지 않는다.

**검수할 근거:** 제작자 BOM·조립 기록에 실제 식별 정보가 있는지 확인

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m09 · 비관련 의도 / missing_attribute

- 회로: ATtiny85 dev board · 대상 **D1** · family: `usb-compliance-measurement`
- 입력: [NET](../data/circuits/collected/samples/attiny85_dev/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/attiny85_dev/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D1을 TSC BZT52C3V6으로 바꾼 보드의 USB 시험 결과가 있어?

**예상 답변 방향:** 데이터시트 특성과 실제 보드 시험·인증 결과를 구분한다. 이 변경의 시험 기록이 없으면 통과를 단정하지 않는다.

**검수할 근거:** 해당 교체 실물의 USB 시험 기록 존재 여부

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-m10 · 비관련 의도 / wrong_period

- 회로: Franzininho DIY · 대상 **D3** · family: `received-vs-later-revision`
- 입력: [NET](../data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net), [연결 JSON](../data/circuits/collected/received-20261030/c09/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** Franzininho DIY 2026년 개정판에서는 D3를 뭘로 써?

**예상 답변 방향:** 받은 NET·확보한 PDF와 요청한 연도 개정판을 구분하고 미래·미확보 자료를 추측하지 않는다.

**검수할 근거:** 2026년 회로 개정판 실존·수집 여부, 받은 NET 및 PDF 버전

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

## 어려움 — Pro Micro v13

### draft30-h01 · 관련 의도

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `jumper-path-pair`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: USB만 연결하고 RAW에는 전원을 연결하지 않는다.

**질문:** USB로 쓸 때 SJ1을 붙이거나 떼면 전원 경로가 어떻게 달라져?

**예상 답변 방향:** 두 상태에서 실제 NET과 점퍼 연결을 따라 경로를 비교하고 변환된 기본 NET만으로 점퍼 상태 변경을 관측했다고 주장하지 않는다.

**검수할 근거:** v13 원본 회로·NET·SJ1 주석·MIC5219 관련 공개 근거

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h02 · 관련 의도

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `source-path-pair`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: USB 단독 공급과 RAW 단독 공급을 비교한다.

**질문:** SJ1을 열어 두면 USB 전원이랑 RAW 전원이 D2를 지나는 방식이 달라?

**예상 답변 방향:** D2 방향과 U2의 입출력 경로를 나누어 설명하고 전체 역류 방지를 D2 하나에 돌리지 않는다.

**검수할 근거:** v13 원본 연결·전원 사용 설명

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h03 · 관련 의도

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `voltage-budget`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: USB 5V 공급, SJ1 개방 상태다.

**질문:** D2를 TSC 1N5819로 바꾸면 VCC에는 최소 몇 V가 나와?

**예상 답변 방향:** 회로 경로로 필요한 조건을 나열하고 후보의 VF 시험 조건을 인용한다. 정보 없이 VCC 최솟값이나 최종 적합성을 계산하지 않는다.

**검수할 근거:** v13 공급 경로·TSC 1N5817 계열 VF 조건·허용된 U2 보장 근거 필요

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h04 · 관련 의도

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `schematic-vs-assembly`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** D2를 TSC 1N5819로 바로 바꿔 달아도 돼?

**예상 답변 방향:** D2 footprint와 후보 패키지를 비교하되 동일품이라고 단정하지 않는다. 전기 조건 판정과 기판 수정 필요를 별도로 설명한다.

**검수할 근거:** v13 D2 value·SOD-323 footprint·TSC 후보 도면·정격

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h05 · 관련 의도

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `same-family-different-vrrm`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: RAW만 공급하고 SJ1은 열어 둔다.

**질문:** TSC 1N5817이랑 1N5819는 같은 계열인데 D2에는 아무거나 써도 돼?

**예상 답변 방향:** 두 후보의 서로 다른 행·정격을 인용하고 요구값 없이 최종 교체 판정을 내리지 않는다.

**검수할 근거:** v13 NET·TSC 1N5817 SERIES H2104의 개별 품번 정격

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h06 · 비관련 의도 / out_of_domain

- 회로: SparkFun Pro Micro v13 · 대상 **U3** · family: `firmware-for-power-path`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** 이 보드의 USB 부트로더를 수정해 줘.

**예상 답변 방향:** 다이오드 대체 판정 범위를 벗어난 펌웨어 개발·동작 보장 요청을 구분한다.

**검수할 근거:** SPEC 지원 범위·U3 식별

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h07 · 비관련 의도 / unknown_entity

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `unknown-ss1p3l`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** USB랑 RAW를 번갈아 쓰는데 D2 후보 SS1P3L의 정격은 어떻게 돼?

**예상 답변 방향:** 공급 경로가 복잡해도 없는 후보 문서를 다른 부품 문서로 대체하지 않는다.

**검수할 근거:** 고정 코퍼스 SS1P3L 문서 유무·제조사 정책

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h08 · 비관련 의도 / missing_attribute

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `measured-backfeed`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: SJ1은 열어 둔다.

**질문:** USB랑 RAW를 같이 꽂았을 때 USB 쪽 역류 전류를 측정한 값이 있어?

**예상 답변 방향:** 시험 설정·측정 기록 부재를 밝히고 후보 역누설 정격을 보드 전체 역류 실측값으로 바꾸지 않는다.

**검수할 근거:** 동시 공급 조건의 실측 로그·보드 버전·시험 조건

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h09 · 비관련 의도 / missing_attribute

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `bill-of-materials-original`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** 이 Pro Micro의 D2는 원래 어느 회사의 무슨 품번을 써?

**예상 답변 방향:** 심볼명·footprint로 제조사·주문 코드를 확정하지 않고 생산 BOM·실장 이력이 필요한 점을 설명한다.

**검수할 근거:** 해당 커밋·생산 버전의 실제 BOM과 실장 기록

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

### draft30-h10 · 비관련 의도 / wrong_period

- 회로: SparkFun Pro Micro v13 · 대상 **D2** · family: `different-board-revision`
- 입력: [NET](../data/circuits/collected/samples/pro_micro/converted/circuit.net), [연결 JSON](../data/circuits/collected/samples/pro_micro/converted/connections.json)
- 사용자 제공 조건: 별도 조건 없음

**질문:** Pro Micro 2026년 USB-C판에서는 D2랑 전원 점퍼 구성이 어떻게 바뀌었어?

**예상 답변 방향:** v13 및 다른 보드의 USB-C 회로를 요청 개정판의 자료로 혼용하지 않는다. 해당 버전의 실존도 확인 대상이다.

**검수할 근거:** 요청 연도·커넥터·개정판의 실제 문서 유무; wrong_period와 unknown_entity 경계 검수

- [ ] 질문·가정·참조번호 / 관련성·난이도 / 답변 방향·근거 검수

## 확정 전 남은 일

1. 작성자 1차 검수 후 질문·가정과 난이도 배분 수정.
2. 필요한 후보 PDF·공개 설명·규칙을 확보하고 코퍼스 버전 고정.
3. 독립 질문 작성 여부 점검 및 두 사람의 정답·근거 교차 검수.
4. SPEC의 회로 범위 확대 합의와 최신 판정 정의에 따른 문항별 채점 기준 검수.
5. 최종 kind·expected·why·gold_chunks·corpus_version을 채운 뒤 별도로 v1 동결·베이스라인 측정.
