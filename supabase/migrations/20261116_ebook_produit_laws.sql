-- Deuxième produit : l'édition anglaise « The Laws of the Mind » (produit 'laws', page /laws/, prix en USD).
do $mig$
declare r record;
begin
  for r in select p.oid from pg_proc p join pg_namespace n on n.oid = p.pronamespace
           where n.nspname = 'public' and p.proname in ('ebook_enregistrer', 'ebook_vente') loop
    execute replace(pg_get_functiondef(r.oid), $q$not in ('gesetzbuch')$q$, $q$not in ('gesetzbuch', 'laws')$q$);
  end loop;
end
$mig$;
