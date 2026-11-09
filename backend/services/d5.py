"""D5 실행 어댑터: 검증된 회로와 체크포인터만 받아 그래프를 실행한다."""
from contextlib import asynccontextmanager
import re
from typing import AsyncIterator, Literal

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from backend.graph.nodes import circuit_around
from backend.conversations.dto import safe_judgement
from backend.multi_agent.build import build_graph
from backend.multi_agent.facts import make_lookup


class RunInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    target_ref: str
    connections: dict
    conditions: str = ''


class RunEvent(BaseModel):
    type: Literal['status', 'requires_input', 'completed', 'refused', 'failed']
    stage: str = ''
    state: dict = Field(default_factory=dict)
    interrupt: dict = Field(default_factory=dict)


def public_state(state: dict) -> dict:
    """공개 계약에 구조화된 값만 선택한다. 원문 문서와 보고서는 복사하지 않는다."""
    answer = state.get('answer', '')
    question_type = state.get('question_type', '')
    parts = state.get('price_parts', [])
    result = {'answer': answer if isinstance(answer, str) else '',
              'question_type': question_type if isinstance(question_type, str) and question_type in {'out_of_scope', 'chat', 'other_part', 'price', 'role', 'rating', 'candidate_judge', 'candidate_find'} else '',
              'price_parts': [p for p in parts if isinstance(p, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}', p)] if isinstance(parts, list) else []}
    reports = state.get('final_reports') or state.get('reports') or []
    cited = {str(item) for report in reports if isinstance(report, dict)
             for item in report.get('evidence_ids', [])}
    evidence = []
    for doc in state.get('docs') or []:
        if not isinstance(doc, dict) or str(doc.get('chunk_id')) not in cited:
            continue
        document, page, table = doc.get('file'), doc.get('page'), doc.get('table')
        if not isinstance(document, str) or not isinstance(page, (int, str)) or not isinstance(table, (str, type(None))):
            continue
        entry = {'document': document.replace('\\', '/').rsplit('/', 1)[-1], 'page': page,
                 'table': table or '', 'row': '', 'section': '', 'citation_number': str(doc['chunk_id'])}
        if entry not in evidence:
            evidence.append(entry)
    if evidence:
        result['evidence'] = evidence
    if judgement := safe_judgement(state.get('judgement')):
        result['judgement'] = judgement
    return result


class D5Service:
    def __init__(self, *, chat, retriever, lookup, specs, find, checkpointer):
        # parse 입력은 이미 변환한 필드다. 파일 경로나 원본 업로드는 받지 않는다.
        self.graph = build_graph(chat=chat, retriever=retriever, lookup=lookup, specs=specs, find=find,
                                 checkpointer=checkpointer, judge_enabled=True,
                                 parse=lambda state: {k: state.get(k, '') for k in ('question', 'conditions', 'target', 'target_part')})

    async def start(self, thread_id: str, run_input: RunInput) -> AsyncIterator[RunEvent]:
        connections = run_input.connections
        normalized = {'components': connections.get('components', connections.get('parts', [])), 'nets': connections.get('nets', [])}
        state = {'question': run_input.question, 'conditions': run_input.conditions, 'target': run_input.target_ref,
                 'target_part': circuit_around(normalized, run_input.target_ref)}
        async for event in self._run(thread_id, state):
            yield event

    async def resume(self, thread_id: str, answers: dict, role: str | None = None) -> AsyncIterator[RunEvent]:
        payload = {'answers': answers}
        if role is not None:
            payload['role'] = role
        async for event in self._run(thread_id, Command(resume=payload)):
            yield event

    async def delete_thread(self, thread_id: str) -> None:
        """소유권 검증된 thread의 checkpoint를 라이브러리 API로 삭제한다."""
        await self.graph.checkpointer.adelete_thread(thread_id)

    async def _run(self, thread_id, value):
        config = {'configurable': {'thread_id': thread_id}}
        yield RunEvent(type='status', stage='running')
        try:
            async for update in self.graph.astream(value, config, stream_mode='updates'):
                if '__interrupt__' in update:
                    items = update['__interrupt__']
                    payload = items[0].value if items else {}
                    yield RunEvent(type='requires_input', stage='judge', interrupt={k: payload[k] for k in ('missing', 'role_choices', 'question') if k in payload})
                    return
                for stage in update:
                    yield RunEvent(type='status', stage=stage)
            snapshot = await self.graph.aget_state(config)
            state = snapshot.values
            kind = 'refused' if state.get('refusal') else 'completed'
            yield RunEvent(type=kind, stage='finished', state=public_state(state))
        except Exception:
            yield RunEvent(type='failed', stage='failed')


async def setup_checkpoints(connection_string: str) -> None:
    """관리자가 준비한 별도 DB에서 라이브러리 경로로만 체크포인트 표 설치."""
    async with AsyncPostgresSaver.from_conn_string(connection_string) as saver:
        await saver.setup()
        # 라이브러리가 만든 표도 다른 공개 표와 같은 접근 경계를 적용한다.
        for name in ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations'):
            await saver.conn.execute(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY')
            await saver.conn.execute(f'REVOKE ALL ON {name} FROM PUBLIC')
            for role in ('anon', 'authenticated'):
                cursor = await saver.conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,))
                if await cursor.fetchone():
                    await saver.conn.execute(f'REVOKE ALL ON {name} FROM {role}')


@asynccontextmanager
async def production_service(connection_string: str):
    """호출자가 수명과 소유권 검증을 관리한다. setup은 별도 관리 단계다."""
    from backend.graph.mcp_retriever import StdioMcpRetriever
    from backend.services import llm
    async with AsyncPostgresSaver.from_conn_string(connection_string) as saver:
        with StdioMcpRetriever() as mcp:
            yield D5Service(chat=llm.node_chat, retriever=mcp, lookup=make_lookup(mcp.check, mcp.part_specs),
                            specs=mcp.part_specs, find=mcp.find_parts, checkpointer=saver)
