import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PFM_BASE = "https://api.postforme.dev";
const VALID = ["facebook","instagram","x","tiktok","youtube","pinterest","linkedin","bluesky","threads","tiktok_business"];

// Nombre de comptes sociaux autorises par plan / cycle. 'none' (gratuit) = 1 compte.
const PLAN_ACCOUNTS = {
  starter: { monthly: 1, annual: 2 },
  growth:  { monthly: 3, annual: 6 },
  elite:   { monthly: 8, annual: 12 },
};
const FREE_ACCOUNTS = 1;

function json(o, s) {
  return new Response(JSON.stringify(o), { status: s || 200, headers: { ...cors, "Content-Type": "application/json" } });
}

async function tryAuthUrl(KEY, payload) {
  let res = await fetch(PFM_BASE + "/v1/social-accounts/auth-url", { method: "POST", headers: { "Content-Type": "application/json", "x-post-for-me-api-key": KEY }, body: JSON.stringify(payload) });
  let txt = await res.text();
  if (res.status === 401 || res.status === 403) {
    res = await fetch(PFM_BASE + "/v1/social-accounts/auth-url", { method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + KEY }, body: JSON.stringify(payload) });
    txt = await res.text();
  }
  let data = {};
  try { data = JSON.parse(txt); } catch (_e) { data = { raw: txt }; }
  return { res, data, txt };
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const KEY = Deno.env.get("POSTFORME_API_KEY");
    if (!KEY) return json({ success: false, error: "Cle Post for Me manquante (POSTFORME_API_KEY)." }, 500);

    const admin = createClient(Deno.env.get("SUPABASE_URL"), Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
    const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
    const { data: u } = await admin.auth.getUser(jwt);
    const userId = u && u.user ? u.user.id : null;
    if (!userId) return json({ success: false, error: "Non authentifie (token utilisateur manquant)." }, 401);

    const body = await req.json().catch(() => ({}));
    const platform = String(body.platform || "").trim();
    if (!VALID.includes(platform)) return json({ success: false, error: "Plateforme invalide: " + platform }, 400);

    // --- Controle d'abonnement : nombre de comptes autorises selon le plan ---
    // On compte les comptes deja connectes. Reconnecter une plateforme deja liee
    // ne consomme pas de slot. Echec OUVERT en cas d'erreur DB (ne jamais bloquer a tort).
    try {
      const norm = (p) => (String(p).toLowerCase() === "tiktok_business" ? "tiktok" : String(p).toLowerCase());

      const { data: subRow } = await admin.from("subscriptions")
        .select("plan, status, billing").eq("user_id", userId).maybeSingle();
      const plan = (subRow && subRow.plan ? String(subRow.plan) : "none").toLowerCase();
      const status = (subRow && subRow.status ? String(subRow.status) : "").toLowerCase();
      const billing = (subRow && subRow.billing ? String(subRow.billing) : "monthly").toLowerCase();
      const cycle = (billing === "yearly" || billing === "annual") ? "annual" : "monthly";

      let maxAccounts = FREE_ACCOUNTS;
      if (status === "active" && PLAN_ACCOUNTS[plan]) maxAccounts = PLAN_ACCOUNTS[plan][cycle] || FREE_ACCOUNTS;

      const { data: conns } = await admin.from("social_connections")
        .select("platform").eq("user_id", userId);
      const distinct = Array.from(new Set((conns || []).map((c) => norm(c.platform))));
      const alreadyHas = distinct.includes(norm(platform));

      if (!alreadyHas && distinct.length >= maxAccounts) {
        const paid = status === "active" && PLAN_ACCOUNTS[plan];
        return json({
          success: false,
          error: "limit_reached",
          plan: paid ? plan : "none",
          max: maxAccounts,
          current: distinct.length,
          message: paid
            ? ("Ton plan " + plan + " permet " + maxAccounts + " compte" + (maxAccounts > 1 ? "s" : "") + ". Tu en as deja " + distinct.length + ". Passe a un plan superieur pour en connecter davantage.")
            : ("Le compte gratuit permet " + FREE_ACCOUNTS + " compte connecte. Abonne-toi pour en connecter plusieurs."),
        }, 200);
      }
    } catch (subErr) {
      console.log("PFM connect: controle abonnement ignore (erreur) ->", String(subErr));
    }

    // 1er essai : posts + feeds (pour lire les stats). Si refuse, repli sur posts seul.
    let out = await tryAuthUrl(KEY, { platform, external_id: userId, permissions: ["posts", "feeds"] });
    if (!(out.res.ok && out.data && out.data.url)) {
      console.log("PFM connect: posts+feeds refuse (", out.res.status, ") -> repli posts. body=", out.txt.slice(0,200));
      out = await tryAuthUrl(KEY, { platform, external_id: userId, permissions: ["posts"] });
    }
    const res = out.res, data = out.data;
    console.log("PFM connect: final status=", res.status, "hasUrl=", !!(data && data.url));

    if (res.ok && data.url) return json({ success: true, url: data.url, platform: data.platform || platform });
    if (res.ok && !data.url) return json({ success: false, no_redirect: true, platform: data.platform || platform, error: "Cette plateforme ne se connecte pas par redirection." }, 200);
    return json({ success: false, error: (data && (data.error || data.message)) || ("Erreur Post for Me (" + res.status + ")"), status: res.status, raw: data }, 200);
  } catch (err) {
    console.log("PFM connect: exception", String(err));
    return json({ success: false, error: String(err) }, 500);
  }
});
