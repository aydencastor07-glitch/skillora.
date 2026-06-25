-- Empêche les relevés de courbe en double pour un même compte le même jour.
-- (refresh-stats / analyze-account écrivent un seul point par compte et par jour ; cet index garantit
--  qu'aucun appel concurrent ne crée de doublon, ce qui gonflait l'historique et faussait la courbe.)

-- 1) Dédoublonnage des relevés existants : on garde le plus récent par (user, plateforme, pseudo, jour).
DELETE FROM public.account_snapshots a
USING public.account_snapshots b
WHERE a.user_id = b.user_id
  AND a.platform = b.platform
  AND lower(a.username) = lower(b.username)
  AND a.snapshot_date = b.snapshot_date
  AND a.created_at < b.created_at;

-- 2) Unicité d'un relevé par compte et par jour.
CREATE UNIQUE INDEX IF NOT EXISTS account_snapshots_daily_uidx
  ON public.account_snapshots (user_id, platform, lower(username), snapshot_date);
