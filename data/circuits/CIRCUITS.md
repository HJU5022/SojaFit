# circuits

## 역할
- 이 폴더: 평가와 시연에 쓰는 공개 KiCad 회로와 그 라이선스를 둡니다.
- 넣는 것: MIT·CC BY-SA 등 라이선스가 확인된 공개 회로의 넷리스트·연결 목록(`connections.json`)·원본의 LICENSE와 README, 회로마다 원 저장소·커밋·라이선스를 적은 표(아래).
- 넣지 않는 것: 단위 테스트용 가공 회로(`tests/` 아래), 라이선스를 확인하지 못한 회로, 원본 회로도·PCB 파일(필요하면 아래 표의 저장소·커밋에서 받음).
- 담당: 평가·문서

## 파일
- `collected/` — 동결 평가셋 v1(`evals/dataset_v1.jsonl`)이 쓰는 회로 5종. 설명 파일은 두지 않고 이 문서가 설명합니다.
  - `received-20261030/c09/` — 받은 회로 1종(Franzininho DIY): `received/`(받은 넷리스트), `connections.json`, `original/`(LICENSE·README)
  - `samples/{attiny85_dev,breadboard_supply,mosfet_driver,pro_micro}/` — 공개 표본 4종: `converted/`(`circuit.net`, `connections.json`), `original/`(LICENSE·README)

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
