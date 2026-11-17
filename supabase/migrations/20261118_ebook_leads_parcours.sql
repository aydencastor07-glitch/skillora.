-- Nouvelle page /laws/ : parcours en étapes + emails donnés avant le paiement.
-- 1) Suivi des étapes : 'cta' (clic « Get the ebook ↓ »), 'reviews' (avis vus), 'email' (email donné), en plus de 'view' et 'buy_click'.
alter table public.ebook_events drop constraint if exists ebook_events_type_check;
alter table public.ebook_events add constraint ebook_events_type_check check (type in ('view', 'buy_click', 'cta', 'reviews', 'email'));

create or replace function public.ebook_enregistrer(p_type text, p_product text, p_session text, p_visitor text, p_country text, p_city text, p_device text, p_os text, p_browser text, p_referrer text, p_source text, p_lang text, p_seconds integer)
 returns void language plpgsql security definer set search_path to 'public' as $function$
begin
  if p_product not in ('gesetzbuch', 'laws') or coalesce(p_session, '') = '' then return; end if;
  if p_type = 'leave' then
    update ebook_events set seconds = greatest(0, least(1800, coalesce(p_seconds, 0)))
     where session = left(p_session, 64) and product = p_product and type = 'view';
  elsif p_type in ('view', 'buy_click', 'cta', 'reviews', 'email') then
    if coalesce(p_visitor, '') <> '' and exists (
      select 1 from ebook_events where product = p_product and type = p_type and visitor = left(p_visitor, 64)) then
      return;
    end if;
    insert into ebook_events (product, type, session, visitor, country, city, device, os, browser, referrer, source, lang)
    values (p_product, p_type, left(p_session, 64), left(nullif(p_visitor, ''), 64), left(nullif(p_country, ''), 2),
            left(nullif(p_city, ''), 60), p_device, p_os, p_browser, left(nullif(p_referrer, ''), 300),
            left(nullif(p_source, ''), 40), left(nullif(p_lang, ''), 12));
  end if;
end $function$;

-- 2) Emails donnés à l'étape 1 de la caisse (illisibles depuis le navigateur : RLS sans politique).
create table if not exists public.ebook_leads (
  id           bigint generated always as identity primary key,
  product      text not null,
  email        text not null,
  visitor      text,
  country      text,
  unsubscribed boolean not null default false,
  created_at   timestamptz not null default now(),
  unique (product, email)
);
alter table public.ebook_leads enable row level security;

create or replace function public.ebook_lead(p_product text, p_email text, p_visitor text, p_country text)
 returns void language plpgsql security definer set search_path to 'public' as $function$
begin
  if p_product not in ('gesetzbuch', 'laws') or p_email !~* '^[^\s@]+@[^\s@]+\.[a-z]{2,24}$' then return; end if;
  insert into ebook_leads (product, email, visitor, country)
  values (p_product, lower(left(p_email, 254)), left(nullif(p_visitor, ''), 64), left(nullif(p_country, ''), 2))
  on conflict (product, email) do nothing;
end $function$;
revoke all on function public.ebook_lead(text, text, text, text) from public, anon, authenticated;
grant execute on function public.ebook_lead(text, text, text, text) to skillora_stats, service_role;
