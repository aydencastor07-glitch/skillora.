-- Nettoyage automatique du bucket post-media (voir functions/storage-cleanup).
-- La liste de ce qu'on supprime est decidee ici, en base : la fonction web ne
-- fait qu'appliquer. Reservee a la cle de service.
create or replace function public.nettoyage_a_supprimer(p_limit int default 100)
returns setof text language sql stable security definer set search_path = public, storage as $$
  select name from storage.objects
  where bucket_id = 'post-media' and (
        (split_part(name, '/', 1) in ('improve-src', 'generate-src') and created_at < now() - interval '7 days')
     or (split_part(name, '/', 1) = 'improved' and created_at < '2026-08-01'))
  order by created_at
  limit p_limit;
$$;
revoke all on function public.nettoyage_a_supprimer(int) from public, anon, authenticated;
grant execute on function public.nettoyage_a_supprimer(int) to service_role;

-- Chaque heure, mais seulement s'il reste quelque chose a supprimer : tant que
-- le projet est bloque (402), l'appel echoue sans rien casser et sera retente.
-- La cle (en-tete x-cleanup-key) est posee a la main dans cron.job, pas ici.
