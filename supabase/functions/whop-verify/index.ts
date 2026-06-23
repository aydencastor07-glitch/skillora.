// SKILLORA — whop-verify : vérifie l'abonnement Whop d'un utilisateur (Plan B sans webhook).
// Appelé par le front au retour du paiement. Cherche la membership Whop de l'utilisateur
// (via les métadonnées posées au checkout) et met à jour la table subscriptions.
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const PLAN_BY_WHOP_ID: Record<string, { plan: string; billing: string }> = {
  "plan_oDCfFU7lLws8B": { plan: "starter", billing: "monthly" },
  "plan_ecJbjbjlfxXOi": { plan: "starter", billing: "yearly"  },
  "plan_PJc5IYlQNCBBs": { plan: "growth",  billing: "monthly" },
  "plan_KZunBJm7YjLzC": { plan: "growth",  billing: "yearly"  },
  "plan_L776Rw5hJcIin": { plan: "elite",   billing: "monthly" },
  "plan_JePPrOlGknPbM": { plan: "elite",   billing: "yearly"  },
};

function isValidMembership(m: any): boolean {
  if (m?.valid === true) return true;
  const s = (m?.status || "").toString().toLowerCase();
  return ["active", "completed", "trialing"].includes(s);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const KEY = Deno.env.get("WHOP_API_KEY");
    if (!KEY) return j({ error: "Whop non configuré (clé API manquante)." }, 500);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return j({ error: "Non authentifié." }, 401);

    const email = (user.email || "").toLowerCase();

    // Parcourt les memberships Whop et trouve celle de cet utilisateur.
    let found: any = null;
    for (let page = 1; page <= 5 && !found; page++) {
      const r = await fetch(`https://api.whop.com/api/v2/memberships?per=50&page=${page}`, {
        headers: { "Authorization": `Bearer ${KEY}`, "Accept": "application/json" },
      });
      if (!r.ok) break;
      const d = await r.json().catch(() => ({}));
      const list: any[] = d?.data ?? [];
      for (const m of list) {
        if (!isValidMembership(m)) continue;
        const meta = m.metadata || {};
        const mEmail = (m.email || meta.email || (typeof m.user === "object" ? m.user?.email : "") || "").toString().toLowerCase();
        if (meta.user_id === user.id || (email && mEmail && mEmail === email)) { found = m; break; }
      }
      if (list.length < 50) break; // dernière page atteinte
    }

    if (!found) return j({ success: true, active: false });

    const planId = found.plan || found.plan_id || "";
    const meta = found.metadata || {};
    const mapped = PLAN_BY_WHOP_ID[planId];
    const plan = (meta.plan || mapped?.plan || "starter").toString().toLowerCase();
    const billing = (meta.billing || mapped?.billing || "monthly").toString().toLowerCase();
    const whopUserId = found.user_id || (typeof found.user === "string" ? found.user : found.user?.id) || null;

    const admin = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );
    await admin.from("subscriptions").upsert({
      user_id: user.id,
      plan,
      billing,
      status: "active",
      currency: "usd",
      whop_membership_id: found.id || null,
      whop_user_id: whopUserId,
      updated_at: new Date().toISOString(),
    }, { onConflict: "user_id" });

    return j({ success: true, active: true, plan, billing });
  } catch (e) {
    return j({ error: "Erreur serveur: " + (e?.message ?? String(e)) }, 500);
  }
});

function j(o: unknown, s = 200) {
  return new Response(JSON.stringify(o), { status: s, headers: { ...cors, "Content-Type": "application/json" } });
}
