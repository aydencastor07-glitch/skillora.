-- Stats du livre : on repart de zéro le 28.10.2026 à 17:00 (Berlin), sans rien effacer.
-- Les anciennes lignes (tests) restent en base mais ne sont plus jamais comptées,
-- et le téléphone du propriétaire (empreinte de sa vente test) est toujours exclu.
create or replace function public.admin_ebook(p_product text, p_from timestamptz, p_to timestamptz)
returns jsonb
language sql
stable security definer
set search_path to 'public'
as $function$
  with moi as (
    select buyer_fp from ebook_sales where sale_id = 'pp_3XK25131SH793221W' and buyer_fp is not null
  ), tous as (
    select * from ebook_events
    where product = p_product and created_at >= timestamptz '2026-10-28 16:00+00'
      and visitor is distinct from (select buyer_fp from moi)
  ), toutes_ventes as (
    select * from ebook_sales
    where product = p_product and not refunded and created_at >= timestamptz '2026-10-28 16:00+00'
  ), ev as (
    select * from tous where created_at >= p_from and created_at < p_to
  ), vu as (select * from ev where type = 'view'),
  ve as (
    select * from toutes_ventes where created_at >= p_from and created_at < p_to
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
    'vues_total',  (select count(*) from tous where type = 'view'),
    'clics_total', (select count(*) from tous where type = 'buy_click'),
    'ventes_total',(select count(*) from toutes_ventes),
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
$function$;
