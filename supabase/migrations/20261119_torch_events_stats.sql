-- Truflame : suivi des visiteurs de la boutique (vue, choix d'offre, clic paiement, achat) + tableau de bord.
create table if not exists public.torch_events (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  type text not null,            -- view / offer / pay_click / paid
  visitor text,                  -- empreinte (IP + appareil), jamais l'IP
  qty int,
  country text, city text, device text, os text, source text
);
create index if not exists torch_events_date on public.torch_events (created_at);
alter table public.torch_events enable row level security;
revoke all on public.torch_events from anon, authenticated;

create or replace function public.torch_event(p_type text, p_visitor text, p_qty int, p_country text, p_city text, p_device text, p_os text, p_source text)
returns void language sql security definer set search_path = public as $$
  insert into public.torch_events (type, visitor, qty, country, city, device, os, source)
  select p_type, nullif(p_visitor, ''), p_qty, p_country, p_city, p_device, p_os, p_source
  where p_type in ('view', 'offer', 'pay_click', 'paid');
$$;
revoke all on function public.torch_event(text, text, int, text, text, text, text, text) from public, anon, authenticated;
grant execute on function public.torch_event(text, text, int, text, text, text, text, text) to skillora_stats;

create or replace function public.torch_stats(p_periode text)
returns json language sql security definer set search_path = public as $$
  with d as (select case p_periode when 'auj' then date_trunc('day', now() at time zone 'America/New_York') at time zone 'America/New_York'
      when '7j' then now() - interval '7 days' when '90j' then now() - interval '90 days' when 'tout' then '2000-01-01'::timestamptz
      else now() - interval '30 days' end as debut),
  e as (select * from torch_events, d where created_at >= d.debut),
  o as (select * from torch_orders, d where created_at >= d.debut)
  select json_build_object(
    'visiteurs', (select count(distinct coalesce(visitor, id::text)) from e where type = 'view'),
    'vues', (select count(*) from e where type = 'view'),
    'offres', (select count(*) from e where type = 'offer'),
    'clics_paiement', (select count(distinct coalesce(visitor, id::text)) from e where type = 'pay_click'),
    'commandes', (select count(*) from o),
    'briquets', (select coalesce(sum(qty), 0) from o),
    'revenu_cents', (select coalesce(sum(amount_cents), 0) from o),
    'pays', (select coalesce(json_agg(x order by x.visiteurs desc), '[]') from (
        select ee.c as pays, count(distinct coalesce(ee.visitor, ee.id::text)) filter (where ee.type = 'view') as visiteurs,
               count(distinct coalesce(ee.visitor, ee.id::text)) filter (where ee.type = 'pay_click') as clics,
               (select count(*) from o where o.address->>'country_code' = ee.c) as commandes
        from (select coalesce(country, '?') as c, visitor, id, type from e) ee group by ee.c limit 30) x),
    'sources', (select coalesce(json_agg(x order by x.visiteurs desc), '[]') from (
        select coalesce(source, 'direct') as source, count(distinct coalesce(visitor, id::text)) as visiteurs from e where type = 'view' group by 1 limit 15) x),
    'appareils', (select coalesce(json_agg(x order by x.visiteurs desc), '[]') from (
        select coalesce(device, '?') as appareil, count(distinct coalesce(visitor, id::text)) as visiteurs from e where type = 'view' group by 1) x),
    'offres_choisies', (select coalesce(json_agg(x order by x.qty), '[]') from (
        select qty, count(*) as n from e where type = 'offer' and qty is not null group by 1) x),
    'liste', (select coalesce(json_agg(x order by x.created_at desc), '[]') from (
        select id, created_at, qty, amount_cents, email, name, address, status from o order by created_at desc limit 100) x),
    'jours', (select coalesce(json_agg(x order by x.j), '[]') from (
        select to_char(created_at at time zone 'America/New_York', 'YYYY-MM-DD') as j, count(distinct coalesce(visitor, id::text)) as n
        from e where type = 'view' group by 1) x),
    'dernieres', (select coalesce(json_agg(x order by x.t desc), '[]') from (
        select max(created_at) as t, country as pays, max(city) as ville, max(device) as appareil, max(source) as source,
               bool_or(type = 'pay_click') as clic, bool_or(type = 'paid') as paye, max(qty) filter (where type = 'offer') as offre
        from e group by coalesce(visitor, id::text), country order by max(created_at) desc limit 40) x)
  );
$$;
revoke all on function public.torch_stats(text) from public, anon, authenticated;
grant execute on function public.torch_stats(text) to skillora_stats;

-- Suivi des envois depuis le tableau de bord : à commander → commandé (AutoDS) → expédié, ou remboursé.
create or replace function public.torch_statut(p_id text, p_statut text)
returns void language sql security definer set search_path = public as $$
  update public.torch_orders set status = p_statut where id = p_id and p_statut in ('a_commander', 'commande', 'expedie', 'rembourse');
$$;
revoke all on function public.torch_statut(text, text) from public, anon, authenticated;
grant execute on function public.torch_statut(text, text) to skillora_stats;
