"""벡터 캐시(본문 해시 → 벡터)가 끊겼다 다시 열어도 같은 벡터를 돌려주는지 본다(rag-pipeline EC-04·05). DB 없이 돈다."""
import numpy as np

from backend.rag.ingest import DIM, VectorCache


def test_cache_survives_reopen(tmp_path):
    a, b = np.full(DIM, 0.5, np.float32), np.arange(DIM, dtype=np.float32)
    VectorCache(tmp_path).add([('sha-a', a)])
    VectorCache(tmp_path).add([('sha-b', b)])  # 다시 열어 이어 붙인다
    cache = VectorCache(tmp_path)
    assert set(cache.index) == {'sha-a', 'sha-b'}
    assert np.array_equal(cache.get('sha-a'), a) and np.array_equal(cache.get('sha-b'), b)
