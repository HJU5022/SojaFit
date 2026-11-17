/** 검토 결과 답·조건 입력 카드. 서버가 보낸 상태를 그리고 판정은 계산하지 않는다. 출처: SPEC 3·4절. */
import { useId, useState } from 'react';
import { ArrowRight, MessageSquare, PanelRight } from 'lucide-react';
import { statuses } from './api';
import { replyCandidates, withoutCorpusCitations } from './display';
import { inputLabel, inputPlaceholder, isBooleanInput } from './inputLabels';
import { Badge, Disclaimer, ErrorBox, GradeHelp, Markdown, Source } from './ui';
import { PriceLookup } from './Candidate';
import type { Candidate, DemoQuestion, Result, Role, Run } from './types';
export function MissingInput({
  result,
  roles,
  demo,
  busy,
  onResume,
}: {
  result: Result;
  roles: Role[];
  demo?: DemoQuestion;
  busy: boolean;
  onResume: (body: any) => void;
}) {
  const fieldId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({}),
    [role, setRole] = useState('');
  return (
    <div className="missing-input" data-testid="requires-input">
      <div className="inline-heading">
        <MessageSquare size={20} />
        <h2>조건을 알려주시면 이어서 검토합니다.</h2>
      </div>
      <p>{result.interrupt.question}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onResume({
            answers: Object.fromEntries(Object.entries(answers).filter(([, v]) => v.trim())),
            ...(result.interrupt.role_choices?.length ? { role } : {}),
          });
        }}
      >
        {!!result.interrupt.role_choices?.length && (
          <label>
            회로에서 맡은 역할
            <select value={role} onChange={(e) => setRole(e.target.value)} required>
              <option value="">역할을 선택하세요</option>
              {result.interrupt.role_choices.map((code) => (
                <option key={code} value={code}>
                  {roles.find((r) => r.code === code)?.name ?? code}
                </option>
              ))}
            </select>
          </label>
        )}
        {result.interrupt.missing?.map((code) =>
          isBooleanInput(code) ? (
            <fieldset key={code} className="boolean-input" disabled={busy}>
              <legend>{inputLabel(code).replace(' (예/아니오)', '')}</legend>
              <div className="boolean-options">
                {['예', '아니오', ''].map((value) => (
                  <label key={value} className="checkbox">
                    <input
                      type="radio"
                      name={`${fieldId}-${code}`}
                      value={value}
                      checked={(answers[code] ?? '') === value}
                      onChange={() => setAnswers({ ...answers, [code]: value })}
                    />
                    {value || '모름'}
                  </label>
                ))}
              </div>
            </fieldset>
          ) : (
            <label key={code}>
              {inputLabel(code)}
              <input
                value={answers[code] ?? ''}
                onChange={(e) => setAnswers({ ...answers, [code]: e.target.value })}
                maxLength={200}
                placeholder={inputPlaceholder(code)}
              />
            </label>
          ),
        )}
        <div className="actions">
          <button className="primary" disabled={busy}>
            이 값으로 계속 검토
          </button>
          <button
            type="button"
            disabled={busy || (!!result.interrupt.role_choices?.length && !role)}
            onClick={() =>
              onResume({ answers: {}, ...(result.interrupt.role_choices?.length ? { role } : {}) })
            }
          >
            모두 모름으로 계속
          </button>
        </div>
        {demo?.resume && (
          <div className="recorded-resume">
            <p>
              이 데모는 기록된 답으로 재개할 수 있습니다.
              {Object.entries(demo.resume.answers)
                .map(([k, v]) => ` ${inputLabel(k)}: ${v}`)
                .join('')}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onResume({
                  answers: demo.resume!.answers,
                  ...(demo.resume!.role ? { role: demo.resume!.role } : {}),
                })
              }
            >
              기록한 답으로 계속하기 <ArrowRight size={15} />
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
/** 닫힌 회로 패널을 열고 회로 구역으로 내리는 작은 글자 단추(#47). 회로에 관한 답 머리에 둔다 */
function CircuitLink({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="circuit-link" onClick={onClick}>
      <PanelRight size={14} />
      회로 보기
    </button>
  );
}
/** 서버가 대상 부품을 정하지 못했을 때 넷리스트의 후보 중 하나를 고르는 카드(조건 카드와 같은 모양). */
export function TargetChoice({
  result,
  busy,
  onResume,
  onCircuit,
}: {
  result: Result;
  busy: boolean;
  onResume: (body: any) => void;
  onCircuit?: () => void;
}) {
  return (
    <div className="missing-input" data-testid="target-choice">
      <div className="inline-heading">
        <MessageSquare size={20} />
        <h2>바꿀 부품을 골라 주시면 이어서 검토합니다.</h2>
        {onCircuit && <CircuitLink onClick={onCircuit} />}
      </div>
      <p>{result.interrupt.question}</p>
      <div className="actions">
        {result.interrupt.target_choices?.map((c) => (
          <button
            key={c.ref}
            type="button"
            disabled={busy}
            onClick={() => onResume({ answers: {}, target: c.ref })}
          >
            {c.ref}
            {c.value ? ` · ${c.value}` : ''}
          </button>
        ))}
      </div>
    </div>
  );
}
export function Reply({
  run,
  onCandidate,
  onCircuit,
}: {
  run: Run;
  onCandidate: (c: Candidate, r: Run) => void;
  /** 회로가 있고 바꿀 부품이 정해진 대화의 답에만 준다(#47) */
  onCircuit?: () => void;
}) {
  const r = run.result,
    candidates = replyCandidates(r.judgement);
  return (
    <div className="assistant-reply">
      <div className="reply-label">
        <span className="mini-mark">↳</span> SojaFit{' '}
        {/* [왜] AI 기본법 제31조 생성물 표시(#27). 판정 답 틀·가격 안내도 AI가 길을 정한 결과라 답마다 붙인다. 상태 칸보다 앞에 둔다 */}
        <small className="ai-label">
          AI 생성<span className="sr-only">: 생성형 AI를 이용해 만든 답변입니다</span>
        </small>{' '}
        <span className="reply-status">{statuses[r.status] ?? r.stage}</span>
        {onCircuit && <CircuitLink onClick={onCircuit} />}
      </div>
      {/* [왜] 웹 검색 장애를 "못 찾음"과 구별해 알린다(#28) */}
      {r.web_search_unavailable && (
        <p role="status" className="notice">
          웹 검색을 잠시 쓸 수 없어 등록된 자료로만 답했어요.
        </p>
      )}
      {candidates.length ? (
        <>
          <h2>후보별 검토 결과입니다.</h2>
          <div className="candidate-list">
            {candidates.map((c, i) => (
              <button key={i} className="candidate-card" onClick={() => onCandidate(c, run)}>
                <div>
                  <strong>{c.part}</strong>
                  <Badge verdict={c.verdict} />
                </div>
                <p>
                  {c.board_change === true
                    ? '기판 수정 필요'
                    : c.board_change === false
                      ? '기판 수정 불필요'
                      : '기판 수정 여부 확인 안 됨'}
                </p>
                <span>
                  조건과 근거 보기 <ArrowRight size={16} />
                </span>
              </button>
            ))}
          </div>
          <details className="full-answer">
            <summary>전체 답변 보기</summary>
            <div className="markdown">
              <Markdown>{withoutCorpusCitations(r.answer, r.evidence)}</Markdown>
            </div>
          </details>
        </>
      ) : r.answer ? (
        <div className="markdown">
          <Markdown>{withoutCorpusCitations(r.answer, r.evidence)}</Markdown>
        </div>
      ) : null}
      <ErrorBox error={r.error?.message ?? null} />
      {r.evidence.length > 0 && (
        <details className="evidence-list">
          <summary>문서 근거</summary>
          <GradeHelp />
          {r.evidence.map((s, i) => (
            <Source cite={s} key={i} />
          ))}
        </details>
      )}
      {r.price_parts.map((p) => (
        <PriceLookup key={p} part={p} />
      ))}
      {/* [왜] 면책 문구는 후보 판정이 든 답에만 둔다. 일상 대화 · 부품 목록에 붙으면 하지 않은 판정을 한 것처럼 읽힌다(#55). "AI 생성" 표시는 답마다 그대로 */}
      {candidates.length > 0 && <Disclaimer />}
    </div>
  );
}
