-- SKILLORA — suivi marketing par lien (?src=fb-ads, tiktok-organic, influenceurs…)
-- 1) D'où vient chaque inscrit
alter table public.profiles add column if not exists ref_source text;
create index if not exists profiles_ref_source_idx on public.profiles (ref_source);

-- 2) Chaque clic sur un lien marketing (insert public, lecture service-role uniquement)
create table if not exists public.marketing_clicks (
  id bigint generated always as identity primary key,
  ref text not null,
  path text,
  created_at timestamptz not null default now()
);
alter table public.marketing_clicks enable row level security;
drop policy if exists "log clicks" on public.marketing_clicks;
create policy "log clicks" on public.marketing_clicks
  for insert to anon, authenticated with check (char_length(ref) between 1 and 64);
create index if not exists marketing_clicks_ref_idx on public.marketing_clicks (ref);
create index if not exists marketing_clicks_created_idx on public.marketing_clicks (created_at);
