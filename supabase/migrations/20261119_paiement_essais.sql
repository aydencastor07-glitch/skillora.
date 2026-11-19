-- Chaque essai de paiement (ebook + Truflame) : début, refus, annulation, erreur, payé.
-- But : savoir si PayPal fait perdre des ventes, et dans quels pays.
create table if not exists public.paiement_essais (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  site text not null,            -- gesetzbuch / laws / torch
  etape text not null,           -- debut / refus / annule / erreur / paye
  order_id text, detail text,    -- detail = raison PayPal (INSTRUMENT_DECLINED…) ou carte / paypal
  visitor text, country text, city text, device text, os text
);
create index if not exists paiement_essais_date on public.paiement_essais (created_at);
alter table public.paiement_essais enable row level security;
revoke all on public.paiement_essais from anon, authenticated;

create or replace function public.paiement_noter(p_site text, p_etape text, p_order text, p_detail text,
  p_visitor text, p_country text, p_city text, p_device text, p_os text)
returns void language sql security definer set search_path = public as $$
  insert into public.paiement_essais (site, etape, order_id, detail, visitor, country, city, device, os)
  select p_site, p_etape, left(nullif(p_order, ''), 40), left(nullif(p_detail, ''), 80), left(nullif(p_visitor, ''), 64),
         left(nullif(p_country, ''), 2), left(nullif(p_city, ''), 60), p_device, p_os
  where p_site in ('gesetzbuch', 'laws', 'torch') and p_etape in ('debut', 'refus', 'annule', 'erreur', 'paye');
$$;
revoke all on function public.paiement_noter(text, text, text, text, text, text, text, text, text) from public, anon, authenticated;
grant execute on function public.paiement_noter(text, text, text, text, text, text, text, text, text) to skillora_stats;

-- Résumé pour les tableaux de bord : par personne (visiteur), l'issue la plus avancée.
create or replace function public.paiement_stats(p_sites text[], p_periode text)
returns json language sql security definer set search_path = public as $$
  with d as (select case p_periode when 'auj' then date_trunc('day', now() at time zone 'America/New_York') at time zone 'America/New_York'
      when '7j' then now() - interval '7 days' when '90j' then now() - interval '90 days' when '365j' then now() - interval '365 days'
      when 'tout' then '2000-01-01'::timestamptz else now() - interval '30 days' end as debut),
  e as (select p.* from paiement_essais p, d where p.created_at >= d.debut and p.site = any(p_sites)),
  personnes as (
    select coalesce(visitor, order_id, id::text) as qui, max(country) as pays,
           bool_or(etape = 'paye') as paye, bool_or(etape = 'refus') as refus, bool_or(etape = 'annule') as annule,
           bool_or(etape = 'erreur') as erreur, count(*) filter (where etape = 'debut') as essais
    from e group by 1)
  select json_build_object(
    'essais', (select count(*) from e where etape = 'debut'),
    'personnes', (select count(*) from personnes where essais > 0),
    'payes', (select count(*) from personnes where paye),
    'refuses', (select count(*) from personnes where refus and not paye),
    'annules', (select count(*) from personnes where annule and not paye and not refus),
    'erreurs', (select count(*) from personnes where erreur and not paye and not refus and not annule),
    'sans_suite', (select count(*) from personnes where essais > 0 and not (paye or refus or annule or erreur)),
    'raisons', (select coalesce(json_agg(x order by x.n desc), '[]') from (
        select coalesce(detail, '?') as raison, count(*) as n from e where etape in ('refus', 'erreur') group by 1 limit 10) x),
    'pays', (select coalesce(json_agg(x order by x.personnes desc), '[]') from (
        select coalesce(pays, '?') as pays, count(*) as personnes, count(*) filter (where paye) as payes,
               count(*) filter (where not paye) as bloques
        from personnes where essais > 0 group by 1 limit 20) x),
    'derniers', (select coalesce(json_agg(x order by x.t desc), '[]') from (
        select created_at as t, site, etape, detail, country as pays, city as ville, device as appareil from e order by created_at desc limit 30) x)
  );
$$;
revoke all on function public.paiement_stats(text[], text) from public, anon, authenticated;
grant execute on function public.paiement_stats(text[], text) to skillora_stats;
