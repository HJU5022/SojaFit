export default function ApprovalPanel({ enabled = false }: { enabled?: boolean }) {
  return <section className="panel result-section" aria-labelledby="approval-heading"><h2 id="approval-heading">사람 승인</h2>
    <p>근거와 판정을 확인한 뒤 승인할 수 있습니다.</p><button disabled={!enabled}>판정 승인</button>
  </section>
}
