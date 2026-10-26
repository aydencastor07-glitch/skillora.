-- Statistiques servies par VERCEL (dossier /api), en se connectant directement
-- a la base. Pourquoi : quand Supabase coupe son « guichet web » (erreur 402,
-- quota gratuit depasse), la base elle-meme reste joignable — la page /stats/
-- et le suivi du livre continuent donc de marcher.
-- Le role skillora_stats ne peut RIEN faire d'autre qu'appeler ces deux
-- fonctions : aucune table ne lui est ouverte. Son mot de passe n'est pas ici
-- (pose a la main, garde dans les variables d'environnement Vercel).

create or replace function public.stats_publiques(p_periode text default '30j')
returns jsonb language plpgsql stable security definer set search_path = public as $$
declare
  fin timestamptz := date_trunc('day', now() at time zone 'utc') at time zone 'utc' + interval '1 day';
  deb timestamptz;
  n int := case p_periode when 'auj' then 1 when '7j' then 7 when '30j' then 30 when '90j' then 90 when '365j' then 365 else 30 end;
begin
  -- « tout » part de la creation du projet (juin 2026) : pas de courbe vide depuis 2020
  deb := case when p_periode = 'tout' then timestamptz '2026-06-01' else fin - make_interval(days => n) end;
  return jsonb_build_object(
    'periode',   jsonb_build_object('debut', deb, 'fin', fin, 'type', p_periode),
    'site',      admin_overview(deb, fin),
    'ebook',     admin_ebook('gesetzbuch', deb, fin),
    'campagnes', (select coalesce(jsonb_agg(jsonb_build_object(
                    'nom', coalesce(x->>'nom', x->>'code'), 'plateforme', x->>'plateforme',
                    'clics', coalesce((x->>'clics')::int, 0), 'inscrits', coalesce((x->>'inscrits')::int, 0),
                    'payants', coalesce((x->>'payants')::int, 0))), '[]'::jsonb)
                  from jsonb_array_elements(coalesce(to_jsonb(admin_pubs(deb, fin)), '[]'::jsonb)) x),
    'genere_le', now());
end $$;

create or replace function public.ebook_enregistrer(
  p_type text, p_product text, p_session text, p_visitor text, p_country text, p_city text,
  p_device text, p_os text, p_browser text, p_referrer text, p_source text, p_lang text, p_seconds int)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_product not in ('gesetzbuch') or coalesce(p_session, '') = '' then return; end if;
  if p_type = 'leave' then
    update ebook_events set seconds = greatest(0, least(1800, coalesce(p_seconds, 0)))
     where session = left(p_session, 64) and product = p_product and type = 'view';
  elsif p_type in ('view', 'buy_click') then
    insert into ebook_events (product, type, session, visitor, country, city, device, os, browser, referrer, source, lang)
    values (p_product, p_type, left(p_session, 64), left(nullif(p_visitor, ''), 64), left(nullif(p_country, ''), 2),
            left(nullif(p_city, ''), 60), p_device, p_os, p_browser, left(nullif(p_referrer, ''), 300),
            left(nullif(p_source, ''), 40), left(nullif(p_lang, ''), 12));
  end if;
end $$;

revoke all on function public.stats_publiques(text) from public, anon, authenticated;
revoke all on function public.ebook_enregistrer(text, text, text, text, text, text, text, text, text, text, text, text, int) from public, anon, authenticated;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'skillora_stats') then
    create role skillora_stats login noinherit;
  end if;
end $$;
grant usage on schema public to skillora_stats;
grant execute on function public.stats_publiques(text) to skillora_stats, service_role;
grant execute on function public.ebook_enregistrer(text, text, text, text, text, text, text, text, text, text, text, text, int) to skillora_stats, service_role;

-- Les statistiques ne sortent QU'AVEC la cle du lien /stats/ (verifiee en base).
create or replace function public.stats_publiques_cle(p_cle text, p_periode text default '30j')
returns jsonb language plpgsql stable security definer set search_path = public, extensions as $$
begin
  -- Sans la bonne cle du lien /stats/, rien ne sort : seule son empreinte est ici.
  if encode(extensions.digest(coalesce(p_cle, ''), 'sha256'), 'hex') <> 'bdc6b46cb6a4b4e49b656f0e807106375b4975fd88ebe742fc02583536589873' then
    raise exception 'cle invalide' using errcode = '28000';
  end if;
  return public.stats_publiques(p_periode);
end $$;
revoke all on function public.stats_publiques_cle(text, text) from public, anon, authenticated;
grant execute on function public.stats_publiques_cle(text, text) to skillora_stats, service_role;
revoke execute on function public.stats_publiques(text) from skillora_stats;
alter role skillora_stats connection limit 5;
