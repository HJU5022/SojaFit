"""키 없는 compose 데모가 로컬 DB에 넣는 코퍼스 스냅샷(data/demo/snapshot/)을 전체 v4h 청크에서 뽑는 오프라인 도구.

- 역할: 오프라인 CLI(`python -m backend.rag.pipeline.demo_snapshot`). 서버가 import하지 않는다.
  원본 폴더의 manifest.jsonl·chunks.jsonl에서 아래 규칙에 걸린 문서의 줄을 바이트 그대로, 원래 순서로 골라
  <출력 폴더>/manifest.jsonl·chunks.jsonl로 쓰고, 줄 수·크기·sha256과 문서마다 걸린 규칙 번호·청크 수를 출력한다.
  규칙(문서 품번 목록 `parts` 기준, 여러 규칙에 걸리면 앞 번호를 이유로 적는다):
    1. 품번 1N4148이 있는 문서
    2. 1N4148로 시작하는 다른 품번(1N4148W·1N4148WS 등, 대체 후보)이 있는 문서
    3. 1N4001G·1N4007G로 시작하는 품번이 있는 문서
    4. 1번 문서와 분류 이름(ingest.py와 같은 family())이 같은 문서. 60건이 넘으면 파일 이름 순 앞 60건
  문서의 청크는 자르지 않고 모두 넣는다. 임베딩은 넣지 않는다(키가 없으면 질문도 임베딩하지 못해 BM25만 쓴다).
- 하지 않는 일: DB 적재(compose의 corpus-load가 ingest.py --chunks-only로 넣는다), 원본 수정.
- 출처: data/demo/snapshot/SNAPSHOT.md, SPEC.md 7절

실행: python -m backend.rag.pipeline.demo_snapshot <chunks-v4h 폴더> <출력 폴더>
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from backend.rag.pipeline.chunk import doc_key
from backend.rag.pipeline.specs import family

EXACT = '1N4148'  # 데모 회로 D3의 정확한 품번
PREFIXES = ('1N4001G', '1N4007G')  # 데모 회로 D1(1N4001)은 코퍼스에 없고 같은 계열의 G 품번만 있다
FAMILY_MAX = 60  # 4번 규칙으로 넣는 같은 분류 문서 수 상한


def select(src):
    """원본 폴더 → (스냅샷 manifest 바이트, 스냅샷 청크 바이트, {파일 이름: 규칙 번호})."""
    src = Path(src)
    # [왜] 원본 줄 바이트를 그대로 옮겨야 ingest.py가 원본과 같은 청크·sha256을 넣는다
    rows = [(json.loads(line), line) for line in (src / 'chunks.jsonl').read_bytes().splitlines(keepends=True)]
    parts, category = {}, {}
    for c, _ in rows:
        parts.setdefault(c['doc'], set()).update(c['parts'])
        category[c['doc']] = family(c['category'])  # 한 문서의 청크는 모두 같은 category를 갖는다(ingest.py 주석)
    rules = {
        1: {d for d, p in parts.items() if EXACT in p},
        2: {d for d, p in parts.items() if any(x.startswith(EXACT) and x != EXACT for x in p)},
        3: {d for d, p in parts.items() if any(x.startswith(PREFIXES) for x in p)},
    }
    families = {category[d] for d in rules[1]}
    rules[4] = set(sorted(d for d in category if category[d] in families)[:FAMILY_MAX])
    reason = {}
    for n in (4, 3, 2, 1):  # 뒤 번호부터 채워 앞 번호가 덮어쓰게 한다
        reason.update(dict.fromkeys(rules[n], n))
    keys = {doc_key(d) for d in reason}
    manifest = [line for line in (src / 'manifest.jsonl').read_bytes().splitlines(keepends=True)
                if json.loads(line)['doc_id'] in keys]
    return b''.join(manifest), b''.join(line for c, line in rows if c['doc'] in reason), reason


def main(src, out):
    """select 결과를 out 폴더에 쓰고 파일별 줄 수·크기·sha256, 문서별 규칙 번호·청크 수를 출력한다."""
    out = Path(out)
    if out.resolve() == Path(src).resolve():  # [주의] 같은 폴더면 원본 manifest·chunks를 덮어써 잃는다
        sys.exit('출력 폴더가 원본 폴더와 같다')
    manifest, chunks, reason = select(src)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (('manifest.jsonl', manifest), ('chunks.jsonl', chunks)):
        (out / name).write_bytes(data)
        print(name, len(data.splitlines()), 'lines', len(data), 'bytes', hashlib.sha256(data).hexdigest())
    count = Counter(json.loads(line)['doc'] for line in chunks.splitlines())
    for d in sorted(reason):
        print(reason[d], d, count[d])


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
