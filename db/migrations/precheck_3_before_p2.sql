-- 실행 전 점검 3/4: migrate_prod_3_contract_p2.sql 직전(P1 contract와 P2 새 코드 배포 뒤). 읽기 전용, 개수만 출력.
-- 사용: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -At -f db/migrations/precheck_3_before_p2.sql
BEGIN READ ONLY;
SELECT '[1] 이력 표 기대: 2026-11-expand, 2026-11-contract-p1 포함 = ' || (SELECT COALESCE(string_agg(version, ', ' ORDER BY applied_at), '(없음)') FROM public.app_migrations);
SELECT '[2] sojafit_agent.approvals 행(기대 0. 0이 아니면 확인 변수 app.ack_drop_agent_approvals 필요) = ' || count(*) FROM sojafit_agent.approvals;
SELECT '[3] sojafit_agent.circuits 행 = ' || count(*) FROM sojafit_agent.circuits;
SELECT '[4] 그중 netlist가 빈 글자가 아닌 행(되돌리면 사라지는 값. 기대 0) = ' || count(*) FROM sojafit_agent.circuits WHERE netlist <> '';
SELECT '[5] 그중 filename이 프로젝트 이름과 다른 행(기대 0) = ' || count(*) FROM sojafit_agent.circuits c WHERE EXISTS (SELECT 1 FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id JOIN public.projects p ON p.id = pt.project_id WHERE t.circuit_id = c.id AND c.filename <> p.name);
SELECT '[6] 그중 thread · 화면 대화 · public 회로로 이어지지 않는 행(기대 0) = ' || count(*) FROM sojafit_agent.circuits c WHERE NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id JOIN public.projects p ON p.id = pt.project_id JOIN public.circuits pc ON pc.project_id = p.id WHERE t.circuit_id = c.id);
SELECT '[7] 위 [4]~[6] 중 하나라도 0이 아니면 P2에 app.ack_drop_agent_circuits 확인이 필요하다. 이 가드의 판정 행 수 = ' || count(*) FROM sojafit_agent.circuits c
    WHERE NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t JOIN public.threads pt ON pt.id = t.id JOIN public.projects p ON p.id = pt.project_id JOIN public.circuits pc ON pc.project_id = p.id WHERE t.circuit_id = c.id AND c.netlist = '' AND c.filename = p.name);
SELECT '[8] 체크포인트가 가리키는 thread가 sojafit_agent.threads에 없는 개수(참고) = ' || (SELECT count(DISTINCT thread_id) FROM sojafit_agent.checkpoints c WHERE NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t WHERE t.id::text = c.thread_id));
ROLLBACK;
