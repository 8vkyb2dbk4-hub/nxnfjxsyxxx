-- AI 前沿日报 v9: Supabase sync schema
-- 在 Supabase SQL Editor 中执行一次。

create table if not exists public.ai_brief_sync_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  state jsonb not null default '{}'::jsonb,
  revision bigint not null default 0,
  updated_at timestamptz not null default now()
);

alter table public.ai_brief_sync_state enable row level security;

drop policy if exists "read own ai brief state" on public.ai_brief_sync_state;
create policy "read own ai brief state"
on public.ai_brief_sync_state
for select to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists "insert own ai brief state" on public.ai_brief_sync_state;
create policy "insert own ai brief state"
on public.ai_brief_sync_state
for insert to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists "update own ai brief state" on public.ai_brief_sync_state;
create policy "update own ai brief state"
on public.ai_brief_sync_state
for update to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create index if not exists ai_brief_sync_updated_at_idx
on public.ai_brief_sync_state(updated_at desc);

-- Atomic revision check prevents concurrent devices overwriting each other.
revoke all on public.ai_brief_sync_state from anon;
grant select, insert, update on public.ai_brief_sync_state to authenticated;
create or replace function public.ai_brief_compare_and_swap(p_state jsonb, p_revision bigint)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare new_revision bigint;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_revision = 0 then
    insert into public.ai_brief_sync_state(user_id,state,revision)
      values(auth.uid(),p_state,1) on conflict(user_id) do nothing
      returning revision into new_revision;
  else
    update public.ai_brief_sync_state set state=p_state,revision=revision+1,updated_at=now()
      where user_id=auth.uid() and revision=p_revision returning revision into new_revision;
  end if;
  return jsonb_build_object('ok',new_revision is not null,'revision',new_revision);
end;
$$;
revoke all on function public.ai_brief_compare_and_swap(jsonb,bigint) from public, anon;
grant execute on function public.ai_brief_compare_and_swap(jsonb,bigint) to authenticated;
