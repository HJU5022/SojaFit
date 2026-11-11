import type { ProfileHintDto } from '../api/profile'

// 참고(내 설정): 이번 질문으로 찾은 내 사실. 판정 근거가 아니므로 근거 · 판정과 따로 보인다.
export default function ProfileHints({ hints }: { hints: ProfileHintDto[] }) {
  if (hints.length === 0) return null
  return <aside className="profile-hints" aria-labelledby="profile-hints-heading"><h3 id="profile-hints-heading">참고(내 설정)</h3>
    <ul>{hints.map(hint => <li key={hint.kind}>{hint.text}</li>)}</ul>
    <p>판정 근거가 아니라 내 설정에서 찾은 사실입니다.</p>
  </aside>
}
