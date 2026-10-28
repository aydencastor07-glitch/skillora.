-- Adresse e-mail de l'acheteur (celle de PayPal, puis la dernière qu'il a confirmée) : pré-remplie quand il revient.
alter table public.ebook_sales add column if not exists email text;

create or replace function public.ebook_email(p_sale_id text, p_email text)
returns void language sql security definer set search_path = public as $$
  update ebook_sales set email = left(p_email, 200) where sale_id = p_sale_id and coalesce(p_email, '') <> '';
$$;
create or replace function public.ebook_email_lire(p_sale_id text)
returns text language sql stable security definer set search_path = public as $$
  select email from ebook_sales where sale_id = p_sale_id;
$$;
revoke all on function public.ebook_email(text, text) from public, anon, authenticated;
revoke all on function public.ebook_email_lire(text) from public, anon, authenticated;
grant execute on function public.ebook_email(text, text) to skillora_stats, service_role;
grant execute on function public.ebook_email_lire(text) to skillora_stats, service_role;
