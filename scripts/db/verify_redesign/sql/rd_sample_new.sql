-- 새 기준선 구조(db/020_service_baseline.sql)에 맞는 합성 데이터. 백업 복원 왕복 시험(rd_test7.sh)용이다.
INSERT INTO users(login_id,password_hash,role) VALUES ('a@example.test','x','user'),('b@example.test','x','admin');
INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES (repeat('a',64),1,now() + interval '1 day');
INSERT INTO projects(user_id,name,source_kind,demo_id) VALUES (1,'p1','demo','breadboard_supply'),(1,'p2','upload',NULL);
INSERT INTO circuits(project_id,connections,source_sha256,parser_version) VALUES (1,'{"parts":[{"ref":"D1"}],"nets":[]}',repeat('a',64),'v1'),(2,'{"parts":[],"nets":[]}',repeat('b',64),'v1');
INSERT INTO threads(id,project_id) VALUES ('00000000-0000-0000-0000-000000000001',1),('00000000-0000-0000-0000-000000000002',2);
INSERT INTO runs(id,thread_id,status,safe_result) VALUES
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001','completed','{"answer":"a","question_type":"candidate_judge","price_parts":[],"interrupt":null,"judgement":{},"evidence":[]}');
INSERT INTO messages(thread_id,run_id,role,content) VALUES
 ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','user','q1'),
 ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','assistant','a1');
INSERT INTO approvals(user_id,message_id,candidate_part,verdict,part_number,snapshot) VALUES
 (1,2,'TSC 1N4007G','ROLE_SUFFICIENT','1N4007G','{"answer":"a","candidate":{"part":"TSC 1N4007G","verdict":"ROLE_SUFFICIENT","part_number":"1N4007G"},"evidence":[{"k":[{"v":1}]}]}');
INSERT INTO quotes(user_id,approval_id,part_number,quantity) VALUES (1,1,'1N4007G',5);
INSERT INTO approved_cases(user_id,approval_id) VALUES (1,1);
INSERT INTO sojafit_agent.threads(id,user_id,target) VALUES ('00000000-0000-0000-0000-000000000001',1,'D1');
INSERT INTO sojafit_agent.messages(thread_id,role,content) VALUES ('00000000-0000-0000-0000-000000000001','user','q1');
INSERT INTO sojafit_agent.analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery) VALUES
 ('20000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001',1,'r','real','DONE',10,'[]','t','queued');
INSERT INTO sojafit_agent.analysis_usage(user_id,day,next_allowed) VALUES (1,CURRENT_DATE,now());
INSERT INTO sojafit_agent.analysis_service_usage(day,reserved_tokens) VALUES (CURRENT_DATE,10);
INSERT INTO sojafit_agent.checkpoints(thread_id,checkpoint_id) VALUES ('00000000-0000-0000-0000-000000000001','c1');
INSERT INTO sojafit_agent.checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type) VALUES ('00000000-0000-0000-0000-000000000001','','ch','1','t');
INSERT INTO sojafit_agent.checkpoint_writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,blob) VALUES ('00000000-0000-0000-0000-000000000001','','c1','t',0,'ch','\x00');
