"""로컬 실제 API의 DB·Origin 격리. Compose 해석만 하며 서버/DB/공급자를 호출하지 않는다."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

import pytest


@pytest.mark.skipif(shutil.which('docker') is None, reason='Docker Compose CLI required (daemon not used)')
def test_local_api_cannot_inherit_production_database_or_auth(tmp_path):
    root = Path(__file__).resolve().parents[2]
    env_file = tmp_path / 'test.env'
    local_password = 'example-local:#/?%@password'
    env_file.write_text(f'LOCAL_DB_PASSWORD={local_password}\nLOCAL_AUTH_SECRET=example-local-only-secret\n')
    env = dict(os.environ, LOCAL_DB_PASSWORD=local_password, LOCAL_AUTH_SECRET='example-local-only-secret',
               DATABASE_URL='postgresql://example@production.invalid/example', AUTH_ORIGIN='https://production.invalid')
    result = subprocess.run(['docker', 'compose', '--env-file', str(env_file), '-f', str(root / 'docker-compose.local.yml'),
                             'config', '--no-env-resolution', '--format', 'json'],
                            cwd=root, env=env, capture_output=True, text=True, check=True, timeout=30)
    config = json.loads(result.stdout)
    api = config['services']['api']
    for name in ('api', 'thread-setup'):
        assert config['services'][name]['build']['args']['VITE_LOCAL_ATTACHMENT_UI'] == '1'
    for name in ('api', 'thread-setup'):
        db_env = config['services'][name]['environment']
        assert urlsplit(db_env['DATABASE_URL']).hostname == 'db'
        assert urlsplit(db_env['DATABASE_URL']).password is None
        assert db_env['PGPASSWORD'] == local_password
    assert api['environment']['AUTH_ORIGIN'] == 'http://localhost:8010'
    assert {key: api['environment'][key] for key in ('DEMO_MODE', 'DEMO_REPLAY', 'THREADS_ENABLED')} == {
        'DEMO_MODE': '0', 'DEMO_REPLAY': '0', 'THREADS_ENABLED': '1'}
    assert api['environment']['AUTH_SECRET'] == 'example-local-only-secret'
    assert api['environment']['PYTHON_DOTENV_DISABLED'] == '1'
    assert api['environment']['KICAD_RENDERER_URL'] == 'http://renderer:8000'
    assert config['services']['renderer']['build']['target'] == 'renderer'
    assert api['depends_on']['renderer']['condition'] == 'service_started'
    assert not config['services']['renderer'].get('ports')
    assert api['ports'][0]['host_ip'] == '127.0.0.1' and str(api['ports'][0]['published']) == '8010'
    assert not config['services']['db'].get('ports')
    assert config['name'] == 'sojafit-sth-local'
    assert config['volumes']['local-pgdata']['name'] == 'sojafit-sth-local_local-pgdata'
    assert [Path(item['path']).name for item in api['env_file']] == ['.env.local']
