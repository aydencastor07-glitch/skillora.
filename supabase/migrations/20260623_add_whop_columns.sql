-- SKILLORA — colonnes Whop sur la table subscriptions (additif, sans risque).
-- Permet au webhook Whop de relier un abonnement à un utilisateur.
alter table public.subscriptions
  add column if not exists whop_membership_id text,
  add column if not exists whop_user_id text;

create index if not exists subscriptions_whop_membership_id_idx
  on public.subscriptions (whop_membership_id);
