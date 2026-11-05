"""사용자에게 보이는 거절 문구(일상어). 내부 이유 코드는 따로 로그에 남긴다.

- 역할: 거절 사유(`Reason`)를 사용자가 알아들을 말로 바꾸고, 가능하면 다음에 할 행동을 같이 알려 준다.
- 하지 않는 일: 거절 결정(Supervisor), 코드 이름 노출. "코퍼스" 같은 우리끼리 쓰는 말은 쓰지 않는다.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05, 내부 코드와 사용자 문구 분리)
"""
from backend.multi_agent.contracts import Reason

CLUES = '부품 윗면의 글자, 주문 코드, 데이터시트 파일'


def refusal_message(reason: Reason, parts: list[str] = (), revisions: list[str] = ()) -> str:
    """거절 사유에 맞는 안내 문구. parts · revisions는 질문에서 확인한 값이고 있으면 문구에 넣는다."""
    named = ', '.join(parts) if parts else '질문하신 부품'
    texts = {
        Reason.OUT_OF_SCOPE: '이 서비스는 회로 속 다이오드의 역할과 대체 후보를 데이터시트로 확인해 드려요. 질문하신 내용은 지원하지 않아요.',
        Reason.PART_MISSING: f'{named}의 데이터시트를 찾을 수 없어요. 품번이 맞는지 확인해 주시거나 데이터시트 파일을 알려 주세요.',
        Reason.REVISION_MISSING: f'요청하신 판({", ".join(revisions) if revisions else "개정판"})의 데이터시트가 없어요. 가지고 계신 판의 데이터시트를 알려 주세요.',
        Reason.NOT_FOUND: f'요청하신 내용을 데이터시트에서 확인하지 못했어요. 정확한 품번이나 {CLUES}을 알려 주시면 다시 찾아볼게요.',
        Reason.LIMIT_REACHED: '확인하는 데 시간이 너무 오래 걸려 멈췄어요. 질문을 조금 더 구체적으로 다시 해 주세요.',
        Reason.VERIFY_FAILED: '답변의 근거를 확인하지 못해 답을 보여 드릴 수 없어요. 질문을 다시 해 주세요.',
        Reason.SEARCH_ERROR: '검색 도구를 사용할 수 없어 근거를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
    }
    return texts[reason]  # 거절 사유가 아닌 이유(재시도 사유)를 넘기면 KeyError: 거절 결정서는 이미 거절 사유만 받는다
