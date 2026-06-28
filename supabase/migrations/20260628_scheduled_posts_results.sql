-- Cache des URLs publiées par plateforme (permaliens Post for Me) pour chaque vidéo.
-- Évite de rappeler l'API Post for Me à chaque ouverture de la cloche / de l'accueil.
alter table public.scheduled_posts add column if not exists results jsonb;
