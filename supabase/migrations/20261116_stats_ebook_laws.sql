-- /stats/ : les chiffres du livre anglais (« The Laws of the Mind », produit 'laws') à côté du livre allemand.
do $mig$
declare d text := pg_get_functiondef('public.stats_publiques(text)'::regprocedure);
begin
  if position('ebook_laws' in d) = 0 then
    d := replace(d, $q$'ebook',     admin_ebook('gesetzbuch', deb, fin),$q$, $q$'ebook',     admin_ebook('gesetzbuch', deb, fin),
    'ebook_laws', admin_ebook('laws', deb, fin),$q$);
    if position('ebook_laws' in d) = 0 then raise exception 'motif introuvable'; end if;
    execute d;
  end if;
end
$mig$;
