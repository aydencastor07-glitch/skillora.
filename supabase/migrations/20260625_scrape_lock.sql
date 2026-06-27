-- Verrou anti-scrape concurrent : garantit UN SEUL scrape SociaVault à la fois par compte.
-- (Sans ça, 3 appels analyze-account en parallèle = profil scrapé 3x = 3x les crédits.)
CREATE TABLE IF NOT EXISTS public.scrape_locks (
  lock_key   text PRIMARY KEY,
  locked_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.scrape_locks ENABLE ROW LEVEL SECURITY;
-- Aucune policy : seul le service_role (client admin de l'edge function) y accède, il contourne RLS.

-- Claim atomique : pose le verrou s'il est libre OU périmé (> p_ttl secondes). Renvoie true si on l'a obtenu.
CREATE OR REPLACE FUNCTION public.claim_scrape_lock(p_key text, p_ttl int)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE affected int;
BEGIN
  INSERT INTO public.scrape_locks(lock_key, locked_at)
  VALUES (p_key, now())
  ON CONFLICT (lock_key) DO UPDATE
    SET locked_at = now()
    WHERE public.scrape_locks.locked_at < now() - make_interval(secs => p_ttl);
  GET DIAGNOSTICS affected = row_count;
  RETURN affected > 0;
END;
$$;
