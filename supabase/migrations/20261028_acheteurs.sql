-- Reconnaître un acheteur qui revient (même navigateur ou même IP + appareil) : empreinte salée,
-- l'adresse IP n'est jamais enregistrée. Utilisé par api/mon-achat.js et api/download.js.
alter table public.ebook_sales add column if not exists buyer_fp text;
create index if not exists ebook_sales_fp_idx on public.ebook_sales (product, buyer_fp);

create or replace function public.ebook_vente(
  p_sale_id text, p_product text, p_price_cents int, p_currency text, p_country text, p_fp text)
returns void language plpgsql security definer set search_path = public as $$
begin
  if p_product not in ('gesetzbuch') or coalesce(p_sale_id, '') = '' then return; end if;
  insert into ebook_sales (sale_id, product, price_cents, currency, country, buyer_fp)
  values (left(p_sale_id, 64), p_product, greatest(0, coalesce(p_price_cents, 0)), left(coalesce(p_currency, 'EUR'), 3),
          left(nullif(upper(p_country), ''), 2), left(nullif(p_fp, ''), 64))
  on conflict (sale_id) do update set buyer_fp = coalesce(ebook_sales.buyer_fp, excluded.buyer_fp);
end $$;

-- Dernier achat (non remboursé) de cette empreinte pour ce livre, ou null.
create or replace function public.ebook_achat_fp(p_product text, p_fp text)
returns text language sql stable security definer set search_path = public as $$
  select sale_id from ebook_sales
   where product = p_product and buyer_fp = p_fp and coalesce(p_fp, '') <> '' and not refunded
   order by created_at desc limit 1;
$$;

-- Cette vente appartient-elle à cette empreinte ? Vente faite avant le suivi des acheteurs (buyer_fp vide) :
-- le premier qui l'ouvre avec le lien signé en devient l'acheteur.
create or replace function public.ebook_achat_ok(p_sale_id text, p_fp text)
returns boolean language plpgsql security definer set search_path = public as $$
begin
  if coalesce(p_fp, '') = '' then return false; end if;
  update ebook_sales set buyer_fp = p_fp where sale_id = p_sale_id and buyer_fp is null and not refunded;
  return exists(select 1 from ebook_sales where sale_id = p_sale_id and buyer_fp = p_fp and not refunded);
end $$;

revoke all on function public.ebook_vente(text, text, int, text, text, text) from public, anon, authenticated;
revoke all on function public.ebook_achat_fp(text, text) from public, anon, authenticated;
revoke all on function public.ebook_achat_ok(text, text) from public, anon, authenticated;
grant execute on function public.ebook_vente(text, text, int, text, text, text) to skillora_stats, service_role;
grant execute on function public.ebook_achat_fp(text, text) to skillora_stats, service_role;
grant execute on function public.ebook_achat_ok(text, text) to skillora_stats, service_role;
