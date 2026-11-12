# 청크별 sha256 목록 (v4h)

- 상태: 현행
- 기준일: 2026-11-13
- 기준 커밋: 이 파일을 추가한 커밋
- 정본 여부: 정본(청크별 본문 해시). 청크 수의 정본은 [data/DATA.md](../../../../data/DATA.md#코퍼스-수치), 게이트 증거는 [docs/GATES.md](../../../../docs/GATES.md) G3
- 관련 문서: [README.md](README.md)(이 폴더 설명), [summary.json](summary.json), [SHA256.txt](SHA256.txt)

[chunk_sha256.tsv](chunk_sha256.tsv)는 현재 코퍼스(청커 `tsc-v4h-2026-11-08`)의 청크마다 본문 해시 한 줄을 담는다. 청크 본문은 담지 않는다. 청크 본문은 저장소에 두지 않고 DB에만 둔다(SPEC 6절, ADR 0005).

## 형식

| 항목 | 값 |
|---|---|
| 열 | `doc`(PDF 파일 이름), `idx`(문서 안 청크 순번), `sha256` |
| 정렬 | `doc` 문자열 오름차순, 같은 문서 안에서 `idx` 숫자 오름차순 |
| 인코딩·줄바꿈 | UTF-8, LF. 맨 위 한 줄은 머리글. `.gitattributes`가 줄바꿈 변환 없이 받게 한다 |
| 파일 크기·sha256 | 4,723,954바이트, `af5ec51e3ec965184ef1bcff9c9f9be443f858c6bcb00ae26bb16786b0e50897` |
| 행 수 | 머리글 제외 51,967 |
| 서로 다른 sha256 | 51,967 |
| 문서 수 | 1,360 |

## 무엇의 해시인가

`sha256`은 `chunks.jsonl` 각 줄의 `text`(JSON에서 읽은 글자 그대로)를 UTF-8로 인코딩한 바이트의 SHA-256이다. 글자를 정규화하지 않고, 앞뒤 공백을 자르지 않고, 줄 끝에 줄바꿈을 붙이지 않는다. 51,967줄 전부 재계산한 값과 일치한다 [실측 2026-11-13].

줄바꿈: `text` 51,967건 중 CR(`\r`)을 포함한 것은 0건이고, 내부 줄바꿈은 LF(22,009건에 있다). 같은 글을 CRLF로 바꿔 해시하면 줄바꿈이 없는 29,958건만 일치한다. 해시는 LF 기준이다.

## 확인

TSV의 행 수와 서로 다른 해시 수([실측] 2026-11-13: `51967 51967`):

```
awk -F'\t' 'NR>1{n++;s[$3]=1}END{print n,length(s)}' evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv
```

[summary.json](summary.json)의 `cards`와 `distinct_text`가 각각 51,967이고, [manifest.jsonl](manifest.jsonl)이 1,360줄이다. TSV의 문서 수 1,360과 같다.

## 다시 만들기

`chunks.jsonl`(저장소 밖)에서 같은 TSV를 만든다. 결과의 sha256이 위 값과 같아야 한다.

```
python3 -I -c "import json,sys;r=sorted((json.loads(l) for l in open(sys.argv[1],encoding='utf-8')),key=lambda x:(x['doc'],x['idx']));open(sys.argv[2],'w',encoding='utf-8',newline='\n').write('doc\tidx\tsha256\n'+''.join(f\"{x['doc']}\t{x['idx']}\t{x['sha256']}\n\" for x in r))" <chunks.jsonl 경로> chunk_sha256.tsv
```

## chunks.jsonl 입수

`chunks.jsonl`은 저장소에 없다. 크기가 약 36MB이고([README.md](README.md)) 청크 본문을 저장소에 두지 않기로 했기 때문이다(SPEC 6절, ADR 0005, [data/DATA.md](../../../../data/DATA.md) "저장소 크기"). 입수 경로는 두 가지다.

- 작업 자료 위치: 팀 로컬 `SojaFit/corpus/tsc/chunks-v4h/chunks.jsonl`(37,932,479바이트, sha256 `bc1454cfee189b3c73fabe82dcfc1f5861b5feddd9f9b65efa3f93c2a10cee17`). 이 sha256은 [SNAPSHOT.md](../../../../data/demo/snapshot/SNAPSHOT.md)가 적은 원본 값과 같다 [실측 2026-11-13].
- 다시 만들기: PDF를 받아(`data/DATA.md` "기준") Docling으로 파싱한 뒤 `backend/rag/pipeline/chunk.py`의 실행 명령으로 청킹한다. 이 재실행은 하지 않았다.

## 한계

- 운영 DB의 `document_chunks`에서 `sha256(본문)`이나 행 수를 다시 조회한 기록은 저장소에 없다. 이 목록은 청킹 산출물의 해시이며 DB 내용의 증거가 아니다.
- `chunks.jsonl` 본문 없이는 이 목록으로 해시를 다시 계산할 수 없다. TSV는 `chunks.jsonl`과 대조하는 용도다.
