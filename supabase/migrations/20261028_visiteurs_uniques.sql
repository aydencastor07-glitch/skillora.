-- Une personne (empreinte IP + appareil) n'est comptée qu'UNE fois : sa première visite (avec son temps passé)
-- et son premier clic « Acheter ». Si elle revient, rien n'est ajouté ; seul un achat est enregistré à nouveau.
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
    -- déjà vue / déjà cliqué par cette personne : on ne compte pas une deuxième fois
    if coalesce(p_visitor, '') <> '' and exists (
      select 1 from ebook_events where product = p_product and type = p_type and visitor = left(p_visitor, 64)) then
      return;
    end if;
    insert into ebook_events (product, type, session, visitor, country, city, device, os, browser, referrer, source, lang)
    values (p_product, p_type, left(p_session, 64), left(nullif(p_visitor, ''), 64), left(nullif(p_country, ''), 2),
            left(nullif(p_city, ''), 60), p_device, p_os, p_browser, left(nullif(p_referrer, ''), 300),
            left(nullif(p_source, ''), 40), left(nullif(p_lang, ''), 12));
  end if;
end $$;
