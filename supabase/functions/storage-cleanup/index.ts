// SKILLORA — nettoyage du stockage (bucket post-media).
// ====================================================
// Le plan gratuit de Supabase s'arrete a 1 Go : au-dela, TOUT le projet est
// bloque (connexion comprise). Les vrais coupables sont les fichiers de travail
// des fonctions « ameliorer » / « generer » : les videos sources (*-src) ne
// servent plus une fois le traitement fini.
// Ce que l'on supprime est choisi EN BASE par nettoyage_a_supprimer() :
//   improve-src/, generate-src/  plus vieux que 7 jours
//   improved/                    resultats des tests de juillet 2026
// Appelee chaque heure par pg_cron (tache storage_cleanup), seulement s'il reste
// quelque chose a supprimer. Protegee par une cle dont seule l'empreinte est ici.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const EMPREINTE = "80f1b77e74ef8c71163ca516eacaf847984723697417021560a08c5634488031";

async function sha(s: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

serve(async (req) => {
  try {
    if (await sha(req.headers.get("x-cleanup-key") || "") !== EMPREINTE) return new Response("forbidden", { status: 403 });
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    let supprimes = 0;
    for (let tour = 0; tour < 20; tour++) {          // 20 x 100 fichiers au plus par appel
      const { data, error } = await admin.rpc("nettoyage_a_supprimer", { p_limit: 100 });
      if (error) return new Response("err:" + error.message, { status: 500 });
      const noms = ((data as string[]) || []).filter(Boolean);
      if (!noms.length) break;
      const { error: e2 } = await admin.storage.from("post-media").remove(noms);
      if (e2) return new Response(`err:${e2.message} (deja ${supprimes})`, { status: 500 });
      supprimes += noms.length;
    }
    console.log("storage-cleanup:", supprimes, "fichiers supprimes");
    return new Response(JSON.stringify({ success: true, supprimes }), { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response("err:" + String((e as Error)?.message || e), { status: 500 });
  }
});
