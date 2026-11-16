## v3-01
- 결론: 제시된 전기 조건에서는 TSC 1N4007G로 교체할 수 있다. 다만 기존 풋프린트의 실장 적합성을 확인하고 필요하면 변경해야 한다.
- 근거: TSC 정격은 순방향 1A, 반복 역전압 1000V, 8.3ms 단발 반정현파 서지 30A이므로 각각 120mA, 역전압 15V 이하, 피크 2A 조건을 충족한다. DO-41 몸체 길이는 최대 5.20mm, 리드 지름은 최대 0.86mm이므로 기존 A-405·7.62mm 간격에서 홀 지름, 리드 굽힘 및 주변 공간을 확인해야 한다. 넷리스트만으로 실제 기판 치수는 확인할 수 없다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/1N4001G%20SERIES_P2104.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/1N4001G%20SERIES_P2104.pdf))

## v3-02
- 결론: TSC SS24로 교체해 두 전원을 번갈아 쓰는 방식은 가능하지만, USB만 쓸 때 NES 쪽 역류가 100µA 이하라고 보장할 수는 없습니다. 역류가 중요한 조건이라면 저누설 역류 차단회로를 검토하세요.
- 근거: 넷리스트상 D2의 A는 NES_5V, K는 공통 +5V에 연결됩니다. SS24는 40V·2A 정격이고 접합온도 25°C, 2A 펄스에서 순방향 전압 최대 0.50V이지만, 역누설은 40V·접합온도 25°C에서 최대 400µA로 규정되어 5.25V에서의 100µA 이하 최대치는 확인되지 않습니다. 주변 25°C가 접합온도 25°C를 보장하지 않으며, NES 신호선을 통한 다른 역급전도 별도 확인해야 합니다. 기존 SMA를 후보의 SMB 패키지에 맞춰 수정해야 하며, 기존 SS34는 제조사 미확인으로 비교할 수 없습니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/SS22%20SERIES_N2306.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SS22%20SERIES_N2306.pdf))

## v3-03
- 결론: 네. 주문품이 Taiwan Semiconductor(TSC)의 정품 LL4148 L0G라면 기존 LL4148 L0와 같은 부품으로 받아 D5에 사용할 수 있습니다.
- 근거: 제조사 데이터시트는 L0와 L0G를 물리적으로 차이가 없는 동일 부품이라고 명시합니다. MMELF, 역전압 정격 75V, 순방향 전류 정격 150mA로 주어진 12.6V·최대 35mA 조건에 여유가 있습니다. D5의 캐소드는 +12V 쪽으로 실장해야 하며, 전원 과도전압은 제공되지 않아 별도 확인이 필요합니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf))

## v3-04
- 결론: TSC UF4007은 주어진 20kHz PWM 조건에 적합한 교체 후보입니다. 내압뿐 아니라 역회복 시간, 전류·전압강하 및 발열도 확인해야 합니다.
- 근거: D1은 팬 양단의 환류 다이오드이며 K는 +12V, A는 Q1 드레인에 연결됩니다. TSC 데이터시트상 UF4007은 내압 1000V, 순방향 전류 1A, 역회복 시간 최대 75ns(IF=0.5A, IR=1A, Irr=0.25A), 순방향 전압 최대 1.7V(IF=1A, 접합온도 25°C)로 제시 조건에 여유가 있습니다. DO-41 패키지이며, 실제 회로의 스위칭 파형과 발열은 별도 확인해야 합니다. 기존 1N4001은 제조사 미상이라 역회복 시간을 확인할 수 없습니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf))

## v3-05
- 결론: TSC S1M은 D2 대체품으로 승인하지 마세요. 높은 역전압 정격만으로 PWM 환류 다이오드에 적합하다고 판단할 수 없습니다.
- 근거: 넷리스트상 D2는 모터 양단의 환류 다이오드이며, MOSFET이 켜질 때 역회복 전류가 발생할 수 있습니다. TSC는 S1M을 1000V·평균 1A·SMA 표준 정류기로 명시하지만, 역회복 시간은 1500ns로 기재해 승인 기준 100ns 이하를 충족한다고 볼 수 없습니다. 해당 제품 페이지에는 이 시간의 측정 조건과 최댓값 여부가 명시되지 않았습니다. 기존 SS34의 제조사도 불명입니다. 출처: https://www.taiwansemi.com/en/products/S1M/ ([taiwansemi.com](https://www.taiwansemi.com/en/products/S1M/))

## v3-06
- 결론: 네, BZV55B3V3 L0G로 주문해도 됩니다. G가 붙어도 기존 L0와 같은 소자이지만, 회로의 입력 보호는 별도로 확인해야 합니다.
- 근거: TSC는 L0와 L0G가 물리적으로 동일하다고 명시하며, 25°C에서 5mA 기준 제너 전압은 3.23~3.37V, 정격은 500mW입니다. ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/BZV55B2V4%20SERIES_G2301.pdf)) 출처: https://services.taiwansemi.com/storage/resources/datasheet/BZV55B2V4%20SERIES_G2301.pdf ; 14.4V에서 D1 전류는 약 7.2mA, D1 손실은 약 24mW로 추정되지만, 실제 동작전압은 5mA 범위로 보장되지 않습니다. PB3 전압과 특히 MCU 전원 꺼짐 시 역급전 가능성은 별도 검증이 필요합니다.

## v3-07
- 결론: SS16은 USB 전원 공급 경로에는 사용할 수 있지만, 요구된 역류 100µA 이하까지 보장되는 대체품인지는 확인되지 않습니다.
- 근거: 넷리스트에서 D1은 J1 VBUS→애노드, 5V 넷→캐소드이며, SS16은 SMA 패키지, 60V·1A, 순방향 1A·접합온도 25°C에서 최대 0.75V입니다. 역전류는 60V·접합온도 25°C에서 최대 200µA로 규정되어 5V에서의 100µA 이하를 보장하지 않습니다. 주변온도 25°C가 접합온도 25°C를 뜻하지도 않습니다. 또한 R8을 통한 J1 D+ 역급전 가능성도 별도 확인해야 합니다. TSC 데이터시트: https://services.taiwansemi.com/storage/resources/datasheet/SS12%20SERIES_R2305.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SS12%20SERIES_R2305.pdf))

## v3-08
- 결론: 네, 제시된 조건에서는 TSC SS14H를 현재 SS14와 대체로 같은 수준으로 사용할 수 있습니다. 다만 실제 기판의 방열과 역전압 스파이크는 확인해야 합니다.
- 근거: 두 제품 모두 40V, 1A, SMA이며, SS14H의 단발 8.3ms 반정현파 서지 정격은 40A로 제시된 3A보다 큽니다. 9Vrms의 피크는 약 12.7V이고 부하 150mA는 1A보다 작지만, 충전 전류 파형·기판 온도·스파이크는 넷리스트만으로 확인할 수 없습니다. 제조사 자료: https://www.taiwansemi.com/en/products/SS14/ 및 https://services.taiwansemi.com/storage/resources/datasheet/SS12H%20SERIES_B2305.pdf ([taiwansemi.com](https://www.taiwansemi.com/en/products/SS14/))

## v3-09
- 결론: 부품 정격상 SMBJ14AH로 보호 조건을 유지할 수 있지만, 보호 노드에서 23.2V 이하가 된다는 것은 배선 기생 성분을 포함해 검증해야 합니다. 극성은 기존과 같이 캐소드를 12V, 애노드를 GND에 연결하세요.
- 근거: 두 부품 모두 단방향 SMB, 역방향 동작전압 14V, 10/1000µs 단발 정격 600W이며 27A에서 최대 클램프 전압 23.2V입니다. 따라서 25°C의 10A 펄스는 정격 이내이나, 10A에서의 정확한 클램프 전압과 기판 전압 상승은 확인되지 않았습니다. 주문 시 SMBJ14A의 H 추가형인 **SMBJ14AH**는 AEC-Q101 차량용이고, **SMBJ14CAH**는 양방향이므로 같은 보호 방향의 대체품이 아닙니다. 넷리스트의 D2 설명·데이터시트는 SMAJ6.5A용이라 실제 부품 근거로 쓸 수 없습니다. ([taiwansemi.com](https://www.taiwansemi.com/en/products/SMBJ14A/))

## v3-10
- 결론: 아니요. SMAJ6.0CA는 기존 단방향 부품과 음의 과도 보호 특성이 달라 직접 대체할 수 없습니다.
- 근거: D4는 /Left–GND 사이에 있으며, 기존 SMAJ5.0A는 10/1000µs에서 43.5A일 때 최대 9.2V로 규정됩니다. 후보는 양방향이고 38.8A에서 최대 10.3V이지만, 이 수치만으로 5A에서 9.2V 초과 여부를 단정할 수는 없습니다. 기존 단방향 부품의 실제 실장 극성과 음의 과도 조건도 확인해야 합니다. ([taiwansemi.com](https://www.taiwansemi.com/en/products/SMAJ6.0CA/))

## v3-11
- 결론: 확인된 TSC 대체 후보는 S1G·S1J, S1GH·S1JH, S1G-K·S1J-K, S1G-T·S1J-T, GS1G·GS1J, TSD1G, S2GA·S2JA, S2GAH·S2JAH이다. 모두 SMA(DO-214AC)이며, 기존 관통홀 풋프린트는 변경해야 한다.
- 근거: 각 쌍에서 첫 모델은 반복 피크 역전압 400V, 둘째는 600V이고 TSD1G는 400V다. 순방향 전류 정격은 S1·GS1·TSD1G가 1A, S2가 1.5A다. 데이터시트 표는 별도 명시 없으면 주변온도 25°C에서의 순방향 전류 IF로 표기하므로 이를 임의로 다른 시험 조건의 정격으로 바꾸지 않았다. 출처: S1 ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/S1A%20SERIES_S2102.pdf)), GS1 ([taiwansemi.com](https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=GS1M)), TSD1G ([taiwansemi.com](https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=TSD1G)), S2 ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/S2AA%20SERIES_K2102.pdf)). 넷리스트상 D1은 J1→S1→D1→F1 경로에 직렬이며, 실제 기판의 방열 조건과 기존 1N4001 제조사는 확인되지 않았다.

## v3-12
- 결론: TSC **HER105G** 또는 **HER106G**를 D3 대체 후보로 추천합니다. 기존 SOD-123 풋프린트는 DO-41용으로 변경해야 합니다.
- 근거: HER105G는 400V·역회복 최대 50ns, HER106G는 600V·최대 75ns이며, 둘 다 DO-41·순방향 전류 정격 1A입니다. 표의 역회복 시험 조건은 25°C, IF=0.5A, IR=1A, Irr=0.25A입니다. 실제 20kHz·250mA 조건의 파형과 손실은 별도 확인이 필요합니다. 제조사 데이터시트: https://services.taiwansemi.com/storage/resources/datasheet/HER101G%20SERIES_L2104.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/HER101G%20SERIES_L2104.pdf))

## v3-13
- 결론: 구매 규격에 맞는 TSC 단일 제너 후보는 **BZV55B3V3**(MiniMELF)와 **BZT52B3V3**(SOD-123F)이다. 기판 풋프린트 변경이 필요하다. ([taiwansemi.com](https://www.taiwansemi.com/en/products/BZV55B3V3/))
- 근거: 두 제품 모두 B 등급 3.3V ±2%, 500mW이며, 제너 전압은 25°C·시험전류 5mA에서 3.23~3.37V이다. 500mW 정격은 25°C 기준이고, BZT52B는 전극을 주변 온도로 유지하는 조건이 명시되어 있다. ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/BZV55B2V4%20SERIES_G2301.pdf)) 회로에서 PB3 입력전류를 무시하고 3.3V로 클램프된다고 가정하면 D1 전류는 약 7.24mA, 전력은 약 24mW이나, 실제 클램프 전압은 시험전류 조건과 다를 수 있다.

## v3-14
- 결론: D1 후보로 TSC **SSL14H** 쇼트키 정류기를 권장합니다. 기존 SMA 풋프린트에 맞는 패키지이지만, 실제 기판의 패드 치수와 실장 여유는 최종 확인이 필요합니다.
- 근거: 데이터시트에 SMA(DO-214AC), AEC-Q101 적합, VRRM 40V, 순방향 전류 1A가 명시되어 있습니다. VF는 접합온도 25°C, IF=1A에서 최대 0.39V이며, 이는 사용 조건의 피크 200mA에서의 보장값이 아닙니다. 평균 50mA는 1A보다 낮지만, 100kHz 반복 피크와 실제 스파이크에 대한 검증은 별도로 필요합니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/SSL12H%20SERIES_B2304.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SSL12H%20SERIES_B2304.pdf))

## v3-15
- 결론: TSC의 **SMAJ5.0AH, SMAJ5.0H, SMAJ5.0**을 D3 대체 후보로 사용할 수 있습니다. 단방향 극성은 캐소드(띠)를 /Stop에, 애노드를 GND에 맞춰 실장하세요.
- 근거: 세 제품 모두 SMA(DO-214AC), 스탠드오프 5.0V, 10/1000µs 400W입니다. SMAJ5.0AH는 43.5A에서 최대 9.2V, 나머지 두 제품은 41.7A에서 최대 9.6V이며, 주어진 25°C 단발 5A는 정격 전류 이내입니다. 5A에서의 정확한 클램프 전압은 확인하지 못했습니다. 5.0V에서 역방향 누설은 최대 800µA입니다. 제조사 데이터시트: ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SMAJ%20SERIES_U2102.pdf))

## v3-16
- 결론: TSC UF4007의 역회복시간 \(t_{rr}\) 최댓값은 **75 ns**입니다.
- 근거: 순방향 전류 \(I_F=0.5\) A, 역방향 전류 \(I_R=1.0\) A, 역회복 측정 기준 전류 \(I_{rr}=0.25\) A이며, 별도 명시가 없으면 주변 온도 25°C 기준입니다. 출처: TSC 데이터시트 2쪽, https://services.ts.com.tw/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf ([services.ts.com.tw](https://services.ts.com.tw/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf))

## v3-17
- 결론: TSC BZT52B4V7의 제너 전압 범위는 **4.61~4.79 V**입니다. 시험 펄스의 길이는 확인하지 못했습니다.
- 근거: TSC 데이터시트의 조건은 주변 온도 25°C, 시험 전류 5 mA이며 공칭 전압은 4.70 V입니다. 확인한 자료에는 펄스 길이가 제시되어 있지 않습니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/BZT52B2V4%20SERIES_F15.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/BZT52B2V4%20SERIES_F15.pdf)) 넷리스트의 D2는 “3.6 Zener”로 기재되어 있어 BZT52B4V7이 실제 장착된 부품인지는 확인할 수 없습니다.

## v3-18
- 결론: L0와 L0G는 전기 규격이 다른 소자가 아니라, 물리적으로 동일한 소자를 가리키는 주문 코드입니다. ([mouser.com](https://www.mouser.com/datasheet/2/395/BZV55B2V4_2520SERIES_G2301-3228592.pdf))
- 근거: TSC 데이터시트는 L0/L0G가 차이 없는 동일 부품이라고 명시합니다. 구판 주문표에서 L0는 포장 코드, G는 그린 컴파운드 표시입니다. BZV55B5V1의 공통 규격은 제너 전압 5.1V(시험 전류 5mA), 허용오차 ±2%, 500mW입니다. 제조사 제품 정보: https://www.taiwansemi.com/en/products/BZV55B5V1/ ; 데이터시트의 코드 설명은 검색 색인에서 확인했습니다. ([mouser.com](https://www.mouser.com/datasheet/2/395/BZV55B2V4_2520SERIES_G2301-3228592.pdf))

## v3-19
- 결론: TSC SMAJ6.5CA의 역방향 누설전류 상한은 1,000 µA입니다. 양방향 품번에는 표의 수치를 그대로 적용하지 않습니다. ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SMAJ%20SERIES_U2102.pdf))
- 근거: TSC 데이터시트 U2102의 SMAJ6.5A 행은 VWM=6.5 V에서 최대 500 µA이며, 양방향 제품 중 VR이 10 V 이하이면 누설전류 상한을 2배로 적용한다는 주석이 있습니다. 전기 특성은 양 방향에 적용되며, 별도 지정이 없으면 주변온도 25°C 조건입니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/SMAJ%20SERIES_U2102.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SMAJ%20SERIES_U2102.pdf))

## v3-20
- 결론: SS14H의 H는 더 큰 전류 정격이 아니라 자동차용 AEC-Q101 인증 제품을 구분하는 것으로 보입니다. 제조사가 H의 문자 자체를 정의한 설명은 확인하지 못했습니다.
- 근거: TSC 제품 자료에서 SS14H와 SS14는 모두 평균 순방향 전류 1A, 반복 피크 역전압 40V이며, AEC-Q 표기는 각각 Yes와 No입니다. ([taiwansemi.com](https://www.taiwansemi.com/zh_tw/products/SS14H/)) SS14H는 SMA 패키지이므로, 넷리스트의 D2용 SOD-323 풋프린트에 직접 맞지 않습니다. ([taiwansemi.com](https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=SS14H)) 출처: https://www.taiwansemi.com/zh_tw/products/SS14H/ , https://www.taiwansemi.com/en/products/SS14/

## v3-21
- 결론: TSC 1N5408G의 비반복 순방향 서지 전류 한계는 조건부로 피크 125 A입니다. 다만 넷리스트의 D1은 1N4001이므로 이 수치를 D1에 그대로 적용할 수 없습니다.
- 근거: TSC 데이터시트의 조건은 주위온도 25°C(별도 명시 없을 때), 정격 부하 전류에 중첩된 지속시간 8.3 ms의 단일 반사인파입니다. 비반복 정격은 반복 펄스에 대한 정격이란 뜻이 아니며, 소자 수명 중 단 한 번만 허용된다는 뜻도 아닙니다. 접합 온도 범위는 −55~150°C이며, 실제 기동 전류의 파형·온도·반복 조건이 다르면 125 A를 그대로 적용할 수 없습니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/1N5400G%20SERIES_K2105.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/1N5400G%20SERIES_K2105.pdf))

## v3-22
- 결론: D1과 D2는 USB와 NES 전원을 각각 공통 +5V 레일에 공급하면서, 사용하지 않는 쪽 전원으로 역류하는 것을 막기 위한 다이오드 OR 구성이다.
- 근거: 제공된 circuit.net에서 D1의 애노드 2번은 USB-C J2의 VBUS, 캐소드 1번은 +5V에 연결된다. D2는 J1 36번의 NES_5V에서 +5V로 연결된다. 따라서 USB 사용 시 D1이 공급하고 D2가 NES 쪽 역류를 막으며, NES 사용 시 D2가 공급하고 D1이 USB 쪽 역류를 막는다. 공통 +5V는 U25를 거쳐 +3V3을 만들며, 다이오드의 순방향 전압 강하 때문에 입력 전압과 정확히 같지는 않다.

## v3-23
- 결론: D1은 Q1이 켜져 부저에 전류가 흐를 때 역방향으로 차단된다. Q1을 끄면 코일 전류의 순환 경로를 제공해 Q1 컬렉터의 전압 급등을 억제한다.
- 근거: 제공된 circuit.net에서 LS1 P는 D1 1번(K) 및 R22를 거쳐 +5V에 연결되고, LS1 N은 D1 2번(A) 및 Q1 1번(C)에 연결된다. 차단 직후 전류 경로는 LS1 P → LS1 N → D1 A → D1 K → LS1 P이며, R22는 100Ω이다. 데이터시트와 실제 부품의 정격 적합성은 확인하지 않았다.

## v3-24
- 결론: D3는 전원 직렬 다이오드가 아니라 USB D− 신호를 GND에 대해 제한하는 제너 다이오드다. 5V로 동작하는 U1의 신호가 USB 측으로 나갈 때 전압을 낮추려는 구성으로 보인다. ([obdev.at](https://www.obdev.at/products/vusb/index.html))
- 근거: 넷리스트상 J1 2번(D−)은 D3의 K와 R10에 연결되고, R10 66.5Ω을 거쳐 U1 2번(PB3)으로 이어진다. D3의 A는 GND에 연결되며, 공칭 제너 전압은 3.6V이지만 실제 제한 전압은 전류에 따라 달라진다. D+에도 같은 역할의 D2가 있다. 제조사 자료: https://www.diodes.com/datasheet/download/BZT52CxxT.pdf ; 유사 구성 설명: https://www.obdev.at/products/vusb/index.html ; 실제 펌웨어와 USB 규격 적합성은 넷리스트만으로 확인할 수 없다. ([diodes.com](https://www.diodes.com/spice/download/839/BZT52C3V6T.spice.txt))

## v3-25
- 결론: D1은 단순한 배터리 직렬 보호용이 아니라, U1·L1과 함께 승압 회로를 이루는 정류 다이오드입니다. L1의 에너지를 VCC로 전달하고, 반대 방향의 전류는 막습니다.
- 근거: 넷리스트에서 L1은 BT1의 양극과 U1의 LX 사이에 있고, D1의 애노드는 LX, 캐소드는 VCC에 연결됩니다. U1의 스위치가 켜질 때 L1에 에너지가 쌓이고 D1은 VCC의 역방전을 막으며, 꺼질 때 L1 전류가 D1을 거쳐 C2(22µF)와 부하로 흐릅니다. U1은 3.3V 승압기이며 D1은 손실이 낮은 쇼트키 다이오드입니다. Holtek 데이터시트: https://akizukidenshi.com/goodsaffix/HT77xxa.pdf ([akizukidenshi.com](https://akizukidenshi.com/goodsaffix/HT77xxa.pdf))

## v3-26
- 결론: Omron G6RL-1 DC12를 K1 대체 후보로 추천합니다. 24V·2A 저항성 부하에 적합하나, 기판 배선과 실제 구동 조건을 확인해야 합니다.
- 근거: 코일은 12V, 654Ω±10%이므로 12.6V에서 최대 약 21.4mA이며, 접점은 SPDT·30V DC 5A 및 250V AC 8A 저항성 정격입니다. 동작 전압은 최대 8.4V이지만 최소 공급전압은 주어지지 않았고, D5·Q7의 실제 정격도 넷리스트에서 확인되지 않습니다. J3의 COM/NO/NC 배선은 새 릴레이 핀 배치에 맞춰 확인해야 합니다. 데이터시트: https://omronfs.omron.com/en_US/ecb/products/pdf/en-g6rl.pdf ([omronfs.omron.com](https://omronfs.omron.com/en_US/ecb/products/pdf/en-g6rl.pdf))

## v3-27
- 결론: Q1용 로사이드 게이트 드라이버 후보는 **TI UCC27517A** 또는 **Microchip MCP1407**이다. 둘 다 3.3V 논리 입력과 12V 전원 구동에 적합하며, D1과 Q1을 유지할 수 있다.
- 근거: 두 제품의 전원 범위는 4.5~18V이며, 피크 구동 전류는 각각 4A와 6A다. 20kHz PWM에 대해 데이터시트의 전형적인 지연은 각각 13ns와 40ns다. ([ti.com](https://www.ti.com/lit/ds/symlink/ucc27517a.pdf)) 출처: https://www.ti.com/lit/ds/symlink/ucc27517a.pdf , https://ww1.microchip.com/downloads/en/DeviceDoc/20002019C.pdf ; 드라이버 입력을 PWM에 연결하고 출력을 R2를 거쳐 Q1 게이트에 연결하며, 공통 GND와 12V측 근접 바이패스 커패시터를 사용한다. 넷리스트의 U1 전원은 3.3V가 아닌 5V이고, Q1의 값은 IRF3808이나 심벌·데이터시트는 IRF3205이므로 실제 부품과 게이트 전압 정격을 확인해야 한다. D1의 20kHz 동작 적합성은 확인하지 않았다.

## v3-28
- 결론: 대체 후보는 동기식 벅 IC **TI TPS54202**입니다. 다만 넷리스트상 5V 레일은 IC1이 아닌 IC2가 공급하므로, 그 출력을 개선하려면 IC2 쪽을 검토해야 합니다.
- 근거: TPS54202는 입력 4.5~28V, 출력 조정 범위 0.6~26V, 연속 2A로 12V→5V·1A에 맞습니다(https://www.ti.com/product/TPS54202). ([ti.com](https://www.ti.com/product/TPS54202)) 기존 MP2307도 동기식이며 4.75~23V·3A 정격이므로 조건만으로 교체가 우선이라고 단정할 수 없습니다(https://www.monolithicpower.com/en/mp2307.html). ([monolithicpower.com](https://www.monolithicpower.com/en/mp2307.html)) TPS54202는 6핀으로 기판과 인덕터·커패시터·피드백을 재설계해야 합니다. D1은 USB 입력과 5V 레일 사이에 있어 12V 벅 출력 경로에는 직렬로 있지 않으며, 실제 부품과 열 성능은 확인되지 않았습니다.

## v3-29
- 결론: 기판용 절연 변압기 후보로 **Myrra 44194**를 권합니다. 다만 RV1과 기판 절연을 검토하기 전에는 230V를 인가하지 마세요.
- 근거: 44194는 230V·50/60Hz 입력, 정격 9V·356mA, 3.2VA, 절연 시험 4kV이며 25°C에서 사용 가능합니다. 9V는 정격 전류 조건의 값이고 무부하 시 12V로 명시되어 있어 200mA에서 정확히 9V인지는 확인되지 않았습니다. ([myrra.com](https://myrra.com/wp-content/uploads/2024/03/44193-44204-EI38-x-13.6-230-V-3.2-VA-Datasheet.pdf)) 데이터시트: https://myrra.com/wp-content/uploads/2024/03/44193-44204-EI38-x-13.6-230-V-3.2-VA-Datasheet.pdf ; 기존 RV1의 제조사는 미확인이나 동종 Bourns 14D271K는 연속 175Vac 정격이므로 230V 사용에 부적합합니다. ([bourns.com](https://www.bourns.com/docs/Product-Datasheets/MOV14D.pdf)) 자료: https://www.bourns.com/docs/Product-Datasheets/MOV14D.pdf ; 실제 2차 RMS 전류·발열과 PCB 연면거리·공간거리도 확인해야 합니다.

## v3-30
- 결론: 클록 설정 후보는 **Low fuse 0xE1**이다. High·Extended fuse는 현재 값을 먼저 읽어 유지하고, 펌웨어에서 16.5MHz용 USB 코드와 오실레이터 보정을 사용하라.
- 근거: 0xE1은 내부 PLL 기반 약 16MHz와 CKDIV8 해제 설정이며, 16.5MHz는 퓨즈만으로 보장되지 않는다. ([github.com](https://github.com/ArminJo/micronucleus-firmware)) D3가 USB VBUS와 IC1 VCC 사이에 있으므로 실제 VCC를 측정하라. ATtiny85의 20MHz 속도 등급은 VCC 4.5~5.5V 조건이며, 넷리스트만으로 D3 전압강하나 USB 통신 성공은 확인할 수 없다. ([ww1.microchip.com](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/Atmel-2586-AVR-8-bit-Microcontroller-ATtiny25-ATtiny45-ATtiny85_Datasheet.pdf)) 확인한 출처: https://github.com/ArminJo/micronucleus-firmware ; https://github.com/obdev/v-usb/blob/master/libs-device/osccal.h ; https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/Atmel-2586-AVR-8-bit-Microcontroller-ATtiny25-ATtiny45-ATtiny85_Datasheet.pdf

## v3-31
- 결론: GCT USB4085-GF-A USB 2.0 Type-C 리셉터클을 후보로 선택하고, CC1과 CC2를 각각 별도의 5.1 kΩ 저항으로 GND에 연결한다. D+ 두 핀은 기존 X1 D+에, D− 두 핀은 기존 X1 D−에 각각 합쳐 연결하고, VBUS와 GND는 기존 X1의 해당 네트에 연결한다.
- 근거: USB4085-GF-A는 16접점 스루홀형이므로 새 풋프린트와 기판 수정이 필요하다(https://gct.co/connector/usb4085). ([gct.co](https://gct.co/connector/usb4085)) 넷리스트상 D+·D−는 각각 기존 22 Ω R5·R7을 거치고, USB 전원은 F1을 거쳐 SJ1이 닫혀 있으면 VCC에 공급되며 D2는 RAW 쪽 분기에 있다. D2의 실제 품번·정격과 기판 실측 치수는 확인되지 않았다. CC 저항만으로 1.5 A 또는 3 A 사용을 전제하지 말고 USB 전원·열거 조건과 실제 부하를 확인해야 한다(https://e2e.ti.com/support/interface-group/interface/f/interface-forum/628168/tusb321ai-usb-pd-adapter-in-use-is-a-cc-chip-for-5v-3a-required-or-are-pull-down-resistors-sufficient). ([e2e.ti.com](https://e2e.ti.com/support/interface-group/interface/f/interface-forum/628168/tusb321ai-usb-pd-adapter-in-use-is-a-cc-chip-for-5v-3a-required-or-are-pull-down-resistors-sufficient))

## v3-32
- 결론: TSC 1N5408X의 정확한 정격을 확인하지 못해 D1 대체 사용은 보류하세요. 공급자에게 해당 품번의 데이터시트를 요청해야 합니다.
- 근거: D1은 VIN과 U2 입력 사이의 직렬 다이오드이며, 조건은 최대 12V·연속 100mA·25°C·PWM 없음입니다. TSC의 별도 품번 1N5408G는 반복 피크 역전압 1000V, 순방향 전류 3A이지만 이를 1N5408X에 적용할 수는 없습니다; 확인한 자료: https://services.taiwansemi.com/storage/resources/datasheet/1N5400G%20SERIES_K2105.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/1N5400G%20SERIES_K2105.pdf))

## v3-33
- 결론: TSC SS14J의 제조사 자료를 확인하지 못해 패키지·정격 및 D1 대체 가능 여부는 판단 보류입니다. 발주처에 J까지 포함된 정확한 제조사 데이터시트를 요청하세요.
- 근거: 넷리스트상 D1은 VBUS→+5V 경로이며 기존 풋프린트는 SMA입니다. TSC의 J 없는 SS14는 SMA, 역전압 40V, 평균 순전류 1A이지만 SS14J에 적용할 수 없습니다(https://www.taiwansemi.com/en/products/SS14/). ([taiwansemi.com](https://www.taiwansemi.com/en/products/SS14/)) 다른 제조사 LGE의 SS14J는 SMAJ·40V·1A로 표기되어 있어 품번만으로 동일성을 판단할 수 없습니다(https://www.lgesemi.com/products_details/1541537314997813248.html). ([lgesemi.com](https://www.lgesemi.com/products_details/1541537314997813248.html)) 역방향 전압과 기동 돌입전류 조건도 확인이 필요합니다.

## v3-34
- 결론: TSC **UF4007X**의 정확한 품번과 정격을 확인하지 못해 교체를 승인할 수 없다. 제조사 확인 후 교체하거나, 별도 품번인 TSC UF4007을 대안으로 검토하라.
- 근거: D1은 팬 양단의 플라이백 다이오드다. 확인된 **UF4007**은 25°C에서 순방향 전류 1A, 역회복 시간 최대 75ns(IF=0.5A, IR=1A, Irr=0.25A)로, 200mA 팬과 20kHz 주기 50µs에 비추어 유력한 대안이다. 다만 이 수치를 UF4007X에 적용할 수는 없으며, 팬 기동·피크 전류와 실제 파형은 확인되지 않았다. 제조사 자료: https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=UF4007 ([taiwansemi.com](https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=UF4007))

## v3-35
- 결론: TSC BZV55B3V4의 제너 전압 허용 범위와 시험 전류는 확인하지 못했습니다. 이 품번 그대로 제조사에 사양을 확인해야 합니다.
- 근거: TSC 시리즈 데이터시트에는 BZV55B3V4가 없으며, BZV55B3V3과 BZV55B3V6 사이 전압의 제품은 제조사에 문의하도록 안내합니다. BZV55B3V3의 참고값은 3.23~3.37V, 시험 전류 5mA이지만 BZV55B3V4의 사양은 아닙니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/BZV55B2V4%20SERIES_G2301.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/BZV55B2V4%20SERIES_G2301.pdf))

## v3-36
- 결론: TSC LL4149의 순방향 전압강하 최댓값과 시험 전류는 확인하지 못했습니다. LL4148의 수치를 LL4149에 적용할 수 없습니다.
- 근거: 확인한 TSC 자료는 LL4148·LL4448·LL914B용이며 LL4149는 포함하지 않습니다. 따라서 주어진 40mA, 주변 25°C 조건에서 LL4149의 전압강하도 확인할 수 없습니다. 자료: https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf))

## v3-37
- 결론: TSC **US1MX의 정확한 정격을 확인하지 못해**, D1 대체품으로 승인할 수 없습니다. 품번이나 제조사 자료를 확인한 뒤 기동·효율·피크 전류를 검증해야 합니다.
- 근거: 제조사 자료에서 확인한 **US1M은 US1MX가 아닌 별도 품번**이며, 반복 피크 역전압 1000V, 순방향 전류 1A, 역회복시간 최대 75ns입니다. 이 값을 US1MX에 적용할 근거는 찾지 못했습니다. US1M 자료의 “US1x”는 x가 전압 등급을 나타내는 표기입니다: https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=US1M ([taiwansemi.com](https://www.taiwansemi.com/assets/datasheet/pdf.php?pn=US1M))

## v3-38
- 결론: TSC SMBJ14AZ의 정확한 납품 품번을 확인하지 못해 작동 전압과 클램프 전압을 확정할 수 없습니다. SMBJ14A와 동일한 전기적 사양이라면 각각 14V와 최대 23.2V입니다.
- 근거: 확인한 TSC 자료는 SMBJ14A를 다루지만 끝의 Z가 포함된 품번과 그 의미는 확인하지 못했습니다. SMBJ14A의 클램프 전압은 규정된 펄스전류 조건의 값이며, D5는 /Right와 GND 사이에 연결되어 있습니다. ([mouser.com](https://www.mouser.com/datasheet/2/395/SMBJ_SERIES_Q2004-1918376.pdf))

## v3-39
- 결론: D1의 1시간 후 실제 표면 온도는 알 수 없으며, 60°C 이하라는 교체 승인 조건도 확인할 수 없어 승인을 보류해야 합니다.
- 근거: 제공된 circuit.net에는 실측 온도가 없고, 100mA 부하 전류가 모두 D1을 통과하는 구조도 아닙니다. c01 기판을 VIN 12V, 연속 부하 100mA, 주변 25°C, PWM 없이 1시간 가동한 뒤 D1 패키지 표면을 직접 측정해 60°C 이하인지 확인해야 합니다.

## v3-40
- 결론: D1을 TSC SS24로 교체한 시험 보드의 전원 효율 실측값은 확인할 수 없습니다.
- 근거: 제공된 circuit.net에는 USB 5.0V, D1 전류 300mA, 주변 25°C, PWM 없는 조건의 실측 데이터가 없으며, 공개 자료 검색에서도 해당 시험 결과를 찾지 못했습니다. 효율을 알려면 측정 범위를 정하고 USB 입력과 해당 출력의 전력을 실측해야 합니다.

## v3-41
- 결론: 제시된 조건에서 고장 전 평균 작동 횟수나 반복 횟수 보장값을 확인할 수 없어, 요구된 승인 기준을 충족하지 못합니다.
- 근거: D1은 부저 LS1과 병렬로 연결되어 있습니다. TSC 데이터시트의 25°C 정격은 반복 피크 역전압 75V, 순방향 전류 150mA이지만 작동 수명 횟수는 명시하지 않습니다. 5.25V·초기 20mA·1회/초 조건만으로는 평균 수명을 산출할 수 없으며, 전류 파형과 펄스 지속시간도 미확인입니다. 출처: https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/LL4148%20SERIES_K2301.pdf))

## v3-42
- 결론: 해당 보드의 3m 거리 방사성 방출 실측 최댓값은 알 수 없습니다.
- 근거: USB 5.0V, D1 200mA, 25°C 및 30~1000MHz 조건만으로는 실측값을 결정할 수 없습니다. 제공된 넷리스트에 시험 결과가 없고 웹 검색에서도 해당 보드의 성적서를 확인하지 못했으므로, 수정된 보드의 시험 성적서가 필요합니다.

## v3-43
- 결론: 요청한 조건에서의 SS16 몸체 표면 최고 온도 실측값은 확인하지 못했습니다.
- 근거: 제공된 넷리스트에는 온도 측정 기록이 없고 D1은 SS16이 아닌 SS14-E3/61T로 기재되어 있습니다. HRem 저장소 검색 결과에서도 해당 열화상 실측값을 찾지 못했습니다. 출처: https://github.com/bazhenov/hrem ([github.com](https://github.com/bazhenov/hrem))

## v3-44
- 결론: 로트 QA-261106-A의 클램프 전압 평균과 표준편차는 모두 확인할 수 없어 승인 판단을 보류해야 합니다.
- 근거: 제공된 circuit.net에는 D3가 SMAJ5.0A로 기재되어 있으나, 해당 로트 200개의 측정값과 클램프 시험 전류·파형이 없습니다. 로트 검사 성적서 또는 측정 원자료가 필요합니다.

## v3-45
- 결론: 지정된 S1A SERIES_S2202.pdf 판본을 열람하지 못해 TSC S1J의 반복 역전압과 평균 전류를 확인할 수 없습니다. 따라서 D1 적합성도 판정할 수 없습니다.
- 근거: 입력 최대 12V, 연속 전류 최대 200mA, 주변 온도 25°C 조건은 주어졌지만 지정 판본의 정격과 비교할 수 없습니다. 검색에서 확인된 자료는 다른 판본인 S2102이며, 그 수치는 대신 사용하지 않았습니다: https://www.mouser.com/datasheet/2/395/S1A_SERIES_S2102-2821864.pdf ([mouser.com](https://www.mouser.com/datasheet/2/395/S1A_SERIES_S2102-2821864.pdf))

## v3-46
- 결론: 지정된 P2204 판본을 확인하지 못해 UF4005의 역회복 시간과 시험 조건을 승인용 수치로 제시할 수 없습니다. 해당 PDF를 제공해 주세요.
- 근거: 검색에서 확인된 TSC 자료는 P2104로, 요청한 개정 코드와 다릅니다. 검색 결과 URL: `https://services.ts.com.tw/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf` ([services.ts.com.tw](https://services.ts.com.tw/storage/resources/datasheet/UF4001%20SERIES_P2104.pdf))

## v3-47
- 결론: 지정한 F16 판본을 확인하지 못해 BZT52B3V6의 제너 전압 범위를 답할 수 없습니다.
- 근거: 시험 조건은 5mA, 주변 온도 25°C이나, 확인한 제조사 페이지는 지정 판본의 전압 범위를 확인하는 출처가 아닙니다. 제조사 페이지: https://www.taiwansemi.com/en/products/BZT52B2V4/ ([taiwansemi.com](https://www.taiwansemi.com/en/products/BZT52B2V4/))

## v3-48
- 결론: 요청한 N2406 개정판을 열람하지 못해 그 문서 기준 정격과 D2 적합성은 확인할 수 없습니다. 해당 PDF를 확보한 뒤 검토해야 합니다.
- 근거: TSC 제품 페이지에는 SS26의 반복 피크 역전압 60V, 평균 정류 전류 2A, DO-214AA(SMB) 패키지가 표시되어 있으나 N2406의 확인값은 아닙니다: https://www.taiwansemi.com/en/products/SS26/ ([taiwansemi.com](https://www.taiwansemi.com/en/products/SS26/)) 넷리스트상 D2는 USB→F1→RAW 경로에 있고 기존 풋프린트는 SOD-323이므로 기판 수정이 필요합니다. 제공 조건은 USB 최대 5.25V, D2 연속 최대 100mA, 주변 25°C입니다.

## v3-49
- 결론: 지정한 B2405 개정판을 확인하지 못해 SS14H의 전압 및 평균 전류 정격은 알려드릴 수 없습니다.
- 근거: 검색에서 확인된 TSC 자료는 B2305 개정판이므로 정격 산출에 사용하지 않았습니다. 지정한 PDF를 제공해 주시면 확인할 수 있습니다. ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SS12H%20SERIES_B2305.pdf))

## v3-50
- 결론: 지정된 SMBJH SERIES_A2202.pdf 판본을 확인하지 못해 SMBJ5.0AH의 클램프 전압 최댓값은 답할 수 없습니다. 해당 PDF를 제공해 주시면 확인하겠습니다.
- 근거: 검색에서 확인한 제조사 자료는 A2102 판본이므로 그 수치는 이번 검토에 사용하지 않았습니다: https://services.taiwansemi.com/storage/resources/datasheet/SMBJH%20SERIES_A2102.pdf ([services.taiwansemi.com](https://services.taiwansemi.com/storage/resources/datasheet/SMBJH%20SERIES_A2102.pdf))
