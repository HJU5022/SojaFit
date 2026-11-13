INSERT INTO users(login_id,password_hash,role) VALUES ('a@example.test','x','user'),('b@example.test','x','admin');
INSERT INTO projects(user_id,name,source_kind,demo_id) VALUES (1,'p1','demo','breadboard_supply'),(1,'p2','upload',NULL);
INSERT INTO circuits(project_id,connections,source_sha256,parser_version) VALUES (1,'{"parts":[]}',repeat('a',64),'v1'),(2,'{"parts":[]}',repeat('b',64),'v1');
INSERT INTO threads(id,project_id) VALUES ('00000000-0000-0000-0000-000000000001',1),('00000000-0000-0000-0000-000000000002',2);
INSERT INTO runs(id,thread_id,status,safe_result) VALUES
 ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001','completed','{"answer":"a","question_type":"candidate_judge","price_parts":[],"interrupt":{"missing":[],"role_choices":[],"question":""},"judgement":null,"evidence":[]}'),
 ('10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000002','completed','{"answer":"b","question_type":"candidate_judge","price_parts":[],"interrupt":{"missing":[],"role_choices":[],"question":""},"judgement":null,"evidence":[]}');
INSERT INTO messages(thread_id,run_id,role,content) VALUES
 ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','user','q1'),
 ('00000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','assistant','a1'),
 ('00000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002','user','q2'),
 ('00000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002','assistant','a2');
INSERT INTO approvals(user_id,message_id,snapshot) VALUES
 (1,2,'{"answer":"a","question_type":"candidate_judge","candidate":{"part":"TSC 1N4007G","verdict":"ROLE_SUFFICIENT","part_number":"1N4007G"},"evidence":[]}'),
 (1,4,'{"answer":"b","question_type":"candidate_judge","candidate":{"part":"TSC SS34","verdict":"IDENTICAL"},"evidence":[]}');
INSERT INTO quotes(user_id,approval_id,part_number,quantity,snapshot) SELECT user_id,id,'1N4007G',5,snapshot FROM approvals WHERE id=1;
INSERT INTO approved_cases(user_id,approval_id,snapshot) SELECT user_id,id,snapshot FROM approvals;
INSERT INTO sojafit_agent.circuits(id,user_id,filename,netlist,connections) VALUES
 ('00000000-0000-0000-0000-000000000001',1,'p1','','{"parts":[]}'),('00000000-0000-0000-0000-000000000002',1,'p2','','{"parts":[]}');
INSERT INTO sojafit_agent.threads(id,user_id,circuit_id,target) VALUES
 ('00000000-0000-0000-0000-000000000001',1,'00000000-0000-0000-0000-000000000001','D1'),('00000000-0000-0000-0000-000000000002',1,'00000000-0000-0000-0000-000000000002','D2');
INSERT INTO sojafit_agent.messages(thread_id,role,content) VALUES ('00000000-0000-0000-0000-000000000001','user','q1'),('00000000-0000-0000-0000-000000000002','user','q2');
INSERT INTO sojafit_agent.analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery) VALUES
 ('20000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001',1,'r','real','DONE',10,'[]','t','queued');
INSERT INTO sojafit_agent.analysis_usage(user_id,day,next_allowed) VALUES (1,CURRENT_DATE,now());
INSERT INTO sojafit_agent.checkpoints(thread_id,checkpoint_id) VALUES ('00000000-0000-0000-0000-000000000001','c1'),('00000000-0000-0000-0000-000000000002','c2');
INSERT INTO sojafit_agent.checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type) VALUES ('00000000-0000-0000-0000-000000000001','','ch','1','t');
INSERT INTO sojafit_agent.checkpoint_writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,blob) VALUES ('00000000-0000-0000-0000-000000000001','','c1','t',0,'ch','\x00');
