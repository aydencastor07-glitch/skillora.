-- E-BOOKS : ce qui se passe sur la page de vente de chaque livre.
-- ============================================================
-- ebook_events : une ligne par VUE (chaque ouverture de la page), par CLIC sur
--                « Acheter ». Le temps passe est ecrit sur la ligne de la vue
--                quand le visiteur quitte la page.
-- ebook_sales  : une ligne par vente Gumroad (le webhook l'ecrit).
-- Rien n'est lisible depuis le navigateur : seules les fonctions (cle de
-- service) ecrivent et lisent. Aucun email, aucune adresse IP.

create table if not exists public.ebook_events (
  id         bigint generated always as identity primary key,
  product    text not null,
  type       text not null check (type in ('view', 'buy_click')),
  visitor    text,
  session    text,
  country    text,
  city       text,
  device     text,
  os         text,
  browser    text,
  referrer   text,
  source     text,
  lang       text,
  seconds    int,
  created_at timestamptz not null default now()
);
alter table public.ebook_events enable row level security;
create index if not exists ebook_events_prod_idx on public.ebook_events (product, created_at);
create index if not exists ebook_events_session_idx on public.ebook_events (session);

create table if not exists public.ebook_sales (
  sale_id     text primary key,
  product     text not null,
  price_cents int,
  currency    text,
  country     text,
  refunded    boolean not null default false,
  created_at  timestamptz not null default now()
);
alter table public.ebook_sales enable row level security;
create index if not exists ebook_sales_prod_idx on public.ebook_sales (product, created_at);

/* Tout le tableau d'un livre en un seul appel, calcule en base. */
create or replace function public.admin_ebook(p_product text, p_from timestamptz, p_to timestamptz)
returns jsonb language sql stable security definer set search_path = public as $$
  with ev as (
    select * from ebook_events where product = p_product and created_at >= p_from and created_at < p_to
  ), vu as (select * from ev where type = 'view'),
  ve as (
    select * from ebook_sales where product = p_product and not refunded and created_at >= p_from and created_at < p_to
  ),
  jours as (
    select generate_series(date_trunc('day', p_from), date_trunc('day', least(p_to, now()) - interval '1 second'), interval '1 day')::date as j
  )
  select jsonb_build_object(
    'vues',        (select count(*) from vu),
    'visiteurs',   (select count(distinct visitor) from vu),
    'clics',       (select count(*) from ev where type = 'buy_click'),
    'cliqueurs',   (select count(distinct visitor) from ev where type = 'buy_click'),
    'ventes',      (select count(*) from ve),
    'revenu_cents',(select coalesce(sum(price_cents), 0) from ve),
    'devise',      (select currency from ve order by created_at desc limit 1),
    'temps_moyen', (select coalesce(round(avg(seconds)), 0) from vu where seconds > 0),
    'temps_median',(select coalesce(percentile_cont(0.5) within group (order by seconds), 0) from vu where seconds > 0),
    'vues_total',  (select count(*) from ebook_events where product = p_product and type = 'view'),
    'clics_total', (select count(*) from ebook_events where product = p_product and type = 'buy_click'),
    'ventes_total',(select count(*) from ebook_sales where product = p_product and not refunded),
    'series', (select coalesce(jsonb_agg(jsonb_build_object('j', j,
        'vues',   (select count(*) from vu where created_at::date = j),
        'clics',  (select count(*) from ev where type = 'buy_click' and created_at::date = j),
        'ventes', (select count(*) from ve where created_at::date = j)) order by j), '[]') from jours),
    'pays', (select coalesce(jsonb_agg(x), '[]') from (
        select jsonb_build_object('code', coalesce(country, '?'), 'n', count(distinct visitor),
          'temps', coalesce(round(avg(seconds) filter (where seconds > 0)), 0),
          'clics', (select count(distinct e2.visitor) from ev e2 where e2.type = 'buy_click' and coalesce(e2.country, '?') = coalesce(vu.country, '?'))) x
        from vu group by country order by count(distinct visitor) desc limit 15) t),
    'villes', (select coalesce(jsonb_agg(jsonb_build_object('k', k, 'n', n)), '[]') from (
        select coalesce(city, '?') || coalesce(' · ' || country, '') k, count(distinct visitor) n
        from vu where city is not null group by city, country order by 2 desc limit 8) t),
    'ventes_pays', (select coalesce(jsonb_agg(jsonb_build_object('k', k, 'n', n)), '[]') from (
        select coalesce(country, '?') k, count(*) n from ve group by 1 order by 2 desc limit 10) t),
    'appareils', (select coalesce(jsonb_agg(jsonb_build_object('k', k, 'n', n)), '[]') from (
        select coalesce(device, '?') k, count(distinct visitor) n from vu group by 1 order by 2 desc) t),
    'systemes', (select coalesce(jsonb_agg(jsonb_build_object('k', k, 'n', n)), '[]') from (
        select coalesce(os, '?') k, count(distinct visitor) n from vu group by 1 order by 2 desc limit 6) t),
    'sources', (select coalesce(jsonb_agg(jsonb_build_object('k', k, 'n', n)), '[]') from (
        select coalesce(source, 'direct') k, count(distinct visitor) n from vu group by 1 order by 2 desc limit 8) t),
    'durees', (select jsonb_build_object(
        'moins10', count(*) filter (where seconds < 10),
        'de10a30', count(*) filter (where seconds >= 10 and seconds < 30),
        'de30a60', count(*) filter (where seconds >= 30 and seconds < 60),
        'de1a3m',  count(*) filter (where seconds >= 60 and seconds < 180),
        'plus3m',  count(*) filter (where seconds >= 180)) from vu where seconds > 0),
    'dernieres', (select coalesce(jsonb_agg(x), '[]') from (
        select jsonb_build_object('t', created_at, 'pays', country, 'ville', city, 'appareil', device,
          'source', source, 'secondes', seconds,
          'clic', exists(select 1 from ev e2 where e2.type = 'buy_click' and e2.session = vu.session)) x
        from vu order by created_at desc limit 15) t)
  );
$$;
revoke all on function public.admin_ebook(text, timestamptz, timestamptz) from public, anon, authenticated;
grant execute on function public.admin_ebook(text, timestamptz, timestamptz) to service_role;
