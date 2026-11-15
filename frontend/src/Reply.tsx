/** 검토 결과 답·조건 입력 카드. 서버가 보낸 상태를 그리고 판정은 계산하지 않는다. 출처: SPEC 3·4절. */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowRight, MessageSquare } from 'lucide-react';
import { fieldNames, statuses } from './api';
import { Badge, Disclaimer, ErrorBox, Source } from './ui';
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
        {result.interrupt.missing?.map((code) => (
          <label key={code}>
            {fieldNames[code] ?? code}
            <input
              value={answers[code] ?? ''}
              onChange={(e) => setAnswers({ ...answers, [code]: e.target.value })}
              maxLength={200}
              placeholder="값과 단위, 또는 모름"
            />
          </label>
        ))}
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
                .map(([k, v]) => ` ${fieldNames[k] ?? k}: ${v}`)
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
export function Reply({
  run,
  onCandidate,
}: {
  run: Run;
  onCandidate: (c: Candidate, r: Run) => void;
}) {
  const r = run.result,
    candidates = [
      ...(r.judgement.results ?? []),
      ...(r.judgement.shown ?? []),
      ...(r.judgement.unverified ?? []),
    ].filter((c, i, all) => all.findIndex((x) => x.part === c.part && x.role === c.role) === i);
  return (
    <div className="assistant-reply">
      <div className="reply-label">
        <span className="mini-mark">↳</span> SojaFit <span>{statuses[r.status] ?? r.stage}</span>
      </div>
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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
            </div>
          </details>
        </>
      ) : r.answer ? (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
        </div>
      ) : null}
      <ErrorBox error={r.error?.message ?? null} />
      {r.evidence.length > 0 && (
        <details className="evidence-list">
          <summary>문서 근거</summary>
          {r.evidence.map((s, i) => (
            <Source cite={s} key={i} />
          ))}
        </details>
      )}
      {r.price_parts.map((p) => (
        <PriceLookup key={p} part={p} />
      ))}
      <Disclaimer />
    </div>
  );
}
