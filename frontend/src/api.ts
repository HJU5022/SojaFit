/** 쿠키 API·오류와 SSE 연결. 판정이나 자동 재전송을 하지 않는다. 출처: SPEC 4·8.6절. */
import { consumeSSE } from './stream';
export class ApiError extends Error {
  status: number;
  code: string;
  details: any;
  constructor(message: string, status: number, code = '', details?: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}
async function checked(response: Response) {
  if (response.ok) return response;
  const body = await response.json().catch(() => ({}));
  if (response.status === 401 && !response.url.includes('/auth/'))
    window.dispatchEvent(new Event('session-expired'));
  throw new ApiError(
    body.error?.message ?? '요청을 처리하지 못했습니다.',
    response.status,
    body.error?.code,
    // [왜] 서버 공통 오류는 details를 error 밖 맨 위에 둔다(backend/main.py error_response). error 안에서 읽으면 409 중복 목록이 늘 비었다(#48)
    body.details,
  );
}
export async function api<T = any>(path: string, method = 'GET', body?: any): Promise<T> {
  const multipart = body instanceof FormData;
  const response = await checked(
    await fetch('/api' + path, {
      method,
      credentials: 'include',
      cache: 'no-store',
      headers: body && !multipart ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? (multipart ? body : JSON.stringify(body)) : undefined,
    }),
  );
  return response.status === 204 ? (undefined as T) : response.json();
}
export async function streamRun(
  path: string,
  body: any,
  signal: AbortSignal,
  onFrame: (event: string, data: any) => void,
) {
  const response = await checked(
    await fetch('/api' + path, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
  );
  if (!response.body) throw new Error('실시간 응답이 없습니다. 저장된 상태를 확인해 주세요.');
  await consumeSSE(response.body, onFrame);
}
export const verdicts = {
  IDENTICAL: '동일품',
  SPEC_EQUIVALENT: '사양 동등',
  ROLE_SUFFICIENT: '역할상 충분',
  NOT_SUFFICIENT: '불충족',
  NOT_VERIFIED: '문서로 확인 안 됨',
};
export const statuses: Record<string, string> = {
  running: '검토 중',
  requires_input: '조건 입력 필요',
  completed: '검토 완료',
  refused: '답변 범위 안내',
  failed: '검토 실패',
};
