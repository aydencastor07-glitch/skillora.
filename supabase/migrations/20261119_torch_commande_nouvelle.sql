-- Comme torch_commande, mais dit si la commande est nouvelle (true) : évite de créer deux fois la commande Shopify
-- quand Stripe prévient deux fois (retour sur la page + webhook).
create or replace function public.torch_commande_nouvelle(p_id text, p_qty int, p_cents int, p_email text, p_name text, p_address jsonb)
returns boolean language sql security definer set search_path = public as $$
  with i as (
    insert into public.torch_orders (id, qty, amount_cents, email, name, address)
    values (p_id, p_qty, p_cents, p_email, p_name, p_address)
    on conflict (id) do nothing returning 1)
  select exists (select 1 from i);
$$;
revoke all on function public.torch_commande_nouvelle(text, int, int, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.torch_commande_nouvelle(text, int, int, text, text, jsonb) to skillora_stats;
