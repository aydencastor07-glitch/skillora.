-- Stats du livre : le parcours de la nouvelle page /laws/, étape par étape (visiteurs uniques),
-- les emails donnés (ebook_leads), et l'étape atteinte par chaque visite récente.
do $mig$
declare d text;
begin
  d := pg_get_functiondef('public.admin_ebook'::regproc);
  if position('''parcours''' in d) = 0 then
    d := replace(d, $q$    'dernieres', ($q$, $q$    'parcours', jsonb_build_object(
        'visiteurs', (select count(distinct visitor) from vu),
        'cta',       (select count(distinct visitor) from ev where type = 'cta'),
        'avis',      (select count(distinct visitor) from ev where type = 'reviews'),
        'veut',      (select count(distinct visitor) from ev where type = 'buy_click'),
        'email',     (select count(distinct visitor) from ev where type = 'email'),
        'emails',    (select count(*) from ebook_leads l where l.product = p_product and l.created_at >= p_from and l.created_at < p_to),
        'ventes',    (select count(*) from ve)),
    'dernieres', ($q$);
    d := replace(d, $q$'clic', exists(select 1 from ev e2 where e2.type = 'buy_click' and e2.session = vu.session)) x$q$,
      $q$'clic', exists(select 1 from ev e2 where e2.type = 'buy_click' and e2.session = vu.session),
          'etape', case
            when vu.visitor is not null and exists(select 1 from ebook_sales s where s.product = p_product and s.buyer_fp = vu.visitor) then 'paye'
            when exists(select 1 from ev e2 where e2.type = 'email' and (e2.session = vu.session or e2.visitor = vu.visitor)) then 'email'
            when exists(select 1 from ev e2 where e2.type = 'buy_click' and (e2.session = vu.session or e2.visitor = vu.visitor)) then 'veut'
            when exists(select 1 from ev e2 where e2.type = 'reviews' and (e2.session = vu.session or e2.visitor = vu.visitor)) then 'avis'
            when exists(select 1 from ev e2 where e2.type = 'cta' and (e2.session = vu.session or e2.visitor = vu.visitor)) then 'cta'
            else 'vu' end) x$q$);
    if position('''parcours''' in d) = 0 or position('''etape''' in d) = 0 then raise exception 'admin_ebook : remplacement impossible'; end if;
    execute d;
  end if;
end
$mig$;

-- Le parcours ne compte que depuis la mise en ligne de la nouvelle page (18/11/2026 00:50, heure de Paris),
-- sinon les 113 visiteurs de l'ancienne page faussent les pourcentages.
do $mig$
declare d text; n text := $q$ and created_at >= timestamptz '2026-11-17 23:50+00'$q$;
begin
  d := pg_get_functiondef('public.admin_ebook'::regproc);
  if position('2026-11-17 23:50' in d) = 0 then
    d := replace(d, $q$'visiteurs', (select count(distinct visitor) from vu),$q$, $q$'visiteurs', (select count(distinct visitor) from vu where true$q$ || n || $q$),$q$);
    d := replace(d, $q$from ev where type = 'cta'),$q$, $q$from ev where type = 'cta'$q$ || n || $q$),$q$);
    d := replace(d, $q$from ev where type = 'reviews'),$q$, $q$from ev where type = 'reviews'$q$ || n || $q$),$q$);
    d := replace(d, $q$'veut',      (select count(distinct visitor) from ev where type = 'buy_click'),$q$, $q$'veut',      (select count(distinct visitor) from ev where type = 'buy_click'$q$ || n || $q$),$q$);
    d := replace(d, $q$from ev where type = 'email'),$q$, $q$from ev where type = 'email'$q$ || n || $q$),$q$);
    d := replace(d, $q$'ventes',    (select count(*) from ve)),$q$, $q$'ventes',    (select count(*) from ve where true$q$ || n || $q$)),$q$);
    if (length(d) - length(replace(d, '2026-11-17 23:50', ''))) / 16 <> 6 then raise exception 'admin_ebook : remplacement incomplet'; end if;
    execute d;
  end if;
end
$mig$;
