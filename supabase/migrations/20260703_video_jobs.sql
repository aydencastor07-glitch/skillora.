-- Améliorer ma vidéo : file de jobs traités par le video-worker (serveur externe).
create table if not exists public.video_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'queued' check (status in ('queued','processing','done','error')),
  source_url text not null,
  result_url text,
  context jsonb not null default '{}'::jsonb,  -- niche, retours du scan, durée… (fourni par l'app)
  plan jsonb,                                   -- plan d'amélioration décidé par l'IA (rempli par le worker)
  steps jsonb not null default '[]'::jsonb,     -- [{key,label,state:pending|running|done|skipped,detail}]
  score_before numeric,
  score_after numeric,
  error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

alter table public.video_jobs enable row level security;

-- L'utilisateur suit SES jobs en lecture ; toute écriture passe par le service role
-- (edge function video-improve pour créer, worker pour avancer).
drop policy if exists video_jobs_select_own on public.video_jobs;
create policy video_jobs_select_own on public.video_jobs
  for select using (auth.uid() = user_id);

create index if not exists video_jobs_status_idx on public.video_jobs (status, created_at);
create index if not exists video_jobs_user_idx on public.video_jobs (user_id, created_at desc);

-- Attribution atomique d'un job au worker (évite qu'un job soit pris deux fois
-- si on lance plusieurs workers plus tard).
create or replace function public.claim_video_job()
returns setof public.video_jobs
language sql
security definer
set search_path = public
as $$
  update public.video_jobs
     set status = 'processing', started_at = now()
   where id = (
     select id from public.video_jobs
      where status = 'queued'
      order by created_at asc
      limit 1
      for update skip locked
   )
  returning *;
$$;

revoke all on function public.claim_video_job() from public, anon, authenticated;
grant execute on function public.claim_video_job() to service_role;
