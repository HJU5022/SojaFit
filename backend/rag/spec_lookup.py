"""사양 코드 목록과 찾기 순서 규칙(카드 찾기 · 판정이 함께 쓴다).

- 역할: 사양 코드 목록 `CODES`(대체 부품 에이전트 import), 조건 자리 기본값 `DEFAULT_SLOT`, 삽입형 패키지 이름 `THT_PACKAGES`,
  패키지 이름 맞추기 `_norm_package`와 기준에서 먼 정도 `_ratio`(카드 찾기 `card_find.py` import).
- 하지 않는 일: 판정 5종과 대체 가능 여부(`backend/judge/`, AGENTS 지킬 것 7), 단위 환산(값은 이미 SI), DB 조회, LLM 호출.
  부품 사양 표(part_specifications)와 그 SQL 조회(`part_specs` · `find_candidates`)는 11-09에 버리고 11-10에 지웠다(ADR 0016).
- 출처: ADR 0013(대체됨) · 0016, SPEC.md 8.7
"""
import re

# 5.7·ADR 0013의 17개 + PACKAGE(패키지 이름, text_value) + AEC_Q101(문서가 밝힌 AEC-Q101 인증, text_value, lab v3 11-06)
CODES = ('VRRM', 'IF_AV', 'IFSM', 'VF', 'IR', 'TRR', 'VZ', 'PD', 'CJ', 'TJ_MAX',
         'VR', 'VRWM', 'VBR', 'VC', 'IPP', 'PPPM', 'VESD', 'PACKAGE', 'AEC_Q101')
# [왜] 최소·대표·최대 표시 없는 정격 칸은 최대로, 정전용량은 대표로 읽는다(카드 읽기 규칙 pipeline/specs.py). slot을 안 주면 같은 자리를 본다
DEFAULT_SLOT = {'CJ': 'typ'}


ALIASES = {'MINIMELF': 'MMELF'}  # [왜] 사용자는 MiniMELF라고 쓰지만 TSC 문서는 MMELF로 적는다(BZV55 등 4문서, 11-06 v3-13)
# 삽입형(스루홀) 패키지 이름(_norm_package 모양). 판정의 실장 방식 거르기(judge.mount_of)와 찾기의 문서 고르기(card_find.code_pick)가 같이 쓴다
THT_PACKAGES = {'DO204AC', 'DO15', 'DO41', 'DO204AL', 'DO201', 'DO201AD', 'TO220AB', 'TO247AD', 'TO3P', 'TO220AC', 'GBU', 'DO35',
                'R6', 'TO247', 'KBJL', 'KBPF', 'TO247BD'}


def _norm_package(name):
    key = re.sub(r'[^A-Z0-9]', '', (name or '').upper())  # 영문 · 숫자만(데이터시트마다 'DO-214AC' · 'DO214AC'처럼 하이픈을 다르게 적는다)
    return ALIASES.get(key, key)


def _ratio(cond, row):
    """조건을 채운 행 값이 기준에서 얼마나 먼지(1이면 기준과 같고 클수록 멂). 이상은 값/기준, 이하는 기준/값.

    기준이나 값이 0 이하라 비율을 못 내면 1(순서에 영향 없음)이다. 채운 행의 비율은 늘 1 이상이라 가장 먼 조건을 고를 때 묻힌다.
    """
    v = row[cond.get('slot') or DEFAULT_SLOT.get(cond['code'], 'max')]  # 찾기가 이 칸으로 걸렀으므로(card_find._meets) 값이 있다
    ratios = ([v / cond['gte']] if 'gte' in cond and cond['gte'] > 0 else []) + ([cond['lte'] / v] if 'lte' in cond and v > 0 else [])
    return max(ratios, default=1.0)
