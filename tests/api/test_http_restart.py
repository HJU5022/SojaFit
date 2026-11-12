"""명시적으로 실행할 때만 Docker를 쓰는 HTTP 재시작·재개 검증."""
import os, subprocess, sys, time, uuid
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
TOKEN = uuid.uuid4().hex[:12]
DB_PORT = 54000 + int(TOKEN[:4], 16) % 1000
HTTP_PORT = 18000 + int(TOKEN[4:8], 16) % 1000
DB = f"postgresql://app:app@127.0.0.1:{DB_PORT}/app"
BASE = f"http://127.0.0.1:{HTTP_PORT}"
CONTAINER = f"codex-osc-http-restart-{TOKEN}"


def run(*args, timeout=10, env=None):
    return subprocess.run(args, cwd=ROOT, check=True, timeout=timeout, capture_output=True, text=True, env=env)


def _server_env():
    env = os.environ.copy()
    env.update({"DATABASE_URL": DB, "AUTH_SECRET": "restart-test-secret-32-bytes-minimum", "AUTH_ORIGIN": BASE,
                "DEMO_MODE": "1", "DEMO_REPLAY": "0", "THREADS_ENABLED": "1", "GOOGLE_AUTH_ENABLED": "0",
                "PYTHONPATH": ".", "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "",
                "SOJAFIT_HTTP_RESTART_CHILD": "1",
                # 재시작 직후 재개가 분석 호출 최소 간격(기본 2초)에 걸려 429가 되지 않게 한다. 간격 제한 자체는 test_errors.py · test_threads.py가 본다
                "ANALYSIS_MIN_INTERVAL_SECONDS": "0"})
    return env


def _server():
    return subprocess.Popen([sys.executable, "-m", "uvicorn", "tests.api.test_http_restart:app", "--host", "127.0.0.1",
                             "--port", str(HTTP_PORT), "--log-level", "warning"], cwd=ROOT, env=_server_env(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)


def _wait(client, proc):
    for _ in range(30):
        if proc.poll() is not None: raise RuntimeError(f"server exited early: {proc.returncode}")
        try:
            if client.get("/health", timeout=2).status_code == 200: return
        except httpx.HTTPError: pass
        time.sleep(.3)
    raise RuntimeError("server did not become ready")


def main():
    proc = None; created = False
    try:
        run("docker", "run", "-d", "--name", CONTAINER, "-e", "POSTGRES_USER=app", "-e", "POSTGRES_PASSWORD=app",
            "-e", "POSTGRES_DB=app", "-p", f"127.0.0.1:{DB_PORT}:5432", "pgvector/pgvector:pg16"); created = True
        for _ in range(30):
            if subprocess.run(["docker", "exec", CONTAINER, "pg_isready", "-U", "app", "-d", "app"], capture_output=True).returncode == 0: break
            time.sleep(1)
        env = os.environ.copy(); env["DATABASE_URL"] = DB
        run(sys.executable, "-c", "import psycopg,os; from tests.db_schema import apply_service_schema; c=psycopg.connect(os.environ['DATABASE_URL']); c.execute('CREATE EXTENSION IF NOT EXISTS vector'); apply_service_schema(c,agent=True); c.commit()", env=env)
        run(sys.executable, "-m", "backend.conversations.memory_service", "--setup", env=env)
        proc = _server()
        with httpx.Client(base_url=BASE, headers={"Origin": BASE}, timeout=10) as a, httpx.Client(base_url=BASE, headers={"Origin": BASE}, timeout=10) as b:
            _wait(a, proc)
            assert a.post("/api/auth/demo-login", json={"account":"a"}).status_code == 200 and a.get("/api/auth/me").json()["user_id"] == 1
            project = a.post("/api/projects", json={"demo_id":"breadboard_supply", "name":"restart-repro"}).json()
            thread = a.post(f"/api/projects/{project['id']}/threads").json()["id"]
            sse = a.post(f"/api/threads/{thread}/runs", json={"question":"test", "target_ref":"D1"}).text
            run_id = sse.split('run_id": "', 1)[1].split('"', 1)[0]; assert "event: requires_input" in sse
            assert b.post("/api/auth/demo-login", json={"account":"b"}).status_code == 200 and b.get("/api/auth/me").json()["user_id"] == 2
            assert b.get(f"/api/runs/{run_id}").status_code == 404 and b.post(f"/api/runs/{run_id}/resume", json={"answers":{"v_in":"5V"}}).status_code == 404
            _stop(proc); proc = _server(); _wait(a, proc)
            assert a.get(f"/api/runs/{run_id}").json()["result"]["status"] == "requires_input"
            assert "event: completed" in a.post(f"/api/runs/{run_id}/resume", json={"answers":{"v_in":"5V"}}).text
            print(f"PASS A=1 B=2 B_GET=404 B_RESUME=404 RESTART_RESUME=completed RUN={run_id}")
    finally:
        _stop(proc)
        if created: subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True, timeout=10)


def test_http_restart_is_explicit_only():
    import pytest
    if os.getenv("SOJAFIT_HTTP_RESTART_RUN") != "1": pytest.skip("explicit Docker repro only")
    main()


# Parent pytest import never patches the product. Only the child server sets this flag.
if os.getenv("SOJAFIT_HTTP_RESTART_CHILD") == "1":
    from backend.conversations import memory_service
    from backend.graph.state import AgentState
    from backend.services import langfuse_prompts, service_trace
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt
    service_trace.callbacks = lambda *a, **k: ([], {})
    langfuse_prompts.publish_analysis_trace = lambda *a, **k: "disabled"
    def _graph(saver, store):
        def pause(state):
            value = interrupt({"missing":["v_in"], "role_choices":[], "question":"v_in?"})
            return {"answer": f"synthetic resumed: {value}", "path":["끝"]}
        g = StateGraph(AgentState); g.add_node("pause", pause); g.add_edge(START, "pause"); g.add_edge("pause", END)
        return g.compile(checkpointer=saver, store=store)
    _Real = memory_service.Conversations
    memory_service.Conversations = lambda dsn: _Real(dsn, factory=_graph)
    from backend.main import app


if __name__ == "__main__": main()
