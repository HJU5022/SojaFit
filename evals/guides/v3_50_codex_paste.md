# SojaFit 평가셋 v3 50문항 — Codex용 (정답·채점 정보 없음)

아래 50건에 각각 답해 주세요. 형식은 문항마다:

```
### {id}
- 한 줄 결론
- 근거(있으면 수치·조건)
- 확신이 낮으면 모른다고 적기
```

규칙:
- 각 문항의 「회로/넷리스트 경로/대상/사용 조건/질문」만 보고 답한다.
- 데이터시트 PDF를 열어볼 수 없으면, 일반 지식으로 답하되 **추측이면 추측이라고** 밝힌다.
- 관련 없는 질문이면 거절·범위 밖이라고 답해도 된다.
- 50문항 모두 답한다. 한 덩어리로 이어서 출력한다.

---
## v3-01  (relevant · candidate_judge)

회로: ATtiny85 Time Switch
넷리스트: data/circuits/collected/received-20261030/c01/received/c01-attiny85-time-switch.net
대상: D1
사용 조건: VIN은 최대 15V, D1의 연속 전류는 최대 120mA이며 주변 온도는 25°C이다. PWM 없이 직류로 쓴다. 현재 부품은 넷리스트의 onsemi 1N4007RLG이고 제조사를 바꿔도 된다. 기판의 리드 간격은 수정할 수 있다. 이번 부품 승인에서 순방향 전압강하는 제한 항목으로 삼지 않는다. 투입 시 D1 전류는 초기 접합온도 25°C에서 피크 2A·폭 8.3ms의 단발 반정현파이다.
질문: 전원 입력의 D1을 TSC 1N4007G로 바꿔도 될까? 전기 조건과 실장 변경 여부를 같이 봐 줘.

---
## v3-02  (relevant · candidate_judge)

회로: FC ROM Vomitter
넷리스트: data/circuits/collected/received-20261030/c02/received/c02-fc-rom-vomitter.net
대상: D2
사용 조건: NES_5V와 USB VBUS는 각각 최대 5.25V이고 D2 경로 연속 전류는 최대 700mA이다. 주변 온도는 25°C이며 PWM은 없다. 현재 부품의 표기는 SS34지만 제조사는 확인하지 못했다. 후보 패키지에 맞춘 기판 수정은 가능하다. NES_5V만 공급할 때 D2에 허용되는 전압강하는 최대 0.8V이고, USB만 공급할 때 NES 쪽으로 흐르는 역류는 최대 100µA이어야 한다.
질문: SS34 대신 TSC SS24를 D2에 넣으면 두 전원을 번갈아 쓸 수 있겠어? 특히 꺼진 NES 쪽으로 새는 전류도 봐 줘.

---
## v3-03  (relevant · candidate_judge)

회로: ATtiny2313A Thermostat
넷리스트: data/circuits/collected/received-20261030/c03/received/c03-attiny2313a-thermostat.net
대상: D5
사용 조건: 릴레이 코일 전원은 최대 12.6V, 정상 코일 전류와 차단 직후 D5 초기 전류는 최대 35mA이다. PWM 없이 1초 이상 간격으로 켜고 끈다. 주변 온도는 25°C이다. 넷리스트의 D5 표기는 D지만, 현재 개조 보드에는 TSC LL4148 L0가 달려 있다. 이미 MiniMELF용으로 실장부를 바꿨으며 추가 기판 수정도 가능하다.
질문: 주문서에 LL4148 L0G라고 왔는데, D5에 쓰는 LL4148 L0 대신 이걸 받아도 같은 부품으로 취급할 수 있어?

---
## v3-04  (relevant · candidate_judge)

회로: tiny85 Fan Control
넷리스트: data/circuits/collected/received-20261030/c04/received/c04-tiny85fancontrol.net
대상: D1
사용 조건: 팬 전원은 최대 13.2V, 정상 전류와 차단 직후 초기 환류 전류는 최대 250mA이다. PWM은 20kHz, 주변 온도는 25°C이다. 현재는 제조사 미상의 1N4001이며 기판 리드 간격 변경이 가능하다. 후보는 역회복 시간 최댓값이 100ns 이하여야 한다. 다이오드 전압강하는 1.8V까지 허용한다.
질문: D1을 TSC UF4007로 바꾸려는데 이 PWM 조건에 맞을까? 내압만 보고 고르면 되는 건지 헷갈려.

---
## v3-05  (relevant · candidate_judge)

회로: UG56 PWM Controller
넷리스트: data/circuits/collected/received-20261030/c05/received/c05-ug56-pwm-controller.net
대상: D2
사용 조건: 모터 전원은 최대 12V이고 정상 전류와 차단 직후 초기 환류 전류는 최대 400mA이다. PWM은 25kHz, 주변 온도는 25°C이다. 현재 SS34의 제조사는 모르며 기판 수정은 가능하다. 역회복 시간 최댓값 100ns 이하를 부품 승인 조건으로 정했다. 전압강하는 1.5V까지 허용한다.
질문: 부품함에 TSC S1M이 있는데 D2 대신 써도 될까? 전압을 높게 견디는 부품이면 PWM 모터에도 쓸 만한지 봐 줘.

---
## v3-06  (relevant · candidate_judge)

회로: Car Radio ACC Delay
넷리스트: data/circuits/collected/received-20261030/c07/received/c07-car-radio-acc-delay.net
대상: D1
사용 조건: ACC IN은 최대 14.4V이고 R2는 1.5kΩ, R5는 20kΩ으로 넷리스트와 같다. PWM은 없고 주변 온도는 25°C이다. 원래 표기는 BZX84C3V3이지만 현재 개조 보드에는 TSC BZV55B3V3 L0가 달려 있다. MiniMELF용 기판으로 바꿨고 추가 기판 수정도 가능하다. 입력 검토에 쓰는 전압 범위는 제너 전류 5mA에서 3.20~3.40V이다.
질문: D1에 쓸 BZV55B3V3 L0 대신 TSC BZV55B3V3 L0G로 주문해도 괜찮아? 끝의 G 때문에 소자가 달라지는지 알고 싶어.

---
## v3-07  (relevant · candidate_judge)

회로: OverEngineered PSU
넷리스트: data/circuits/collected/received-20261030/c08/received/c08-overengineered-psu.net
대상: D1
사용 조건: 마이크로 USB VBUS는 최대 5.25V, D1의 연속 전류는 최대 250mA이며 주변 온도는 25°C이다. D1 경로에는 PWM이 없다. 현재 표기는 1N5819지만 실제 제조사는 알 수 없다. 기판의 0805 실장부를 후보 패키지에 맞춰 바꿀 수 있다. 전압강하는 0.9V까지 허용하고, 다른 전원으로 5V 넷을 공급할 때 USB 단자로 흐르는 역류는 100µA 이하여야 한다.
질문: USB 입력의 D1을 TSC SS16으로 바꾸고 싶어. 패키지는 새로 그릴 수 있는데 전원 경로의 역할도 유지될까?

---
## v3-08  (relevant · candidate_judge)

회로: tinydimmer
넷리스트: data/circuits/collected/received-20261030/c10/received/c10-tinydimmer.net
대상: D2
사용 조건: T1 2차는 최대 9Vrms·50Hz, 정류 출력 부하 전류는 최대 150mA이며 주변 온도는 25°C이다. 이 경로에는 PWM이 없다. 브리지 전체를 이전에 표면실장으로 개조했고 D2에는 현재 TSC SS14가 달려 있다. 넷리스트의 1N5819 표기는 개조 전 값이다. 후보에 맞춘 추가 기판 수정은 가능하다. 투입 시 D2에는 초기 접합온도 25°C에서 피크 3A·폭 8.3ms의 단발 반정현파가 흐른다.
질문: 브리지 D2를 TSC SS14H로 바꾸면 지금 쓰는 SS14와 같은 수준으로 사용할 수 있을까? H가 붙은 쪽으로 조달하려고 해.

---
## v3-09  (relevant · candidate_judge)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D2
사용 조건: 12V 넷의 정상 전압은 최대 13.0V이고 정상 상태에서 D2로 직류 부하 전류를 흘리지 않는다. PWM은 없으며 주변 온도와 펄스 직전 접합온도는 25°C이다. 기존 부품은 TSC SMBJ14A이다. 서지는 피크 10A의 단발 10/1000µs 파형이며 보호 노드에서 허용하는 전압은 최대 23.2V이다. 기판 수정은 가능하지만 보호 방향은 기존과 같아야 한다.
질문: D2의 SMBJ14A 대신 TSC SMBJ14AH를 쓰려는데 기존 보호 조건을 유지할 수 있어? 주문 품번 차이도 함께 설명해 줘.

---
## v3-10  (relevant · candidate_judge)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D4
사용 조건: /Left의 정상 신호는 0~5.0V이고 D4에는 정상 직류 부하 전류가 흐르지 않는다. 신호는 최대 2Hz로 전환되며 PWM은 없다. 주변 온도와 펄스 직전 접합온도는 25°C이다. 현재 부품은 TSC SMAJ5.0A이다. 양의 서지는 피크 5A의 단발 10/1000µs이고 보호 노드 허용 전압은 최대 9.2V이다. 음의 과도 전압에 대한 보호 방향도 기존과 같아야 한다. 기판 수정은 가능하다.
질문: D4를 TSC SMAJ6.0CA로 바꿔도 될까? 번호가 조금 높고 방향 구분도 덜 신경 써도 될 것 같아서 후보로 봤어.

---
## v3-11  (relevant · candidate_find)

회로: SparkFun Breadboard Supply
넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net
대상: D1
사용 조건: J1로만 최대 12V를 공급하고 S1은 켠다. D1 연속 전류는 최대 350mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4001의 제조사는 모르고 표면실장으로 기판을 바꿀 수 있다. 구매 규격은 TSC 일반 정류형, SMA(DO-214AC), 반복 피크 역전압 정격 400~600V, 평균 순방향 전류 정격 1A 이상 2A 미만이다. 정격은 데이터시트 표에 적힌 시험 조건 그대로 비교한다.
질문: D1의 입력 역극성 보호용 대체 후보를 위 구매 규격으로만 추려 줘. 각 후보의 전압·전류 정격과 패키지를 근거와 함께 알려 줘.

---
## v3-12  (relevant · candidate_find)

회로: Adafruit MOSFET Driver
넷리스트: data/circuits/collected/samples/mosfet_driver/converted/circuit.net
대상: D3
사용 조건: X1에 최대 24V·정상 전류 250mA인 코일 부하를 연결하며 끌 때 초기 환류 전류도 최대 250mA이다. PWM은 20kHz, 주변 온도는 25°C이다. 현재 표기는 1N400x/SM4002이며 제조사는 모르고 삽입형으로 기판을 바꿀 수 있다. 구매 규격은 TSC 고속 정류형, DO-41, 반복 피크 역전압 정격 400~600V, 평균 순방향 전류 정격 1A, 역회복 시간 최댓값 75ns 이하이다. 정격과 역회복 시간은 각 데이터시트 표에 적힌 시험 조건 그대로 비교한다.
질문: D3의 PWM 플라이백용 대체 후보를 위 구매 규격으로 추려 줘. 역회복 시간은 전형값이 아니라 표에 최댓값이 명시된 부품으로 골라 줘.

---
## v3-13  (relevant · candidate_find)

회로: Car Radio ACC Delay
넷리스트: data/circuits/collected/received-20261030/c07/received/c07-car-radio-acc-delay.net
대상: D1
사용 조건: ACC IN은 최대 14.4V, R2는 1.5kΩ, R5는 20kΩ이며 주변 온도는 25°C이다. PWM은 없고 이 노드는 고속 데이터선이 아니다. 현재 BZX84C3V3에서 기판을 바꿀 수 있다. 구매 규격은 TSC 단일 제너, 공칭 제너 전압 3.3V, 공차 ±2%인 B 등급, 전력 정격 500mW 이상이다. 패키지는 MiniMELF(MMELF) 또는 SOD-123F 중 하나여야 한다. 제너 전압과 전력은 각 데이터시트에 기재된 시험·정격 조건을 함께 확인한다.
질문: PB3 쪽 D1의 제너 클램프용 후보를 위 구매 규격으로 찾아 줘. 공칭 전압·공차 등급·전력 정격·패키지가 모두 맞는 부품만 알려 줘.

---
## v3-14  (relevant · candidate_find)

회로: HRem
넷리스트: data/circuits/collected/received-20261030/c11/received/c11-hrem.net
대상: D1
사용 조건: 입력 배터리는 최대 1.6V, 부스트 출력 VCC는 3.3V이다. D1 평균 전류는 최대 50mA, 스위칭 중 순방향 피크는 최대 200mA, 스위칭 주파수는 최대 100kHz이며 외부 PWM 제어는 사용하지 않는다. 주변 온도는 25°C이다. 현재 부품은 Vishay SS14-E3/61T이고 기판 수정은 허용하지 않는다. 구매 규격은 TSC 쇼트키 정류형, SMA(DO-214AC), 반복 피크 역전압 정격 40~60V, 평균 순방향 전류 정격 1A, AEC-Q101 적합 표기가 있는 제품이다. 정격은 데이터시트 표에 적힌 조건 그대로 비교한다.
질문: D1의 부스트 출력 정류용 후보를 위 구매 규격으로 골라 줘. SMA 패키지와 AEC-Q101 적합 여부도 문서 근거로 확인해 줘.

---
## v3-15  (relevant · candidate_find)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D3
사용 조건: /Stop의 정상 전압은 0~최대 5.0V이고 정상 상태에서 D3에 직류 부하 전류는 흐르지 않는다. PWM은 없으며 주변 온도와 펄스 직전 접합온도는 25°C이다. 현재는 SMAJ5.0A이고 SMA(DO-214AC) 기판 실장부를 바꿀 수 없다. 구매 규격은 TSC 단방향 TVS, 작동 스탠드오프 전압 5.0V, 10/1000µs 피크 펄스 전력 정격 400W 이상 600W 미만, 각 후보 정격 피크 펄스 전류에서 클램프 전압 최댓값 10V 이하이다. 실제 서지는 피크 5A의 단발 10/1000µs이다.
질문: D3 자리에 쓸 대체 후보를 찾아 줘. 양방향이나 더 큰 패키지는 이번에는 제외하고 위 조건을 전부 맞춰 줘.

---
## v3-16  (relevant · rating)

회로: Adafruit MOSFET Driver
넷리스트: data/circuits/collected/samples/mosfet_driver/converted/circuit.net
대상: D3
사용 조건: D3용 후보의 데이터시트 수치만 먼저 확인하는 단계다. 실제 코일에서 측정한 값이나 교체 적합성 판정은 요구하지 않는다.
질문: TSC UF4007의 trr 최댓값은 얼마야? 그 값이 어떤 순방향·역방향 전류와 측정 기준에서 나온 건지도 같이 알려 줘.

---
## v3-17  (relevant · rating)

회로: ATtiny85 dev board
넷리스트: data/circuits/collected/samples/attiny85_dev/converted/circuit.net
대상: D2
질문: TSC BZT52B4V7은 제너 전압을 어느 범위로 규정해? 그 범위를 확인할 때 흘리는 전류와 시험 펄스가 얼마나 긴지도 같이 봐 줘.

---
## v3-18  (relevant · rating)

회로: Franzininho DIY
넷리스트: data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net
대상: D1
사용 조건: 회로에 맞는지 판단하기 전 주문 코드의 의미만 확인하려고 한다.
질문: TSC BZV55B5V1을 주문할 때 L0와 L0G는 소자 자체가 같은지, 아니면 전기 규격이 달라지는지 궁금해. 제조사 문서에서 두 코드를 어떻게 구분하는지 알려 줘.

---
## v3-19  (relevant · rating)

회로: ATtiny85 dev board
넷리스트: data/circuits/collected/samples/attiny85_dev/converted/circuit.net
대상: D1
사용 조건: D1에 바로 교체할 수 있는지는 별도 검토하고 후보의 문서 해석만 확인한다.
질문: TSC SMAJ6.5CA의 역방향 누설전류 상한을 알고 싶어. 양방향 품번도 전기 특성 표의 수치를 그대로 읽으면 되는지, 적용할 별도 주석이 있으면 그 조건까지 알려 줘.

---
## v3-20  (relevant · rating)

회로: SparkFun Pro Micro v13
넷리스트: data/circuits/collected/samples/pro_micro/converted/circuit.net
대상: D2
질문: TSC SS14H를 봤는데 끝의 H는 무슨 차이를 나타내? SS14보다 더 큰 전류를 흘린다는 뜻인지, 다른 제품 구분인지 문서 기준으로 알려 줘.

---
## v3-21  (relevant · rating)

회로: SparkFun Breadboard Supply
넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net
대상: D1
질문: TSC 1N5408G는 전원을 처음 넣을 때처럼 잠깐 몰리는 큰 전류를 어디까지 견딘다고 돼 있어? 한 번만 흘리는 건지, 전류 파형과 지속 시간·온도 조건도 같이 알려 줘.

---
## v3-22  (relevant · role)

회로: FC ROM Vomitter
넷리스트: data/circuits/collected/received-20261030/c02/received/c02-fc-rom-vomitter.net
대상: D1
사용 조건: USB 전원과 NES_5V를 번갈아 연결한다. 부품 정격이나 교체 후보는 묻지 않는다.
질문: D1하고 D2가 같은 +5V 쪽으로 모이던데, 왜 두 개를 따로 달아 놓은 거야? D1의 양쪽 연결을 따라 설명해 줘.

---
## v3-23  (relevant · role)

회로: ATtiny2313A Thermostat
넷리스트: data/circuits/collected/received-20261030/c03/received/c03-attiny2313a-thermostat.net
대상: D1
사용 조건: LS1은 코일형 부저이며 Q1로 켜고 끈다.
질문: 부저 옆 D1은 평소에는 뭐 하고, Q1을 끄면 어떤 경로에 관여해? 넷리스트에서 LS1과 연결된 핀을 짚어 줘.

---
## v3-24  (relevant · role)

회로: OverEngineered PSU
넷리스트: data/circuits/collected/received-20261030/c08/received/c08-overengineered-psu.net
대상: D3
질문: D3가 USB 쪽에 붙어 있는데 전원에 직렬로 들어간 건 아닌 것 같아. J1에서 어느 신호를 받아 어디로 이어지는지 보고 D3가 왜 필요한지 설명해 줘.

---
## v3-25  (relevant · role)

회로: HRem
넷리스트: data/circuits/collected/received-20261030/c11/received/c11-hrem.net
대상: D1
사용 조건: BT1로 전원을 공급하고 U1이 동작하는 상태를 본다.
질문: 여기 D1은 L1 바로 뒤에 있네. 배터리에서 VCC로 가는 길을 따라 보면 D1이 왜 그 자리에 있는 거야?

---
## v3-26  (irrelevant · out_of_domain)

회로: ATtiny2313A Thermostat
넷리스트: data/circuits/collected/received-20261030/c03/received/c03-attiny2313a-thermostat.net
대상: D5
사용 조건: 릴레이 K1은 최대 12.6V로 구동하고 코일 전류는 최대 35mA이다. 주변 온도는 25°C이며 기판 수정은 가능하다. D5는 현재 부품을 유지한다.
질문: D5 교체를 검토하다가 릴레이부터 바꾸기로 했어. 같은 코일 조건으로 동작하면서 접점에 24V·2A를 스위칭할 수 있는 K1 대체 릴레이 후보를 골라 줘.

---
## v3-27  (irrelevant · out_of_domain)

회로: tiny85 Fan Control
넷리스트: data/circuits/collected/received-20261030/c04/received/c04-tiny85fancontrol.net
대상: D1
사용 조건: 팬 전원은 12V, 최대 전류는 250mA, PWM은 20kHz, 주변 온도는 25°C이다. D1과 Q1은 유지하고 별도 제어 회로 추가는 가능하다.
질문: D1 쪽을 손보는 김에 Q1을 구동할 게이트 드라이버 IC 후보를 찾아 줘. 3.3V 논리 입력을 받고 12V 게이트 구동을 할 수 있는 제품으로 골라 줘.

---
## v3-28  (irrelevant · out_of_domain)

회로: OverEngineered PSU
넷리스트: data/circuits/collected/received-20261030/c08/received/c08-overengineered-psu.net
대상: D1
사용 조건: 입력은 12V, 필요한 출력은 5V·1A, 주변 온도는 25°C이다. D1은 그대로 두고 전원 변환부의 기판 수정은 가능하다.
질문: D1 교체보다 IC1 MP2307을 바꾸는 게 먼저일 것 같아. 이 입력과 출력에 맞는 동기식 벅 컨버터 IC 대체 후보를 찾아 줘.

---
## v3-29  (irrelevant · out_of_domain)

회로: tinydimmer
넷리스트: data/circuits/collected/received-20261030/c10/received/c10-tinydimmer.net
대상: D1
사용 조건: 브리지와 D1은 현재대로 유지한다. 변압기 2차는 9Vrms·50Hz, 필요한 2차 전류는 200mA이며 주변 온도는 25°C이다. 변압기 실장부 수정은 가능하다.
질문: D1 앞의 T1을 교체하려고 해. 230V·50Hz 입력에서 위 2차 출력을 내고 절연이 확보되는 기판용 변압기 후보를 골라 줘.

---
## v3-30  (irrelevant · out_of_domain)

회로: Franzininho DIY
넷리스트: data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net
대상: D3
사용 조건: USB 전원 5V로 동작하고 D3는 유지한다. IC1은 넷리스트의 ATtiny85이며 펌웨어는 수정할 수 있다.
질문: D3 교체 대신 펌웨어 쪽을 먼저 보려고 해. 이 ATtiny85가 USB 소프트웨어 통신에 맞는 클록으로 뜨도록 퓨즈 바이트 설정 후보를 골라 줘.

---
## v3-31  (irrelevant · out_of_domain)

회로: SparkFun Pro Micro v13
넷리스트: data/circuits/collected/samples/pro_micro/converted/circuit.net
대상: D2
사용 조건: USB로만 5V를 공급하고 RAW는 연결하지 않는다. D2는 그대로 사용하며 커넥터 주변 기판 수정은 가능하다.
질문: D2를 바꾸기 전에 USB 커넥터를 USB-C로 바꾸고 싶어. USB 2.0 통신과 5V 입력을 유지할 커넥터 후보와 CC 저항 구성을 골라 줘.

---
## v3-32  (irrelevant · unknown_entity)

회로: ATtiny85 Time Switch
넷리스트: data/circuits/collected/received-20261030/c01/received/c01-attiny85-time-switch.net
대상: D1
사용 조건: VIN은 최대 12V, D1 연속 전류는 최대 100mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4007RLG를 쓰고 기판 수정은 가능하다.
질문: D1 후보로 TSC 1N5408X를 받았어. 이 정확한 품번의 역전압과 평균 전류 정격을 확인해서 써도 되는지 봐 줘.

---
## v3-33  (irrelevant · unknown_entity)

회로: FC ROM Vomitter
넷리스트: data/circuits/collected/received-20261030/c02/received/c02-fc-rom-vomitter.net
대상: D1
사용 조건: USB VBUS는 최대 5.25V, D1 연속 전류는 최대 300mA, 주변 온도는 25°C이며 PWM은 없다. 현재 표기는 SS34이고 기판 수정은 가능하다.
질문: USB 입력 D1을 TSC SS14J로 바꾸려는데 이 품번의 패키지와 전압·전류 정격을 봐 줘. 발주서에는 J까지 들어가 있어.

---
## v3-34  (irrelevant · unknown_entity)

회로: tiny85 Fan Control
넷리스트: data/circuits/collected/received-20261030/c04/received/c04-tiny85fancontrol.net
대상: D1
사용 조건: 팬은 최대 12V·200mA, PWM은 20kHz, 주변 온도는 25°C이다. 현재는 제조사 미상의 1N4001이며 기판 수정은 가능하다.
질문: D1 후보가 TSC UF4007X라고 적혀 있어. 이 정확한 품번의 역회복 시간과 전류 정격으로 교체를 판단해 줘.

---
## v3-35  (irrelevant · unknown_entity)

회로: Car Radio ACC Delay
넷리스트: data/circuits/collected/received-20261030/c07/received/c07-car-radio-acc-delay.net
대상: D1
사용 조건: ACC IN은 최대 14.4V, 주변 온도는 25°C이며 PWM은 없다. R2와 R5는 유지하고 현재 BZX84C3V3의 실장부는 수정할 수 있다.
질문: D1 대체품 목록에 TSC BZV55B3V4가 있던데 제너 전압 허용 범위와 시험 전류를 알려 줘. 이 품번 그대로 검토하려고 해.

---
## v3-36  (irrelevant · unknown_entity)

회로: Franzininho DIY
넷리스트: data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net
대상: D3
사용 조건: USB 전원은 최대 5.25V, D3 경로 전류는 최대 40mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4148이고 MiniMELF용 기판 수정은 가능하다.
질문: D3용 TSC LL4149의 전압강하 최댓값과 시험 전류가 어떻게 돼? LL4148 말고 발주서에 적힌 LL4149를 확인해 줘.

---
## v3-37  (irrelevant · unknown_entity)

회로: HRem
넷리스트: data/circuits/collected/received-20261030/c11/received/c11-hrem.net
대상: D1
사용 조건: 입력 배터리는 최대 1.6V, 부스트 출력은 3.3V, D1 평균 전류는 최대 50mA이다. 스위칭은 최대 100kHz, 주변 온도는 25°C이고 기판 수정은 가능하다. 현재는 SS14-E3/61T이다.
질문: D1 대체 후보로 TSC US1MX를 검토 중이야. 정확히 이 품번의 역전압·전류·역회복 정격을 찾아서 판단해 줘.

---
## v3-38  (irrelevant · unknown_entity)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D5
사용 조건: /Right 신호는 정상 0~5.0V이고 D5에는 정상 직류 부하 전류가 흐르지 않는다. PWM은 없고 주변 온도는 25°C이다. 현재는 SMAJ5.0A이며 패키지 변경은 가능하다.
질문: D5 후보 TSC SMBJ14AZ의 작동 전압과 클램프 전압은 얼마야? 납품 품번 끝의 AZ까지 포함해서 봐 줘.

---
## v3-39  (irrelevant · missing_attribute)

회로: ATtiny85 Time Switch
넷리스트: data/circuits/collected/received-20261030/c01/received/c01-attiny85-time-switch.net
대상: D1
사용 조건: VIN은 최대 12V, 연속 전류는 100mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4007RLG를 TSC 1N4006G로 교체한 c01 시제품 기판을 검토 중이다. 기판 수정은 가능하며 열 측정 기록은 따로 제공하지 않는다.
질문: 이 시제품을 위 조건으로 1시간 연속 가동한 뒤 D1 패키지 표면에서 실제로 측정된 온도가 몇 °C인지 알려 줘. 해당 기판의 실측 온도가 60°C 이하인지를 교체 승인 조건으로 확인해 줘.

---
## v3-40  (irrelevant · missing_attribute)

회로: FC ROM Vomitter
넷리스트: data/circuits/collected/received-20261030/c02/received/c02-fc-rom-vomitter.net
대상: D1
사용 조건: USB 전원은 5.0V, D1 경로 전류는 300mA, 주변 온도는 25°C이다. PWM 없이 동작하며 D1을 TSC SS24로 바꾼 시험 보드를 가정한다.
질문: D1을 SS24로 바꾼 이 FC ROM Vomitter 보드를 USB로 켰을 때의 전원 효율 실측값을 알려 줘. 부품 전압강하로 계산한 값 말고 이 보드를 측정한 수치가 필요해.

---
## v3-41  (irrelevant · missing_attribute)

회로: ATtiny2313A Thermostat
넷리스트: data/circuits/collected/received-20261030/c03/received/c03-attiny2313a-thermostat.net
대상: D1
사용 조건: 부저 전원은 최대 5.25V, 차단 직후 D1 초기 전류는 최대 20mA, 동작 빈도는 초당 1회, 주변 온도는 25°C이다. MiniMELF로 기판을 바꾸고 TSC LL4148을 장착한다고 가정한다.
질문: 이 부저 회로에서 LL4148을 계속 쓰면 고장 전까지 평균 몇 번 켜고 끌 수 있다는 수명 보장이 있어? 반복 횟수로 명시된 보장값이 있어야 후보를 승인할 수 있어.

---
## v3-42  (irrelevant · missing_attribute)

회로: OverEngineered PSU
넷리스트: data/circuits/collected/received-20261030/c08/received/c08-overengineered-psu.net
대상: D1
사용 조건: USB 입력은 5.0V, D1 연속 전류는 200mA, 주변 온도는 25°C이다. TSC SS14를 장착하도록 기판을 수정한 상태로 30~1000MHz 방사 시험을 한 보드를 가정한다.
질문: D1을 SS14로 바꾼 이 보드의 3m 거리 방사성 방출 실측 최댓값이 몇 dBµV/m인지 알려 줘. 부품 인증 문구 대신 이 보드의 시험 성적서 수치가 필요해.

---
## v3-43  (irrelevant · missing_attribute)

회로: HRem
넷리스트: data/circuits/collected/received-20261030/c11/received/c11-hrem.net
대상: D1
사용 조건: 입력 배터리는 1.5V, VCC는 3.3V, D1 평균 전류는 50mA, 스위칭은 100kHz, 주변 온도는 25°C이다. TSC SS16을 단면 1oz 동박 보드에 장착하고 30분 동작한 상태를 본다.
질문: 이 HRem 보드에서 SS16 몸체 표면을 열화상 카메라로 찍은 최고 온도가 몇 도였어? 데이터시트 열저항으로 계산하지 말고 그 실측값을 찾아 줘.

---
## v3-44  (irrelevant · missing_attribute)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D3
사용 조건: /Stop의 정상 전압은 최대 5.0V이고 현재 부품은 TSC SMAJ5.0A이다. 정상 직류 부하 전류와 PWM은 없고 주변 온도는 25°C이다. 납품 로트 번호는 QA-261106-A로 가정한다.
질문: 이 로트의 SMAJ5.0A 200개를 입고 검사했을 때 클램프 전압 측정값의 평균과 표준편차가 얼마였어? 로트 검사 성적의 두 숫자가 있어야 승인할 수 있어.

---
## v3-45  (irrelevant · wrong_period)

회로: SparkFun Breadboard Supply
넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net
대상: D1
사용 조건: J1 입력은 최대 12V, D1 연속 전류는 최대 200mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4001의 실장부는 수정할 수 있다. 이번 검토는 지정 판본만 사용한다.
질문: D1 후보 TSC S1J의 반복 역전압과 평균 전류를 S1A SERIES_S2202.pdf 판본에서 확인해 줘. 다른 개정판 수치로 대신하지 말아 줘.

---
## v3-46  (irrelevant · wrong_period)

회로: Adafruit MOSFET Driver
넷리스트: data/circuits/collected/samples/mosfet_driver/converted/circuit.net
대상: D3
사용 조건: X1 코일 전원은 최대 24V, 정상 전류와 초기 환류 전류는 최대 250mA, PWM은 20kHz, 주변 온도는 25°C이다. 현재 표기는 1N400x/SM4002이고 기판 수정은 가능하다.
질문: D3 교체 후보 TSC UF4005의 역회복 시간과 시험 조건을 UF4001 SERIES_P2204.pdf 판본 기준으로 알려 줘. 이번 부품 승인에는 그 개정 코드만 쓸 수 있어.

---
## v3-47  (irrelevant · wrong_period)

회로: ATtiny85 dev board
넷리스트: data/circuits/collected/samples/attiny85_dev/converted/circuit.net
대상: D2
사용 조건: USB 전원은 최대 5.25V이고 D2 노드의 제너 시험 전류는 5mA, 주변 온도는 25°C이다. 현재 표기는 3.6 Zener이고 기판 수정은 가능하다. 이번에는 부품 정격 조회만 한다.
질문: D2 후보 TSC BZT52B3V6의 제너 전압 범위를 BZT52B2V4 SERIES_F16.pdf에서 확인해 줘. 구매팀이 지정한 이 판본으로만 답해 줘.

---
## v3-48  (irrelevant · wrong_period)

회로: SparkFun Pro Micro v13
넷리스트: data/circuits/collected/samples/pro_micro/converted/circuit.net
대상: D2
사용 조건: USB 입력은 최대 5.25V, D2 연속 전류는 최대 100mA, 주변 온도는 25°C이다. RAW는 연결하지 않고 SJ1은 열어 둔다. D2 현재 표기는 DIODESOD이며 기판 수정은 가능하다.
질문: D2 후보 TSC SS26의 전압·전류 정격을 SS22 SERIES_N2406.pdf 개정판에서 확인하고 싶어. 다른 개정판은 검토서에 쓸 수 없어.

---
## v3-49  (irrelevant · wrong_period)

회로: tinydimmer
넷리스트: data/circuits/collected/received-20261030/c10/received/c10-tinydimmer.net
대상: D3
사용 조건: T1 2차는 최대 9Vrms·50Hz, 정류 부하 전류는 최대 100mA, 주변 온도는 25°C이다. 현재 D3 표기는 1N5819이며 기판 수정은 가능하다. 이번 조회는 전압·평균 전류 정격에 한정한다.
질문: 브리지 D3용 TSC SS14H를 검토 중인데 SS12H SERIES_B2405.pdf의 전압과 평균 전류 정격만 알려 줘. 내가 지정한 개정판이 아니면 사용하지 말아 줘.

---
## v3-50  (irrelevant · wrong_period)

회로: ZR7 Taillight
넷리스트: data/circuits/collected/received-20261030/c12/received/c12-zr7-taillight.net
대상: D5
사용 조건: /Right는 정상 0~5.0V이고 D5에는 정상 직류 부하 전류와 PWM이 없다. 주변 온도는 25°C이다. 현재는 SMAJ5.0A이며 기판 수정은 가능하다.
질문: D5 후보 TSC SMBJ5.0AH의 클램프 전압 최댓값을 SMBJH SERIES_A2202.pdf 판본으로 확인해 줘. 더 최신이든 예전이든 다른 파일의 값은 이번 검토에 쓰지 않아.

---
