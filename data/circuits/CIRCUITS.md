# circuits

## 역할
- 이 폴더: 평가와 시연에 쓰는 공개 KiCad 회로를 둡니다.
- 넣는 것: MIT·CC BY-SA 등 라이선스가 확인된 공개 회로 파일과, 회로마다 원 저장소·커밋·라이선스를 적은 표.
- 넣지 않는 것: 단위 테스트용 가공 회로(`tests/fixtures/`), 라이선스를 확인하지 못한 회로.
- 담당: 평가·문서

## 파일
- `CIRCUITS.md` — 이 폴더 설명
- `collected/` — 평가 문항 초안(`evals/draft_30.jsonl`)이 쓰는 회로 5종. 회로마다 넷리스트, 연결 목록(`connections.json`), 원본의 LICENSE·README를 둔다

## 회로 출처

| 회로 | 넷리스트 | 원 저장소 | 커밋 | 라이선스 |
|---|---|---|---|---|
| SparkFun Breadboard Power Supply 5V/3.3V | `collected/samples/breadboard_supply/converted/circuit.net` | https://github.com/sparkfun/Breadboard_Power_Supply_5V_3.3V | `6e4b69f6b8ca4871a802177e6a615fdfc8e82f1b` | CC BY-SA 4.0 |
| Adafruit MOSFET Driver STEMMA | `collected/samples/mosfet_driver/converted/circuit.net` | https://github.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB | `ea11049753a79330cc2651df233909c0191a5af4` | CC BY-SA 3.0 |
| ATtiny85 dev board | `collected/samples/attiny85_dev/converted/circuit.net` | https://github.com/tomasr8/attiny85-dev-board | `488b99063b6bdbafa0f367ecc25901b55c4c7144` | MIT |
| Franzininho DIY | `collected/received-20261030/c09/received/c09-franzininho-diy.net` | https://github.com/Franzininho/franzininho-diy-board | `abdb4b48d867190d6b9794280be8b85b81aa1772` | CC BY-SA 4.0(하드웨어) |
| SparkFun Pro Micro v13 | `collected/samples/pro_micro/converted/circuit.net` | https://github.com/sparkfun/Pro_Micro | `df836f3bf2955c4f1199a852f618d2ac80866d47` | CC BY-SA 4.0 |

- Breadboard Supply·MOSFET Driver·Pro Micro는 Eagle 원본을 KiCad로 변환해 넷리스트를 뽑았고, ATtiny85 dev는 KiCad 원본에서 내보냈고, Franzininho는 원 저장소의 넷리스트를 그대로 썼다.
- 원본 회로도·PCB 파일은 넣지 않는다. 필요하면 위 저장소의 해당 커밋에서 받는다.
- CC BY-SA 회로에서 만든 넷리스트는 원본과 같은 라이선스를 따른다.
