-- Études patientes : compteur d'essais + attente de 2 h entre deux tentatives
-- (le niveau gratuit de Gemini limite le rythme ET le volume journalier).
alter table public.winning_videos add column if not exists attempts int not null default 0;

create or replace function public.claim_winning_video()
returns setof public.winning_videos
language sql
security definer
set search_path = public
as $$
  update public.winning_videos
     set status = 'studying', started_at = now()
   where id = (
     select id from public.winning_videos
      where status = 'queued'
        and (attempts = 0 or started_at is null or started_at < now() - interval '2 hours')
      order by attempts asc, created_at asc
      limit 1
      for update skip locked
   )
  returning *;
$$;

revoke all on function public.claim_winning_video() from public, anon, authenticated;
grant execute on function public.claim_winning_video() to service_role;
