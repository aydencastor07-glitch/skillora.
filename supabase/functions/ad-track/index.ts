// Enregistre un CLIC sur un lien publicitaire.
// ============================================
// Appelee par la page d'accueil des qu'un visiteur arrive avec ?src=<code>.
// Elle ne bloque rien : la page s'affiche, l'appel part en arriere-plan.
//
// Ce qu'on retient et pourquoi :
//   visitor  un identifiant depose sur l'appareil -> distingue un VISITEUR
//            d'un simple rechargement. Sans lui, un curieux qui actualise
//            trois fois compterait pour trois clics et fausserait le taux
//            de conversion.
//   country  d'ou viennent vraiment les gens (pas ce qu'ils declarent).
//   device   telephone ou ordinateur : deux publicites, deux resultats.
//
// Aucune donnee nominative n'est stockee ici : ni email, ni nom, ni adresse
// IP. L'identifiant de visiteur est un nombre au hasard, propre a Skillora.
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), {
    status: s,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

/* Le pays vient du reseau, pas du navigateur : impossible a maquiller par
   un simple reglage de langue. Supabase passe derriere Cloudflare, qui
   ajoute cf-ipcountry ; les autres en-tetes sont des filets. */
function pays(req: Request): string | null {
  for (const h of ["cf-ipcountry", "x-vercel-ip-country", "x-country-code", "x-geo-country"]) {
    const v = req.headers.get(h);
    if (v && v.length === 2 && v !== "XX") return v.toUpperCase();
  }
  return null;
}

function ville(req: Request): string | null {
  const v = req.headers.get("cf-ipcity") || req.headers.get("x-vercel-ip-city");
  return v ? decodeURIComponent(v).slice(0, 60) : null;
}

/* Appareil, systeme et navigateur, lus dans la signature du navigateur. */
function appareil(ua: string) {
  const u = (ua || "").toLowerCase();
  const tablette = /ipad|tablet|playbook|silk|(android(?!.*mobi))/.test(u);
  const mobile = /iphone|ipod|android.*mobi|windows phone|blackberry|opera mini/.test(u);
  const device = tablette ? "tablette" : mobile ? "mobile" : "desktop";
  const os = /iphone|ipad|ipod|ios/.test(u) ? "iOS"
    : /android/.test(u) ? "Android"
    : /windows/.test(u) ? "Windows"
    : /mac os|macintosh/.test(u) ? "macOS"
    : /linux/.test(u) ? "Linux" : null;
  const browser = /edg\//.test(u) ? "Edge"
    : /opr\/|opera/.test(u) ? "Opera"
    : /chrome|crios/.test(u) ? "Chrome"
    : /firefox|fxios/.test(u) ? "Firefox"
    : /safari/.test(u) ? "Safari" : null;
  return { device, os, browser };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const body = await req.json().catch(() => ({}));
    const code = String(body.code || "").trim().slice(0, 60).toLowerCase();
    if (!code || !/^[a-z0-9._-]{2,60}$/.test(code)) return json({ success: false }, 400);

    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
      { auth: { persistSession: false } },
    );

    // Le lien doit exister : sinon n'importe qui pourrait gonfler les
    // statistiques en inventant des codes.
    const { data: camp } = await admin.from("ad_campaigns")
      .select("id, archived").eq("code", code).maybeSingle();
    if (!camp) return json({ success: false, unknown: true }, 404);

    const ua = req.headers.get("user-agent") || "";
    const { device, os, browser } = appareil(ua);

    await admin.from("ad_clicks").insert({
      code,
      campaign_id: camp.id,
      visitor: String(body.visitor || "").slice(0, 64) || null,
      country: pays(req),
      city: ville(req),
      device, os, browser,
      referrer: String(body.referrer || "").slice(0, 300) || null,
      lang: String(body.lang || "").slice(0, 12) || null,
    });

    return json({ success: true });
  } catch (e) {
    // Un clic perdu ne doit jamais casser la page d'accueil.
    console.log("ad-track:", String((e as Error)?.message || e));
    return json({ success: false }, 200);
  }
});
