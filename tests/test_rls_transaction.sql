-- Execute against the dedicated AI Brief project. All test data rolls back.
begin;
select set_config('test.a',gen_random_uuid()::text,true),set_config('test.b',gen_random_uuid()::text,true);
insert into auth.users(id,email) values
 (current_setting('test.a')::uuid,'rls-a-'||current_setting('test.a')||'@example.invalid'),
 (current_setting('test.b')::uuid,'rls-b-'||current_setting('test.b')||'@example.invalid');
set local role authenticated;
select set_config('request.jwt.claim.sub',current_setting('test.b'),true);
select public.ai_brief_compare_and_swap('{"test":"B"}'::jsonb,0);
select set_config('request.jwt.claim.sub',current_setting('test.a'),true);
do $$
declare r jsonb; n integer;
begin
 r:=public.ai_brief_compare_and_swap('{"test":"A"}'::jsonb,0);
 if r->>'ok'<>'true' or r->>'revision'<>'1' then raise exception 'initial CAS failed';end if;
 r:=public.ai_brief_compare_and_swap('{"test":"A2"}'::jsonb,1);
 if r->>'ok'<>'true' or r->>'revision'<>'2' then raise exception 'update CAS failed';end if;
 r:=public.ai_brief_compare_and_swap('{"test":"stale"}'::jsonb,1);
 if r->>'ok'<>'false' then raise exception 'stale revision allowed';end if;
 select count(*) into n from public.ai_brief_sync_state;
 if n<>1 then raise exception 'cross-user row visible';end if;
 update public.ai_brief_sync_state set state='{}' where user_id=current_setting('test.b')::uuid;
 get diagnostics n=row_count;
 if n<>0 then raise exception 'cross-user update allowed';end if;
 begin
  insert into public.ai_brief_sync_state(user_id,state) values(current_setting('test.b')::uuid,'{}');
  raise exception 'cross-user insert allowed';
 exception when insufficient_privilege then null;
 end;
 begin
  update public.ai_brief_sync_state set user_id=current_setting('test.b')::uuid where user_id=current_setting('test.a')::uuid;
  raise exception 'ownership reassignment allowed';
 exception when insufficient_privilege then null;
 end;
end $$;
reset role;
set local role anon;
do $$
begin
 begin
  perform * from public.ai_brief_sync_state;
  raise exception 'anonymous read allowed';
 exception when insufficient_privilege then null;
 end;
 begin
  perform public.ai_brief_compare_and_swap('{}',0);
  raise exception 'anonymous RPC allowed';
 exception when insufficient_privilege then null;
 end;
end $$;
reset role;
select 'PASS: PostgreSQL RLS ownership, anonymous denial, CAS revisions; all fixtures rolled back' as result;
rollback;
