-- Boutique Truflame : commandes payées par PayPal / carte sur la page du briquet (api/torch.js).
-- L'utilisateur passe ensuite chaque commande dans AutoDS avec l'adresse enregistrée ici.
create table if not exists public.torch_orders (
  id text primary key,                 -- n° de commande PayPal
  created_at timestamptz not null default now(),
  qty int not null,
  amount_cents int not null,
  email text,
  name text,
  address jsonb,
  status text not null default 'a_commander'   -- a_commander / commandee / expediee
);
alter table public.torch_orders enable row level security;
revoke all on public.torch_orders from anon, authenticated;

create or replace function public.torch_commande(p_id text, p_qty int, p_cents int, p_email text, p_name text, p_address jsonb)
returns void language sql security definer set search_path = public as $$
  insert into public.torch_orders (id, qty, amount_cents, email, name, address)
  values (p_id, p_qty, p_cents, p_email, p_name, p_address)
  on conflict (id) do nothing;
$$;
revoke all on function public.torch_commande(text, int, int, text, text, jsonb) from public, anon, authenticated;
grant execute on function public.torch_commande(text, int, int, text, text, jsonb) to skillora_stats;
