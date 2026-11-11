# circuits

## 역할
- 이 폴더: 평가와 시연에 쓰는 공개 KiCad 회로와 그 라이선스를 둡니다.
- 넣는 것: MIT·CC BY-SA 등 라이선스가 확인된 공개 회로의 넷리스트·연결 목록(`connections.json`)·원본의 LICENSE와 README, 회로마다 원 저장소·커밋·라이선스를 적은 표(아래).
- 넣지 않는 것: 단위 테스트용 가공 회로(`tests/` 아래), 라이선스를 확인하지 못한 회로, PCB 파일. 검증한 회로도 PNG는 `frontend/public/circuit-schematics/`에 둡니다.
- 담당: 평가·문서

## 파일
- `catalog.json` — 데모 15종의 ID·표시 이름·정규화 연결 JSON 경로 정본.
- `visuals.json` — 검증된 원본 회로도 15종의 배포 경로·원본 URL·저장소 맥락 commit·라이선스 근거·저작자·원본 및 배포 SHA-256 정본.
- `collected/` — 동결 평가셋 v1(`evals/dataset_v1.jsonl`)이 쓰는 회로 5종과 v3(`evals/dataset_v3.jsonl`)가 더 쓰는 받은 회로 10종. 설명 파일은 두지 않고 이 문서가 설명합니다.
  - `received-20261030/c09/` — 받은 회로 1종(Franzininho DIY): `received/`(받은 넷리스트), `connections.json`, `original/`(LICENSE·README)
  - `received-20261030/{c01,c02,c03,c04,c05,c07,c08,c10,c11,c12}/` — v3가 쓰는 받은 회로 10종(11-10 동결 때 lab에서 옮김): 같은 모양(`received/` · `connections.json` · `original/`)
  - `samples/{attiny85_dev,breadboard_supply,mosfet_driver,pro_micro}/` — 공개 표본 4종: `converted/`(`circuit.net`, `connections.json`), `original/`(LICENSE·README)

## 회로 출처

| 회로 | 넷리스트 | 원 저장소 | 커밋 | 라이선스 |
|---|---|---|---|---|
| SparkFun Breadboard Power Supply 5V/3.3V | `collected/samples/breadboard_supply/converted/circuit.net` | https://github.com/sparkfun/Breadboard_Power_Supply_5V_3.3V | `6e4b69f6b8ca4871a802177e6a615fdfc8e82f1b` | CC BY-SA 4.0 |
| Adafruit MOSFET Driver STEMMA | `collected/samples/mosfet_driver/converted/circuit.net` | https://github.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB | `ea11049753a79330cc2651df233909c0191a5af4` | CC BY-SA 3.0 |
| ATtiny85 dev board | `collected/samples/attiny85_dev/converted/circuit.net` | https://github.com/tomasr8/attiny85-dev-board | `488b99063b6bdbafa0f367ecc25901b55c4c7144` | MIT |
| Franzininho DIY | `collected/received-20261030/c09/received/c09-franzininho-diy.net` | https://github.com/Franzininho/franzininho-diy-board | `abdb4b48d867190d6b9794280be8b85b81aa1772` | CC BY-SA 4.0(하드웨어) |
| SparkFun Pro Micro v13 | `collected/samples/pro_micro/converted/circuit.net` | https://github.com/sparkfun/Pro_Micro | `df836f3bf2955c4f1199a852f618d2ac80866d47` | CC BY-SA 4.0 |
| ATtiny85 Time Switch | `collected/received-20261030/c01/received/c01-attiny85-time-switch.net` | https://github.com/UCSIG/attiny85_time_switch | `3566a94ffc17471e3f0a592bacc63480a2898641` | MIT |
| FC ROM Vomitter | `collected/received-20261030/c02/received/c02-fc-rom-vomitter.net` | https://github.com/Keitark/fc-rom-vomitter | `f64502c301ca5e11add76efdf7dd52b343f8baaf` | MIT |
| ATtiny2313A Thermostat | `collected/received-20261030/c03/received/c03-attiny2313a-thermostat.net` | https://github.com/sergeyyarkov/attiny2313a_thermostat | `4e956f152368fc8a6f68e9e2e0d273ea25249840` | MIT |
| tiny85 Fan Control | `collected/received-20261030/c04/received/c04-tiny85fancontrol.net` | https://github.com/Colahall/tiny85fancontrol | `66366bd10b66e4bc3e944902f9e6c93a44ddeac4` | MIT |
| UG56 PWM Controller | `collected/received-20261030/c05/received/c05-ug56-pwm-controller.net` | https://github.com/universalgeek56/UG56-attiny13a-pwm-controller | `91f19385e76a92e9b58c681f22e9891ba1c8aebe` | MIT |
| Car Radio ACC Delay | `collected/received-20261030/c07/received/c07-car-radio-acc-delay.net` | https://github.com/alexwarg/car-radio-acc-delay | `5d5048f196ea539ae2464c6bc766384444ea8696` | MIT |
| OverEngineered PSU | `collected/received-20261030/c08/received/c08-overengineered-psu.net` | https://github.com/MAATHES-THILAK-K/OverEngineered-PSU | `5b8b7757e9742b4f97ddf61c434c7cf2e48b1867` | MIT |
| tinydimmer | `collected/received-20261030/c10/received/c10-tinydimmer.net` | https://github.com/virtual-machinist/tinydimmer | `52ee6077344b044bf046e6c616cefe3675091b46` | CC BY-SA 4.0 |
| HRem | `collected/received-20261030/c11/received/c11-hrem.net` | https://github.com/bazhenov/hrem | `7d6d56d1a7d75231c0d7109d90839474f59f3f1d` | MIT |
| ZR7 Taillight | `collected/received-20261030/c12/received/c12-zr7-taillight.net` | https://github.com/slabua/zr7-taillight | `777c5d5f034361a6d143fedeb3de9a8bb81ca532` | MIT |

- Breadboard Supply·MOSFET Driver·Pro Micro는 Eagle 원본을 KiCad로 변환해 넷리스트를 뽑았고, ATtiny85 dev는 KiCad 원본에서 내보냈고, Franzininho는 원 저장소의 넷리스트를 그대로 썼다.
- 받은 회로 10종(c01 ~ c05 · c07 · c08 · c10 ~ c12)은 lab `data/circuits`에 있던 받은 넷리스트 · `connections.json` · 원본 LICENSE · README를 그대로 옮겼다(11-10, v3 동결).
- PCB 파일은 넣지 않는다. 필요하면 위 저장소의 해당 커밋에서 받는다.
- CC BY-SA 회로에서 만든 넷리스트는 원본과 같은 라이선스를 따른다.

## 배포 회로도

`catalog.json`과 `visuals.json`은 수집된 공개 회로 15종을 모두 등록한다. 공식 PNG·PDF가 있으면 그대로 사용하고, KiCad 원본만 있는 회로는 고정 커밋의 원본을 KiCad 9.0.5로 PDF export한 뒤 첫 페이지를 PNG로 변환했다. 넷리스트 업로드에서 원본 회로도를 추정하지 않는다.

`original_url`은 실제 받은 원본, `source_sha256`은 그 원본 바이트, `sha256`은 배포 PNG 바이트를 식별한다. PNG 원본 2종은 그대로 복사하고 PDF 원본 4종은 `pdftoppm -f 1 -singlefile -png -r 160`으로 첫 페이지만 변환했다. 자르기·주석·재배선은 없다. SHA-256 둘 다 API에 노출하지 않는다. 서버는 실행 중 외부 다운로드 없이 배포 PNG 경로와 해시를 검증한다.

`license_evidence_url`은 자산별 고정 commit의 라이선스 근거다. CDN 원본의 `source_commit`은 관련 저장소 맥락이며 CDN 바이트가 그 commit에서 생성되었다는 증거는 아니다. 정확한 URL과 두 해시는 `visuals.json`에 기록했다.
