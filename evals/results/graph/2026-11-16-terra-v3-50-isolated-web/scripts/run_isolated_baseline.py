"""50 independent OpenRouter requests; no project code, tools, or chat history.

Prepare: py -3 outputs/run_isolated_baseline.py
Run:     py -3 outputs/run_isolated_baseline.py --run
Check:   py -3 outputs/run_isolated_baseline.py --self-check
An attempted request is never automatically retried, even after a timeout.
"""
import concurrent.futures
import hashlib
import json
import platform
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(r"E:\teamproject3\proj3-b")
OUT = Path(__file__).resolve().parent / "terra_web_baseline"
MODEL = "openai/gpt-6.1-terra"
API = "https://openrouter.ai/api/v1/chat/completions"
KST = timezone(timedelta(hours=9))
RULES = """아래 질문 하나에 답해 주세요.

규칙:
- 초기 입력은 아래 질문 글과 함께 제공된 circuit.net 넷리스트 내용뿐이다.
- 데이터시트·제조사 자료가 필요하면 웹 검색으로 찾는다. 찾지 못하면 추측이라고 밝히거나 모른다고 답한다. 실제 열람하지 않은 URL을 확인한 출처처럼 표현하지 않는다.
- 관련 없는 질문이면 거절·범위 밖이라고 답해도 된다.
- 출력은 정확히 두 줄이다. 각 항목 안에서는 줄바꿈하지 않는다.
- 결론: (한두 문장)
- 근거: (수치·조건·출처 URL, 확인하지 못한 정보는 그 한계 명시)
"""


def now():
    return datetime.now(KST).isoformat(timespec="seconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_questions(text):
    questions = []
    for m in re.finditer(r"^## (v3-\d+)[^\n]*\n(.*?)(?=^---$|\Z)", text, re.M | re.S):
        body = m[2].strip()
        net = re.search(r"^넷리스트: (\S+)$", body, re.M)
        if not net:
            raise ValueError(f"Missing netlist: {m[1]}")
        questions.append({"id": m[1], "body": body, "netlist": net[1]})
    if [q["id"] for q in questions] != [f"v3-{i:02d}" for i in range(1, 51)]:
        raise ValueError("Expected exactly v3-01 through v3-50 in order")
    return questions


def make_payload(q, netlist):
    body = q["body"].replace("넷리스트: " + q["netlist"], "넷리스트: ./circuit.net (아래에 전체 내용 제공)", 1)
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": RULES},
            {"role": "user", "content": body + "\n\n--- circuit.net 전체 내용 ---\n" + netlist},
        ],
        "max_tokens": 8192,
        "reasoning": {"effort": "medium", "exclude": True},
        "provider": {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny"},
        "plugins": [{"id": "web", "engine": "native"}],
        "stream": False,
    }


def valid_format(answer):
    return re.fullmatch(r"- 결론: [^\n]+\n- 근거: [^\n]+", answer.strip()) is not None


def render_answer(answer):
    # Only normalize blank lines and missing list markers; never rewrite content.
    lines = [line.strip() for line in answer.strip().splitlines() if line.strip()]
    if len(lines) == 2:
        for i, label in enumerate(("결론:", "근거:")):
            if lines[i].startswith(label):
                lines[i] = "- " + lines[i]
        if valid_format("\n".join(lines)):
            return "\n".join(lines)
    return answer.strip()


def read_key():
    # Read only this key; never export the .env or include credentials in logs.
    for line in (REPO / ".env").read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*(.*?)\s*$", line)
        if m:
            value = m[1]
            if value.startswith(('"', "'")):
                value = value[1:value.index(value[0], 1)]
            else:
                value = value.split(" #", 1)[0].strip()
            if not value or any(c.isspace() for c in value):
                raise ValueError("Invalid OPENROUTER_API_KEY")
            return value
    raise ValueError("OPENROUTER_API_KEY not found")


def prepare():
    OUT.mkdir(exist_ok=True)
    raw = OUT / "raw"
    raw.mkdir(exist_ok=True)
    guide = (REPO / "evals/guides/v3_50_codex_paste.md").read_bytes()
    questions = parse_questions(guide.decode("utf-8-sig").replace("\r\n", "\n"))
    inputs = []
    total = 0
    for q in questions:
        net = (REPO / q["netlist"]).resolve()
        if not net.is_relative_to(REPO.resolve()):
            raise ValueError("Netlist outside repository")
        data = net.read_bytes()
        payload = make_payload(q, data.decode("utf-8-sig"))
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_path = raw / (q["id"] + ".request.json")
        if request_path.exists():
            if json.loads(request_path.read_text(encoding="utf-8")) != payload:
                raise ValueError("Input changed; refusing to mix runs: " + q["id"])
        else:
            save(request_path, payload)
        total += len(encoded)
        inputs.append({**q, "netlist_sha256": digest(data), "request_sha256": digest(encoded), "request_bytes": len(encoded)})
    save(OUT / "inputs.json", {"guide_sha256": digest(guide), "questions": inputs})
    return questions, total


def call_one(q, key):
    stem = OUT / "raw" / q["id"]
    status_path = Path(str(stem) + ".status.json")
    if status_path.exists():
        return json.loads(status_path.read_text(encoding="utf-8"))
    payload = json.loads(Path(str(stem) + ".request.json").read_text(encoding="utf-8"))
    status = {"id": q["id"], "state": "attempted", "started_at": now()}
    # Exclusive marker prevents concurrent or accidental duplicate paid calls.
    with status_path.open("x", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False)
    started = time.monotonic()
    try:
        request = urllib.request.Request(API, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=600) as response:
            body = response.read().decode("utf-8")
        # Preserve API JSON, including usage, provider, generation ID and finish reason.
        Path(str(stem) + ".response.json").write_text(body.replace(key, "[REDACTED]"), encoding="utf-8")
        data = json.loads(body)
        if "error" in data:
            raise ValueError(json.dumps(data["error"], ensure_ascii=False))
        choice = data["choices"][0]
        answer = choice["message"].get("content")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Empty final answer")
        Path(str(stem) + ".answer.md").write_text(answer, encoding="utf-8")
        status.update(state="answered", model=data.get("model"), provider=data.get("provider"), generation_id=data.get("id"), finish_reason=choice.get("finish_reason"), format_ok=valid_format(answer), rendered_format_ok=valid_format(render_answer(answer)), formatting_only_adjusted=render_answer(answer) != answer.strip(), usage=data.get("usage", {}), model_matches=data.get("model") == MODEL, web_annotations=len(choice["message"].get("annotations", [])))
    except urllib.error.HTTPError as e:
        status.update(state="error", http_status=e.code, error=e.read().decode("utf-8", errors="replace").replace(key, "[REDACTED]"))
    except Exception as e:
        status.update(state="error", error=(type(e).__name__ + ": " + str(e)).replace(key, "[REDACTED]"))
    status.update(ended_at=now(), seconds=round(time.monotonic() - started, 2))
    save(status_path, status)
    print(json.dumps({k: status.get(k) for k in ("id", "state", "seconds", "format_ok", "model", "usage", "error")}, ensure_ascii=False), flush=True)
    return status


def summarize(questions, started):
    statuses = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / "raw").glob("*.status.json"))]
    answered = [s for s in statuses if s["state"] == "answered"]
    summary = {"requested_model": MODEL, "interface": "OpenRouter Chat Completions API (not Codex CLI)", "os": platform.platform(), "python": platform.python_version(), "started_at": started, "ended_at": now(), "web_search": False, "repository_context": False, "memory": False, "prior_conversations": False, "cross_question_history": False, "provided_inputs": "generic output rules + one unchanged question body (netlist path replaced) + its full netlist", "reasoning_effort": "medium", "max_tokens_per_request": 8192, "jobs": 3, "automatic_retries": 0, "questions": len(questions), "attempted": len(statuses), "answered": len(answered), "format_ok": sum(s.get("format_ok", False) for s in answered), "complete_untruncated": sum(s.get("finish_reason") == "stop" for s in answered), "returned_models": sorted({s.get("model", "") for s in answered}), "cost_usd_reported": sum(s.get("usage", {}).get("cost", 0) or 0 for s in statuses), "cost_missing": sum(s.get("usage", {}).get("cost") is None for s in answered), "prompt_tokens": sum(s.get("usage", {}).get("prompt_tokens", 0) for s in statuses), "completion_tokens": sum(s.get("usage", {}).get("completion_tokens", 0) for s in statuses), "runs": statuses}
    summary.update(web_search=True, web_search_engine="native", provided_inputs="generic output rules + one question body (netlist path replaced) + full netlist; model may retrieve public web sources", rendered_format_ok=sum(s.get("rendered_format_ok", False) for s in answered), formatting_only_adjusted=[s["id"] for s in answered if s.get("formatting_only_adjusted")], questions_with_citation_annotations=sum(s.get("web_annotations", 0) > 0 for s in answered))
    summary.update(web_search_requests=sum(s.get("usage", {}).get("server_tool_use_details", {}).get("web_search_requests", 0) for s in answered), questions_with_reported_search=sum(s.get("usage", {}).get("server_tool_use_details", {}).get("web_search_requests", 0) > 0 for s in answered))
    summary["ended_at"] = max((s.get("ended_at", s["started_at"]) for s in statuses), default=now())
    save(OUT / "manifest.json", summary)
    blocks = []
    for q in questions:
        answer = OUT / "raw" / (q["id"] + ".answer.md")
        if answer.exists():
            blocks.append("## " + q["id"] + "\n" + render_answer(answer.read_text(encoding="utf-8")))
    (OUT / "answers.md").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    (OUT / "answers.txt").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    readme = f"""# GPT-6.1 Terra 격리 답변 기록

- 모델: `{MODEL}` / OpenRouter Chat Completions API (Codex CLI 사용 안 함)
- 격리: 저장소 문서·코드·위키·AGENTS.md·메모리·현재 대화 전달 없음. 문항 간 대화 이력 없음.
- 입력: 문항 본문 + 해당 넷리스트 전문 + 공통 출력 규칙만. 문항 머리의 관련성/채점 태그 제외. 넷리스트 경로만 `./circuit.net`으로 치환.
- 웹 검색: **켬**, OpenRouter `web` 플러그인 / `native` 엔진. 프로젝트 RAG·프로젝트 API 없음. 실제 검색 여부는 원본 응답의 도구 사용량과 인용 annotations로 구분한다. URL 문자열만으로 실제 검색을 단정하지 않는다.
- API 보고 검색 실행: {summary['questions_with_reported_search']}/50문항, 합계 {summary['web_search_requests']}회. 검색 허용과 실제 검색 사용을 구분한다.
- 추론 강도: medium / 문항당 최대 8192 출력 토큰(추론 포함) / 동시 3건 / 자동 재호출 없음.
- 시작: {started} / 종료: {summary['ended_at']} (한국 시각)
- 답변: {len(answered)}/50 / 원문 두 줄 형식: {summary['format_ok']}/50 / 표시용 두 줄 형식: {summary['rendered_format_ok']}/50 / 정상 종료: {summary['complete_untruncated']}/50
- API 응답에 보고된 합계 비용: ${summary['cost_usd_reported']:.6f} (비용 누락 {summary['cost_missing']}건)

`answers.md`: 스크린샷의 `## v3-XX`, `- 결론:`, `- 근거:` 형식. 두 항목만 있는 답변에서 누락된 목록 기호와 빈 줄만 정리한다. 문장·수치·URL은 고치거나 재생성하지 않음. 원문은 `raw/*.answer.md`와 API 응답에 보존한다.
`raw/`: 문항별 실제 요청 JSON, API 원본 응답 JSON, 원문 답변, 실행 상태. 인증 헤더/API 키는 저장하지 않음.
`inputs.json`: 입력 본문과 넷리스트 SHA-256. `manifest.json`: 모델·시각·사용량·호출 ID·검사 결과.

첨부 TXT의 Astra/Codex CLI 조건과 다른, 사용자가 지정한 Terra/OpenRouter API/웹 검색 켬 실험이다. 모델·실행 도구가 다르므로 동일 실행 조건의 재현이라고 표현하면 안 된다. 앞서 중단한 웹 검색 끔 실행은 이 결과에 섞지 않는다.
입력 격리는 요청 페이로드로 확인 가능하다. 모델 사전학습 데이터나 제공자 내부 보관 정책까지 독립적으로 검증한 것은 아니다.
정답 채점과 프로젝트 agent 비교는 수행하지 않았다. 저장소 수정·git pull·커밋·푸시·외부 사람에게 전달 없음.
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, ensure_ascii=False), flush=True)
    with zipfile.ZipFile(OUT.parent / "terra_web_baseline.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT))
        z.write(Path(__file__), "run_isolated_baseline.py")
    return summary


def main():
    if "--self-check" in sys.argv:
        fixture = "\n---\n".join(f"## v3-{i:02d} (hidden tag)\n넷리스트: data/a.net\n질문: Q{i}" for i in range(1, 51))
        qs = parse_questions(fixture)
        payload = make_payload(qs[0], "NETLIST_SENTINEL")
        assert len(qs) == 50 and "hidden tag" not in json.dumps(payload)
        assert len(payload["messages"]) == 2 and payload["plugins"] == [{"id": "web", "engine": "native"}] and "tools" not in payload
        assert "NETLIST_SENTINEL" in payload["messages"][1]["content"]
        assert "질문: Q1" in payload["messages"][1]["content"]
        assert valid_format("- 결론: A\n- 근거: B") and not valid_format("- 결론: A\n- 근거: B\nextra")
        assert render_answer("결론: A\n\n근거: B") == "- 결론: A\n- 근거: B"
        assert render_answer("unexpected\ncontent\nextra") == "unexpected\ncontent\nextra"
        try:
            parse_questions(fixture.replace("v3-50", "v3-49"))
        except ValueError:
            pass
        else:
            raise AssertionError("Duplicate question accepted")
        print("Self-check passed: parser, IDs, payload isolation, netlist inclusion, format")
        return
    questions, total = prepare()
    print(json.dumps({"questions": len(questions), "with_netlist": len(questions), "request_bytes_total": total, "model": MODEL, "web_search": True, "run": "--run" in sys.argv}, ensure_ascii=False), flush=True)
    if "--run" not in sys.argv:
        return
    key = read_key()
    prior_statuses = [json.loads(p.read_text(encoding="utf-8")) for p in (OUT / "raw").glob("*.status.json")]
    started = min((s["started_at"] for s in prior_statuses), default=now())
    first = call_one(questions[0], key)
    if first["state"] == "answered" and first.get("model_matches") and first.get("finish_reason") == "stop":
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda q: call_one(q, key), questions[1:]))
    summary = summarize(questions, started)
    if summary["answered"] != 50:
        sys.exit(1)


if __name__ == "__main__":
    main()
