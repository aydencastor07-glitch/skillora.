-- Ventes encaissées par la caisse PayPal du site (api/paypal-capture.js) :
-- une ligne dans ebook_sales par commande PayPal, lue par la page /stats/.
-- Le rôle skillora_stats (Vercel) ne peut qu'appeler cette fonction.
create or replace function public.ebook_vente(
  p_sale_id text, p_product text, p_price_cents int, p_currency text, p_country text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_product not in ('gesetzbuch') or coalesce(p_sale_id, '') = '' then return; end if;
  insert into ebook_sales (sale_id, product, price_cents, currency, country)
  values (left(p_sale_id, 64), p_product, greatest(0, coalesce(p_price_cents, 0)), left(coalesce(p_currency, 'EUR'), 3),
          left(nullif(upper(p_country), ''), 2))
  on conflict (sale_id) do nothing;
end $$;
revoke all on function public.ebook_vente(text, text, int, text, text) from public, anon, authenticated;
grant execute on function public.ebook_vente(text, text, int, text, text) to skillora_stats, service_role;
