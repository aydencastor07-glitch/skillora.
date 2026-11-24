-- Souffleur : relier un paiement Whop à la commande en attente par le nom + code postal de facturation
-- (quand l'e-mail du paiement n'est pas celui tapé dans le formulaire, ex. compte Whop existant de l'acheteur).
create or replace function public.blower_payer_adresse(p_nom text, p_zip text, p_payment text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare r blower_orders;
begin
  if exists (select 1 from blower_orders where payment_id = p_payment) then return null; end if;
  select * into r from blower_orders
   where paid_at is null and created_at > now() - interval '2 days'
     and lower(trim(nom)) = lower(trim(p_nom))
     and replace(lower(adresse->>'postal_code'), ' ', '') = replace(lower(trim(p_zip)), ' ', '')
   order by created_at desc limit 1 for update;
  if not found then return null; end if;
  update blower_orders set paid_at = now(), payment_id = p_payment where ref = r.ref;
  return to_jsonb(r);
end $$;
revoke all on function public.blower_payer_adresse(text, text, text) from public;
grant execute on function public.blower_payer_adresse(text, text, text) to skillora_stats;
