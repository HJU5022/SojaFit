"""캐시 전용 재현에서 손상 입력·누락 질의·외부 DB를 거부한다."""
import hashlib
import json

import numpy as np
import pytest

from evals import reproduce_halfvec as runner


def make_cache(folder, texts):
    folder.mkdir(parents=True)
    keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
    (folder / 'vectors.sha.txt').write_text('\n'.join(keys) + '\n')
    np.ones((len(keys), 1536), dtype=np.float32).tofile(folder / 'vectors.f32')


def test_incomplete_cache_is_rejected_without_repair(tmp_path):
    make_cache(tmp_path / 'cache', ['q'])
    p = tmp_path / 'cache/vectors.f32'
    p.write_bytes(p.read_bytes()[:-4])
    before = p.read_bytes()
    with pytest.raises(ValueError, match='cache'):
        runner.read_cache(tmp_path / 'cache')
    assert p.read_bytes() == before


def test_input_hash_mismatch_fails(tmp_path):
    (tmp_path / 'chunks.jsonl').write_text('changed')
    record = {'files': {'chunks.jsonl': '0' * 64}}
    with pytest.raises(ValueError, match='hash'):
        runner.validate_inputs(tmp_path, record)


def test_missing_question_vector_fails_before_retrieval(tmp_path):
    dataset = tmp_path / 'dataset.jsonl'
    dataset.write_text(json.dumps({'kind': 'relevant', 'input': 'q', 'gold_chunks': ['a.pdf, 1쪽']}) + '\n')
    with pytest.raises(ValueError, match='question cache'):
        runner.questions(dataset, {})


def test_nonlocal_database_is_rejected(tmp_path):
    env = tmp_path / 'db.env'
    env.write_text('DATABASE_URL=postgresql://test:fake@remote.invalid/db\n')
    with pytest.raises(ValueError, match='localhost'):
        runner.local_dsn(env)


def test_cached_question_uses_original_float32(tmp_path):
    make_cache(tmp_path / 'cache', ['q'])
    cache = runner.read_cache(tmp_path / 'cache')
    result = runner.cached_embed(cache)(['q'])
    assert result[1] == 0
    assert result[2:] == ('openrouter', 'openai/text-embedding-3-small')
    np.testing.assert_array_equal(result[0][0], np.ones(1536, dtype=np.float32))
