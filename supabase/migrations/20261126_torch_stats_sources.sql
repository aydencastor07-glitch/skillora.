-- Tableau /stats/truflame.html : par source (lien utm_source), visiteurs + visites + clics « Acheter ».
update public.torch_events set source = 'Instagram' where source = 'ig';
update public.torch_events set source = 'Facebook' where source = 'fb';

CREATE OR REPLACE FUNCTION public.torch_stats(p_periode text)
 RETURNS json
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  with d as (select greatest('2026-11-23 16:00:00+00'::timestamptz, case p_periode when 'auj' then date_trunc('day', now() at time zone 'America/New_York') at time zone 'America/New_York'
      when '7j' then now() - interval '7 days' when '90j' then now() - interval '90 days' when 'tout' then '2000-01-01'::timestamptz
      else now() - interval '30 days' end) as debut),
  e as (select * from torch_events, d where created_at >= d.debut),
  o as (select * from torch_orders, d where created_at >= d.debut),
  cliqueurs as (select distinct coalesce(visitor, id::text) as vk from e where type = 'pay_click')
  select json_build_object(
    'visiteurs', (select count(distinct coalesce(visitor, id::text)) from e where type = 'view'),
    'vues', (select count(*) from e where type = 'view'),
    'offres', (select count(*) from e where type = 'offer'),
    'clics_paiement', (select count(*) from cliqueurs),
    'commandes', (select count(*) from o),
    'briquets', (select coalesce(sum(qty), 0) from o),
    'revenu_cents', (select coalesce(sum(amount_cents), 0) from o),
    'pays', (select coalesce(json_agg(x order by x.visiteurs desc), '[]') from (
        select ee.c as pays, count(distinct coalesce(ee.visitor, ee.id::text)) filter (where ee.type = 'view') as visiteurs,
               count(distinct coalesce(ee.visitor, ee.id::text)) filter (where ee.type = 'pay_click') as clics,
               (select count(*) from o where o.address->>'country_code' = ee.c) as commandes
        from (select coalesce(country, '?') as c, visitor, id, type from e) ee group by ee.c limit 30) x),
    'sources', (select coalesce(json_agg(x order by x.visiteurs desc), '[]') from (
        select s.source, count(distinct s.vk) as visiteurs, sum(s.nv) as vues,
               count(distinct s.vk) filter (where s.vk in (select vk from cliqueurs)) as clics
        from (select coalesce(visitor, id::text) as vk, coalesce(source, 'direct') as source, count(*) as nv
              from e where type = 'view' group by 1, 2) s
        group by 1 limit 15) x),
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
$function$;
