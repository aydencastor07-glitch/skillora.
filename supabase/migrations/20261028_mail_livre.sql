-- E-mail « Mein E-Book senden » : l'acheteur choisit l'adresse. Compteur par vente pour éviter les abus (max 5 envois).
alter table public.ebook_sales add column if not exists mails int not null default 0;

create or replace function public.ebook_mail_compte(p_sale_id text)
returns int language plpgsql security definer set search_path = public as $$
declare n int;
begin
  update ebook_sales set mails = mails + 1 where sale_id = p_sale_id and not refunded returning mails into n;
  return coalesce(n, -1);   -- -1 : vente inconnue ou remboursée
end $$;
revoke all on function public.ebook_mail_compte(text) from public, anon, authenticated;
grant execute on function public.ebook_mail_compte(text) to skillora_stats, service_role;
