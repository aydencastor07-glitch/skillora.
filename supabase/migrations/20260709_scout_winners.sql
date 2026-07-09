-- Agent Éclaireur (Scout) — apprentissage AUTONOME du style à partir des vidéos GAGNANTES.
-- ============================================================================================
-- Idée : dès qu'un créateur connecte un compte, on note une "ligne de base" (baseline_at = maintenant
-- + performance médiane du compte). Ensuite, un balayage régulier (edge function scout-winners)
-- repère UNIQUEMENT les vidéos publiées APRÈS la connexion qui EXPLOSENT, et les met en file d'étude :
--   • pour LE CRÉATEUR (user-styles) : une vidéo qui dépasse largement sa norme (>= 3× sa médiane, min 1000 vues) ;
--   • pour GEMINI en général (style-library) : une vidéo qui dépasse 50 000 vues.
-- Le video-worker consomme la file quand il est au repos : Gemini étudie chaque gagnante et enrichit
-- la mémoire de style. Zéro action manuelle : l'agent remplace la recherche humaine.

-- 1) Ligne de base par compte connecté (ce qui existait AVANT la connexion est ignoré).
create table if not exists public.scout_accounts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  platform      text not null,
  handle        text not null,
  baseline_at   timestamptz not null default now(),  -- on n'apprend QUE des vidéos publiées après
  median_views  bigint not null default 0,           -- performance "normale" du compte (détection d'explosion)
  last_scanned_at timestamptz,
  scans         integer not null default 0,
  created_at    timestamptz not null default now(),
  unique (user_id, platform, handle)
);

alter table public.scout_accounts enable row level security;
drop policy if exists scout_accounts_select_own on public.scout_accounts;
create policy scout_accounts_select_own on public.scout_accounts
  for select using (auth.uid() = user_id);

-- 2) File des vidéos gagnantes à faire étudier par Gemini.
--    scope='creator' -> mémoire perso (user-styles/{user_id}) ; scope='global' -> bibliothèque (style-library).
create table if not exists public.winning_videos (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,  -- null autorisé pour du purement global
  platform     text not null,
  video_url    text not null,
  views        bigint not null default 0,
  create_time  bigint,                       -- horodatage de publication (unix), pour trier/journaliser
  niche        text,                          -- optionnel : Gemini la détecte à l'étude
  scope        text not null default 'creator' check (scope in ('creator','global')),
  status       text not null default 'queued' check (status in ('queued','studying','done','error')),
  study_result jsonb,
  error        text,
  created_at   timestamptz not null default now(),
  started_at   timestamptz,
  finished_at  timestamptz,
  unique (video_url, scope)
);

alter table public.winning_videos enable row level security;
drop policy if exists winning_videos_select_own on public.winning_videos;
create policy winning_videos_select_own on public.winning_videos
  for select using (auth.uid() = user_id);

create index if not exists winning_videos_status_idx on public.winning_videos (status, created_at);

-- 3) Attribution atomique d'une gagnante au worker (comme claim_video_job).
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
      order by created_at asc
      limit 1
      for update skip locked
   )
  returning *;
$$;

revoke all on function public.claim_winning_video() from public, anon, authenticated;
grant execute on function public.claim_winning_video() to service_role;
